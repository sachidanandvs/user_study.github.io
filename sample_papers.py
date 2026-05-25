"""Sample N papers common across the 3 baselines and stage their final decks + goals.

For each sampled paper, copies the final deck file as-is (PDF for autoslides/html,
PPTX for convdeck — conversion is a separate step) and writes a normalized
goals.json: [{"category": ..., "requirement": ...}, ...].

Layout produced under --dst:
    papers.json                          # list of sampled paper IDs
    manifest.json                        # per-paper file paths + goal counts
    decks/<paper>/autoslides.pdf
    decks/<paper>/convdeck.pptx
    decks/<paper>/html.pdf
    goals/<paper>/autoslides.json
    goals/<paper>/convdeck.json
    goals/<paper>/html.json
"""

import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

CONVDECK_PREFIX = re.compile(r"^paper\d+_")


def canonical_convdeck(name: str) -> str:
    return CONVDECK_PREFIX.sub("", name)


def discover(src: Path):
    autoslides_dir = src / "autoslides_user_sim"
    convdeck_dir = src / "convdeck_user_sim"
    html_dir = src / "html_user_sim"

    autoslides = {p.name: p for p in autoslides_dir.iterdir() if p.is_dir()}
    html = {p.name: p for p in html_dir.iterdir() if p.is_dir()}
    convdeck = {canonical_convdeck(p.name): p for p in convdeck_dir.iterdir() if p.is_dir()}

    return autoslides, convdeck, html


def find_autoslides_final(folder: Path) -> Optional[Path]:
    matches = sorted(folder.glob("*_final.pdf"))
    return matches[-1] if matches else None


def load_autoslides_goals(folder: Path):
    path = folder / "goals.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return [{"category": g.get("category", ""), "requirement": g.get("requirement", "")} for g in data]


def load_convdeck_goals(folder: Path):
    path = folder / "satisfaction_eval.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return [{"category": g.get("category", ""), "requirement": g.get("goal", "")}
            for g in data.get("goal_evaluations", [])]


def load_html_goals(folder: Path):
    path = folder / "summary.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return [{"category": g.get("category", ""), "requirement": g.get("goal", "")}
            for g in data.get("final_gemini_verdicts", [])]


def stage_paper(paper: str, autoslides_folder: Path, convdeck_folder: Path, html_folder: Path,
                dst: Path, force: bool) -> Optional[dict]:
    decks_dir = dst / "decks" / paper
    goals_dir = dst / "goals" / paper
    decks_dir.mkdir(parents=True, exist_ok=True)
    goals_dir.mkdir(parents=True, exist_ok=True)

    # autoslides
    auto_src = find_autoslides_final(autoslides_folder)
    if auto_src is None:
        print(f"  [skip] {paper}: no *_final.pdf in autoslides", file=sys.stderr)
        return None
    auto_goals = load_autoslides_goals(autoslides_folder)
    if auto_goals is None:
        print(f"  [skip] {paper}: no goals.json in autoslides", file=sys.stderr)
        return None

    # convdeck
    conv_src = convdeck_folder / "final.pptx"
    if not conv_src.exists():
        print(f"  [skip] {paper}: no final.pptx in convdeck", file=sys.stderr)
        return None
    conv_goals = load_convdeck_goals(convdeck_folder)
    if conv_goals is None:
        print(f"  [skip] {paper}: no satisfaction_eval.json in convdeck", file=sys.stderr)
        return None

    # html
    html_src = html_folder / "final.pdf"
    if not html_src.exists():
        print(f"  [skip] {paper}: no final.pdf in html", file=sys.stderr)
        return None
    html_goals = load_html_goals(html_folder)
    if html_goals is None:
        print(f"  [skip] {paper}: no summary.json in html", file=sys.stderr)
        return None

    def copy(src_path: Path, dst_path: Path):
        if dst_path.exists() and not force:
            return
        shutil.copy2(src_path, dst_path)

    auto_dst = decks_dir / "autoslides.pdf"
    conv_dst = decks_dir / "convdeck.pptx"
    html_dst = decks_dir / "html.pdf"
    copy(auto_src, auto_dst)
    copy(conv_src, conv_dst)
    copy(html_src, html_dst)

    (goals_dir / "autoslides.json").write_text(json.dumps(auto_goals, indent=2))
    (goals_dir / "convdeck.json").write_text(json.dumps(conv_goals, indent=2))
    (goals_dir / "html.json").write_text(json.dumps(html_goals, indent=2))

    return {
        "paper": paper,
        "autoslides": {
            "deck": str(auto_dst.relative_to(dst)),
            "deck_source": str(auto_src.relative_to(autoslides_folder.parent.parent)),
            "goals": str((goals_dir / "autoslides.json").relative_to(dst)),
            "n_goals": len(auto_goals),
        },
        "convdeck": {
            "deck": str(conv_dst.relative_to(dst)),
            "deck_source": str(conv_src.relative_to(convdeck_folder.parent.parent)),
            "goals": str((goals_dir / "convdeck.json").relative_to(dst)),
            "n_goals": len(conv_goals),
        },
        "html": {
            "deck": str(html_dst.relative_to(dst)),
            "deck_source": str(html_src.relative_to(html_folder.parent.parent)),
            "goals": str((goals_dir / "html.json").relative_to(dst)),
            "n_goals": len(html_goals),
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path,
                    default=Path("/work/nvme/bgbc/sv69/llm_test/PPTAgent-experiment/user_study_data"),
                    help="Root containing autoslides_user_sim / convdeck_user_sim / html_user_sim")
    ap.add_argument("--dst", type=Path,
                    default=Path(__file__).resolve().parent,
                    help="Output root (default: this script's directory)")
    ap.add_argument("--n", type=int, default=30, help="Number of papers to sample (default 30)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    ap.add_argument("--force", action="store_true", help="Overwrite existing copied files")
    args = ap.parse_args()

    autoslides, convdeck, html = discover(args.src)
    common = sorted(set(autoslides) & set(convdeck) & set(html))
    print(f"autoslides={len(autoslides)}  convdeck={len(convdeck)}  html={len(html)}")
    print(f"common papers across all 3 baselines: {len(common)}")
    if len(common) < args.n:
        print(f"WARN: only {len(common)} common papers, less than requested {args.n}", file=sys.stderr)

    rng = random.Random(args.seed)
    pool = list(common)
    rng.shuffle(pool)

    staged = []
    used = []
    skipped = []
    i = 0
    while len(staged) < args.n and i < len(pool):
        paper = pool[i]
        i += 1
        entry = stage_paper(paper, autoslides[paper], convdeck[paper], html[paper],
                            args.dst, args.force)
        if entry is None:
            skipped.append(paper)
            continue
        staged.append(entry)
        used.append(paper)

    if len(staged) < args.n:
        print(f"WARN: only staged {len(staged)} / {args.n} papers", file=sys.stderr)

    (args.dst / "papers.json").write_text(json.dumps(used, indent=2))
    manifest = {
        "n_papers": len(staged),
        "seed": args.seed,
        "src": str(args.src),
        "skipped": skipped,
        "papers": staged,
    }
    (args.dst / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nStaged {len(staged)} papers under {args.dst}")
    print(f"Skipped {len(skipped)} papers (missing files)")
    print(f"Wrote papers.json and manifest.json")


if __name__ == "__main__":
    main()
