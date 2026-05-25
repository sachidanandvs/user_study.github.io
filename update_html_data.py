"""Refresh the inlined data blocks in index.html from papers.json + goals/.

Reads:
    papers.json                            # ["<paper>", ...]
    goals/<paper>/{autoslides,convdeck,html}.json

Rewrites the two marker-delimited blocks in index.html:
    // === BEGIN PAPERS_ALL === ... // === END PAPERS_ALL ===
    // === BEGIN ALL_GOALS  === ... // === END ALL_GOALS  ===

Run after sample_papers.py / preprocess_decks.py.
"""

import argparse
import json
import re
import sys
from pathlib import Path

BASELINES = ("autoslides", "convdeck", "html")

PAPERS_BEGIN = "// === BEGIN PAPERS_ALL ==="
PAPERS_END   = "// === END PAPERS_ALL ==="
GOALS_BEGIN  = "// === BEGIN ALL_GOALS ==="
GOALS_END    = "// === END ALL_GOALS ==="
DECKS_BEGIN  = "// === BEGIN DECK_FILES ==="
DECKS_END    = "// === END DECK_FILES ==="


def load_goals(goals_root: Path, paper: str):
    out = {}
    for b in BASELINES:
        path = goals_root / paper / f"{b}.json"
        if not path.exists():
            print(f"WARN: missing {path}", file=sys.stderr)
            out[b] = []
            continue
        out[b] = json.loads(path.read_text())
    return out


def replace_block(html: str, begin: str, end: str, new_body: str) -> str:
    pattern = re.compile(
        r"(" + re.escape(begin) + r"[^\n]*\n)(.*?)(" + re.escape(end) + r")",
        re.DOTALL,
    )
    if not pattern.search(html):
        raise SystemExit(f"ERROR: markers {begin!r} / {end!r} not found in index.html")
    return pattern.sub(lambda m: m.group(1) + new_body + m.group(3), html)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parent
    ap.add_argument("--papers",   type=Path, default=here / "papers.json")
    ap.add_argument("--goals",    type=Path, default=here / "goals")
    ap.add_argument("--decks",    type=Path, default=here / "preprocessed_decks",
                    help="Dir containing per-paper decks_map.json")
    ap.add_argument("--html",     type=Path, default=here / "index.html")
    args = ap.parse_args()

    if not args.papers.exists():
        sys.exit(f"ERROR: {args.papers} not found")
    if not args.goals.exists():
        sys.exit(f"ERROR: {args.goals} not found")
    if not args.html.exists():
        sys.exit(f"ERROR: {args.html} not found")

    papers = json.loads(args.papers.read_text())
    all_goals = {paper: load_goals(args.goals, paper) for paper in papers}

    deck_files = {}
    for paper in papers:
        m = args.decks / paper / "decks_map.json"
        if not m.exists():
            print(f"WARN: missing {m} (run preprocess_decks.py)", file=sys.stderr)
            deck_files[paper] = {}
            continue
        deck_files[paper] = json.loads(m.read_text())

    papers_js = "let papersAll = " + json.dumps(papers, indent=2, ensure_ascii=False) + ";\n"
    goals_js  = "const ALL_GOALS = " + json.dumps(all_goals, ensure_ascii=False) + ";\n"
    decks_js  = "const DECK_FILES = " + json.dumps(deck_files, ensure_ascii=False) + ";\n"

    html = args.html.read_text()
    html = replace_block(html, PAPERS_BEGIN, PAPERS_END, papers_js)
    html = replace_block(html, GOALS_BEGIN,  GOALS_END,  goals_js)
    html = replace_block(html, DECKS_BEGIN,  DECKS_END,  decks_js)
    args.html.write_text(html)

    n_goals = sum(len(v) for paper in all_goals.values() for v in paper.values())
    print(f"Updated {args.html.name}: {len(papers)} papers, {n_goals} goals total.")


if __name__ == "__main__":
    main()
