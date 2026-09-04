#!/usr/bin/env python3
"""
sample_traces.py — seeded random sample of trace_ids for W5 Task Set C.

Requirement#2: "Draw a RANDOM sample of 20 traces with a seeded selection
you paste in the write-up." This script IS that seeded selection: run it,
paste the seed and the printed trace_ids into notes.md, and use exactly
that list for open-coding. Re-running with the same seed and the same
traces.jsonl always reproduces the same 20 ids, which is what "provable"
means here — anyone can rerun this and check you didn't cherry-pick.

Usage:
    python sample_traces.py --n 20 --seed 42
    python sample_traces.py --n 10 --seed 7 --out sample_bonus.json   # for the bonus 10-more-from-demo-set draw
    python sample_traces.py --replay-pick --seed 42                  # seeded pick of ONE trace_id for the replay-evidence requirement
"""
import argparse
import json
import sys
from pathlib import Path

from trace_store import TraceStore

DEFAULT_LOG = Path(__file__).parent / "traces" / "traces.jsonl"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log-path", default=str(DEFAULT_LOG), help="Path to traces.jsonl")
    ap.add_argument("--n", type=int, default=20, help="Sample size (default 20)")
    ap.add_argument("--seed", type=int, required=True, help="Random seed — paste this in your write-up")
    ap.add_argument("--out", default=None, help="Optional path to also write the sample as JSON")
    ap.add_argument("--replay-pick", action="store_true",
                     help="Instead of an n-sample, seed-pick ONE trace_id for the replay-evidence requirement")
    args = ap.parse_args()

    store = TraceStore(args.log_path)
    total = len(store.all_ids())

    if args.replay_pick:
        picked = store.pick_one(args.seed)
        if picked is None:
            print(f"No traces found in {args.log_path}. Generate traffic against /ask first.", file=sys.stderr)
            sys.exit(1)
        print(f"Total traces available: {total}")
        print(f"Seed: {args.seed}")
        print(f"Replay trace_id: {picked}")
        if args.out:
            Path(args.out).write_text(json.dumps({"seed": args.seed, "trace_id": picked}, indent=2))
        return

    try:
        sample = store.sample(args.n, args.seed)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Total traces available: {total}")
    print(f"Sample size: {args.n}")
    print(f"Seed: {args.seed}")
    print("Sampled trace_ids (sorted):")
    for tid in sample:
        print(f"  {tid}")

    if args.out:
        Path(args.out).write_text(json.dumps({"seed": args.seed, "n": args.n, "trace_ids": sample}, indent=2))
        print(f"\nWrote sample to {args.out}")


if __name__ == "__main__":
    main()