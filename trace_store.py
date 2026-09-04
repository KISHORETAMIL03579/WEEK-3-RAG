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
    retrieved chunk_ids + scores, model + generation params, and the raw
    (pre-postprocessing) model output — plus the final answer, timing, and
    whether the context-validation gate passed.
  * PII redaction runs BEFORE the record is built, not after — see redact().
    Nothing unredacted ever reaches json.dumps().
  * sample() gives a seeded, provable random sample of trace_ids — pass the
    same seed to reproduce the same 20 rows.
  * Replay reconstructs the exact context + prompt used for a trace_id and
    re-runs the LLM call, so the original and replayed output can be shown
    side by side (see replay_trace() in app.py, which uses this store).
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
#  Prompt version registry
# ─────────────────────────────────────────────────────────────────────────────
#
# Every system prompt sent to the LLM must be traceable to an exact version
# string, so that (a) a trace records which prompt produced an answer and
# (b) replay can look the exact text back up even if app.py's live prompt
# has since changed. NEVER mutate an existing entry's text — bump the
# version key instead, the way you would a migration.

QA_PROMPT_VERSION = "qa-answer-v1"
RERANK_PROMPT_VERSION = "rerank-v1"
REWRITE_PROMPT_VERSION = "rewrite-v1"

PROMPT_REGISTRY: dict[str, str] = {}


def register_prompt(version: str, text: str) -> str:
    """Register (or confirm) a prompt version's exact text. Returns the
    text unchanged so callers can do `system = register_prompt(V, "...")`
    inline at the definition site — one source of truth for both the live
    call and future replay lookups."""
    if version in PROMPT_REGISTRY and PROMPT_REGISTRY[version] != text:
        raise ValueError(
            f"Prompt version {version!r} already registered with different "
            f"text. Bump the version string instead of editing it in place "
            f"— replaying an old trace must use the prompt that produced it."
        )
    PROMPT_REGISTRY[version] = text
    return text


def get_prompt(version: str) -> str | None:
    return PROMPT_REGISTRY.get(version)


# ─────────────────────────────────────────────────────────────────────────────
#  Trace store
# ─────────────────────────────────────────────────────────────────────────────

class TraceStore:
    """Append-only JSONL trace log with lookup and seeded sampling."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        self._lock = threading.Lock()

    def log(self, record: dict) -> str:
        """Append one trace record. Assigns trace_id/timestamp if missing.
        Returns the trace_id. Caller is responsible for having already
        redacted any user-controlled text in `record` — this method does
        NOT redact, so nothing bypasses redact()/redact_deep() by mistake."""
        record = dict(record)
        record.setdefault("trace_id", str(uuid.uuid4()))
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return record["trace_id"]

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def all_ids(self) -> list[str]:
        return [r["trace_id"] for r in self.all() if "trace_id" in r]

    def get(self, trace_id: str) -> dict | None:
        # Last-write-wins in case a trace_id somehow appears twice.
        match = None
        for r in self.all():
            if r.get("trace_id") == trace_id:
                match = r
        return match

    def sample(self, n: int, seed: int) -> list[str]:
        """Seeded random sample of n trace_ids, sorted for a stable,
        pasteable write-up. Raises if fewer than n traces exist."""
        ids = self.all_ids()
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