"""Aggregate verdicts from the user-study CSV: avg satisfaction per baseline x category.

Verdict mapping: TRUE -> 1, FALSE -> 0 (case-insensitive).
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?",
                    default=Path(__file__).resolve().parent / "results.csv",
                    type=Path)
    args = ap.parse_args()

    # totals[(baseline, category)] = [sum, count]
    totals = defaultdict(lambda: [0, 0])
    baseline_totals = defaultdict(lambda: [0, 0])
    category_totals = defaultdict(lambda: [0, 0])
    overall = [0, 0]

    with args.csv.open(newline="") as f:
        for row in csv.DictReader(f):
            verdict = (row.get("verdict") or "").strip().lower()
            if verdict not in ("true", "false"):
                continue
            score = 1 if verdict == "true" else 0
            b = row["baseline"]
            c = row["category"]
            totals[(b, c)][0] += score
            totals[(b, c)][1] += 1
            baseline_totals[b][0] += score
            baseline_totals[b][1] += 1
            category_totals[c][0] += score
            category_totals[c][1] += 1
            overall[0] += score
            overall[1] += 1

    baselines = sorted({b for b, _ in totals})
    categories = sorted({c for _, c in totals})

    # Per-baseline x category table
    print("=== Avg satisfaction per (baseline x category) ===\n")
    col_w = max(len(b) for b in baselines + ["baseline"]) + 2
    cat_w = max(len(c) for c in categories) + 2
    header = "category".ljust(cat_w) + "".join(b.ljust(col_w) for b in baselines)
    print(header)
    print("-" * len(header))
    for c in categories:
        row = c.ljust(cat_w)
        for b in baselines:
            s, n = totals.get((b, c), (0, 0))
            row += (f"{s/n:.3f} (n={n})" if n else "-").ljust(col_w)
        print(row)

    # Per-category totals (across baselines)
    print("\n=== Avg per category (all baselines pooled) ===")
    for c in categories:
        s, n = category_totals[c]
        print(f"  {c:<45s} {s/n:.3f}  (n={n})")

    # Per-baseline totals (across categories)
    print("\n=== Avg per baseline (all categories pooled) ===")
    for b in baselines:
        s, n = baseline_totals[b]
        print(f"  {b:<15s} {s/n:.3f}  (n={n})")

    print(f"\nOverall: {overall[0]/overall[1]:.3f} (n={overall[1]})")


if __name__ == "__main__":
    main()
