"""
trace_store.py — durable, replayable trace logging for the HR RAG assistant.

Built for W5 Task Set C ("Read 20 real traces and hand back a ranked
taxonomy"). Before this module existed, RAGTracer (in app.py) only printed
colored step-by-step logs to stdout — nothing was written to disk, there was
no trace_id, no prompt version, and no way to replay a past question. That
fails requirement #1 of the task outright ("prove your traces are
replayable"). This module fixes that:

  * Every /ask call gets a stable trace_id and is appended as one JSON line
    to a trace file (JSONL — one call = one line, easy to `wc -l`, sample,
    and grep).
  * Each record carries every field requirement #1 asks for: prompt_version,
    prompt_hash, retrieved chunk_ids + scores, model + generation params, and
    the raw (pre-postprocessing) model output — plus the final answer, timing,
    and whether the context-validation gate passed.
  * Defensive PII Redaction: TraceStore.log() strictly enforces best-effort deep regex
    redaction on all fields before serialization to sanitize employee PII
    before writing to traces.jsonl.
  * Privacy-Preserving Replay: Replay operates as privacy-preserving replay,
    re-executing the model call using the durable prompt template version artifact,
    recorded generation parameters, and the persisted redacted context snapshot.
    It does not claim bit-for-bit exact reproduction of unredacted raw PII.
  * sample() gives a seeded, provable random sample of trace_ids — pass the
    same seed to reproduce the same 20 rows.
"""

from __future__ import annotations

import json
import random
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
#  PII / identifier redaction
# ─────────────────────────────────────────────────────────────────────────────
#
# This is intentionally pattern-based, not an NER model — it's cheap, fully
# deterministic (important: redaction must not itself make traces
# unreplayable), and covers the identifier shapes that actually show up in
# an HR context. It is a best-effort layer, not a guarantee: free-text
# employee names typed into a question ("what's the leave balance for John
# Smith") are NOT reliably caught by regex alone. Document this limitation
# in notes.md rather than overstating what redact() does.
_PATTERNS = [
    # Employee ID formats: EMP-1234, E00123, employee id 88231
    (re.compile(r"\b(?:EMP|emp)[-_ ]?\d{3,8}\b"), "[REDACTED_EMP_ID]"),
    (re.compile(r"\b[Ee]\d{5,8}\b"), "[REDACTED_EMP_ID]"),
    (re.compile(r"(?i)\bemployee\s*(?:id|number|no\.?)\s*[:#]?\s*\d{3,8}\b"), "[REDACTED_EMP_ID]"),
    # SSN-shaped
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    # Emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED_EMAIL]"),
    # Phone numbers (loose, US-ish + generic)
    (re.compile(r"\b(?:\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"), "[REDACTED_PHONE]"),
    # "Name: John Smith" / "Employee: John Smith" style labeled fields
    (re.compile(r"(?i)\b(?:name|employee|staff)\s*:\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"), lambda m: m.group(0).split(":")[0] + ": [REDACTED_NAME]"),
]


def redact(text: str | None) -> str:
    """Best-effort redaction of employee identifiers/names. Called before
    ANY field is added to a trace record — never after."""
    if not text:
        return text or ""
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


def redact_deep(value):
    """Recursively redact strings inside dicts/lists (used for chunk text
    snapshots stored in a trace record)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_deep(v) for v in value]
    return value


# ─────────────────────────────────────────────────────────────────────────────
#  Durable Prompt version registry
# ─────────────────────────────────────────────────────────────────────────────
#
# Every system prompt sent to the LLM must be traceable to an exact version
# string and stored durably on disk, so that (a) a trace records which prompt
# produced an answer and (b) replay can look the exact text back up even across
# process restarts. NEVER mutate an existing entry's text — bump the version
# key instead, the way you would a migration.

QA_PROMPT_VERSION = "qa-answer-v1"
RERANK_PROMPT_VERSION = "rerank-v1"
REWRITE_PROMPT_VERSION = "rewrite-v1"

PROMPT_REGISTRY: dict[str, str] = {}
PROMPTS_DIR = Path(__file__).parent / "prompts"


def register_prompt(version: str, text: str) -> str:
    """Register (or confirm) a prompt version's exact text durably on disk.
    Returns the text unchanged so callers can do `system = register_prompt(V, "...")`
    inline at the definition site."""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt_file = PROMPTS_DIR / f"{version}.txt"
    if prompt_file.exists():
        stored_text = prompt_file.read_text(encoding="utf-8")
        if stored_text != text:
            raise ValueError(
                f"Prompt version {version!r} already registered on disk with different "
                f"text. Bump the version string instead of editing it in place "
                f"— replaying an old trace must use the prompt that produced it."
            )
    else:
        prompt_file.write_text(text, encoding="utf-8")

    PROMPT_REGISTRY[version] = text
    return text


def get_prompt(version: str) -> str | None:
    """Retrieve prompt text by version from in-memory cache or durable disk artifact."""
    if version in PROMPT_REGISTRY:
        return PROMPT_REGISTRY[version]
    prompt_file = PROMPTS_DIR / f"{version}.txt"
    if prompt_file.exists():
        text = prompt_file.read_text(encoding="utf-8")
        PROMPT_REGISTRY[version] = text
        return text
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Trace store
# ─────────────────────────────────────────────────────────────────────────────

class TraceStore:
    """Append-only JSONL trace log with defensive PII redaction, lookup,
    and seeded sampling."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        self._lock = threading.Lock()

    def log(self, record: dict) -> str:
        """Append one trace record. Applies best-effort defensive deep regex redaction
        before persistence (regex coverage is not a complete PII detection guarantee).
        Assigns trace_id, timestamp, and cryptographic prompt_hash if missing."""
        # Enforce defensive deep redaction across all record fields
        record = redact_deep(dict(record))
        record.setdefault("trace_id", str(uuid.uuid4()))
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        if "prompt_version" in record and "prompt_hash" not in record:
            p_text = get_prompt(record["prompt_version"])
            if p_text:
                import hashlib
                record["prompt_hash"] = "sha256:" + hashlib.sha256(p_text.encode("utf-8")).hexdigest()

        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return record["trace_id"]

    def all(self) -> list[dict]:
        """Read all valid trace records from the JSONL log, logging warnings for any corrupted lines."""
        if not self.path.exists():
            return []
        out = []
        with self.path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as err:
                    import logging
                    logging.getLogger("trace_store").warning(
                        "Skipping corrupted trace line %d in %s: %s (Error: %s)",
                        line_no, self.path, line[:60], err
                    )
        return out

    def all_ids(self) -> list[str]:
        return [r["trace_id"] for r in self.all() if "trace_id" in r]

    def get(self, trace_id: str) -> dict | None:
        """Lookup a trace by trace_id (last-write-wins)."""
        match = None
        for r in self.all():
            if r.get("trace_id") == trace_id:
                match = r
        return match

    def sample(self, n: int, seed: int) -> list[str]:
        """Seeded random sample of n trace_ids, sorted for a stable,
        pasteable write-up. Raises if fewer than n traces exist."""
        if n <= 0:
            raise ValueError(f"Sample size n must be greater than 0, got {n}.")
        ids = sorted(self.all_ids())
        if len(ids) < n:
            raise ValueError(
                f"Only {len(ids)} traces logged so far — need at least {n} "
                f"to draw a sample of {n}. Generate more real traffic first."
            )
        rng = random.Random(seed)
        chosen = rng.sample(ids, n)
        return sorted(chosen)

    def pick_one(self, seed: int) -> str | None:
        """Seeded single-trace pick, for the replay-evidence requirement."""
        ids = self.all_ids()
        if not ids:
            return None
        rng = random.Random(seed)
        return rng.choice(sorted(ids))


# Default instance for the module
TRACES = TraceStore(Path(__file__).parent / "traces" / "traces.jsonl")