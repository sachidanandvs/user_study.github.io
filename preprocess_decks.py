"""Render each paper's baseline decks into 2x2-grid PDFs for the user study.

Pipeline per (paper, baseline):
    1. Render the deck to per-slide PNGs:
       - PDF (autoslides, html)    -> pdf2image.convert_from_path
       - PPTX (convdeck)            -> soffice --convert-to pdf -> pdf2image
    2. Group every 4 slides into a 2x2 grid page (white-padded if the last
       page has fewer than 4 slides), drawing black separator lines.
    3. Write a combined scrollable PDF via img2pdf.

Inputs come from `decks/<paper>/{autoslides.pdf, convdeck.pptx, html.pdf}`
(produced by sample_papers.py).

Outputs:
    preprocessed_decks/<paper>/<baseline>_pages/slide_0001.png    (rendered slides cache)
    preprocessed_decks/<paper>/<baseline>_grid_pages/page_00.png  (2x2 composites)
    preprocessed_decks/<paper>/<baseline>_grid.pdf                (final scrollable PDF)

Dependencies: pdf2image (poppler), python-pptx not needed, img2pdf, Pillow, soffice/libreoffice.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import img2pdf
from PIL import Image, ImageDraw
from pdf2image import convert_from_path

# Mirror ArcDeck/slide_generation/pipeline.py: prepend local LibreOffice install to PATH.
_lo_programs = glob.glob(os.path.expanduser("~/libreoffice/opt/libreoffice*/program"))
if _lo_programs:
    os.environ["PATH"] = _lo_programs[-1] + ":" + os.environ["PATH"]

GRID_W = 2
GRID_H = 2
SLIDES_PER_PAGE = GRID_W * GRID_H
SEPARATOR_PX = 3
DEFAULT_DPI = 100

BASELINES = [
    ("autoslides", "autoslides.pdf", "pdf"),
    ("convdeck",   "convdeck.pptx",  "pptx"),
    ("html",       "html.pdf",       "pdf"),
]


# ---------- rendering ----------

def render_pdf_to_pngs(pdf_path: Path, out_dir: Path, dpi: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path), dpi=dpi)
    for i, img in enumerate(images, start=1):
        img.save(out_dir / f"slide_{i:04d}.png", "PNG")
    return sorted(out_dir.glob("slide_*.png"))


def render_pptx_to_pngs(pptx_path: Path, out_dir: Path, dpi: int, soffice_bin: str):
    """Convert pptx -> pdf via soffice, then pdf -> pngs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as user_install:
        cmd = [
            soffice_bin,
            "--headless", "--norestore", "--nolockcheck",
            f"-env:UserInstallation=file://{user_install}",
            "--convert-to", "pdf",
            str(pptx_path),
            "--outdir", tmp,
        ]
        env = os.environ.copy()
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        pdfs = list(Path(tmp).glob("*.pdf"))
        if not pdfs:
            raise RuntimeError(f"soffice produced no PDF for {pptx_path}")
        return render_pdf_to_pngs(pdfs[0], out_dir, dpi)


# ---------- 2x2 grid composition ----------

def compose_grid_pages(slide_paths, out_dir: Path):
    """Tile every SLIDES_PER_PAGE slides into a GRID_W x GRID_H page PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not slide_paths:
        return []

    with Image.open(slide_paths[0]) as first:
        w, h = first.size

    page_w = w * GRID_W
    page_h = h * GRID_H
    pages = []
    for i in range(0, len(slide_paths), SLIDES_PER_PAGE):
        chunk = slide_paths[i:i + SLIDES_PER_PAGE]
        canvas = Image.new("RGB", (page_w, page_h), color="white")
        for j, p in enumerate(chunk):
            with Image.open(p) as img:
                if img.size != (w, h):
                    img = img.resize((w, h))
                col = j % GRID_W
                row = j // GRID_W
                canvas.paste(img, (w * col, h * row))
        draw = ImageDraw.Draw(canvas)
        for col in range(1, GRID_W):
            x = w * col
            draw.rectangle([x - SEPARATOR_PX // 2, 0, x + SEPARATOR_PX // 2, page_h], fill="black")
        for row in range(1, GRID_H):
            y = h * row
            draw.rectangle([0, y - SEPARATOR_PX // 2, page_w, y + SEPARATOR_PX // 2], fill="black")
        page_path = out_dir / f"page_{i // SLIDES_PER_PAGE:03d}.png"
        canvas.save(page_path)
        pages.append(page_path)
    return pages


def write_pdf(page_paths, out_pdf: Path):
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(out_pdf, "wb") as f:
        f.write(img2pdf.convert([str(p) for p in page_paths]))


# ---------- per-paper driver ----------

def baseline_to_deckname(paper: str):
    """Deterministically shuffle [autoslides, convdeck, html] to deck1/2/3 per paper.

    Returns {baseline: 'deckN.pdf'}.
    """
    names = [b for b, _, _ in BASELINES]
    h = hashlib.sha256(paper.encode("utf-8")).digest()
    # Fisher-Yates using bytes from the digest.
    order = names[:]
    for i in range(len(order) - 1, 0, -1):
        j = h[i % len(h)] % (i + 1)
        order[i], order[j] = order[j], order[i]
    return {baseline: f"deck{order.index(baseline) + 1}.pdf" for baseline in names}


def rename_paper(paper: str, out_root: Path):
    """Re-shuffle existing PDFs in preprocessed_decks/<paper>/ without re-rendering.

    Reads the current baseline -> filename mapping from decks_map.json (or, as a
    fallback, the legacy <baseline>_grid.pdf naming) and renames each file to
    its new slot per baseline_to_deckname(paper). Two-pass rename via temp
    names avoids clobbering.
    """
    paper_out = out_root / paper
    if not paper_out.is_dir():
        print(f"  [skip] {paper}: {paper_out} missing", file=sys.stderr)
        return {b: None for b, _, _ in BASELINES}

    # Determine current baseline -> filename mapping.
    map_path = paper_out / "decks_map.json"
    if map_path.exists():
        current = json.loads(map_path.read_text())
        # validate every referenced file exists
        missing = [b for b, fn in current.items() if not (paper_out / fn).exists()]
        if missing:
            print(f"  [error] {paper}: decks_map.json references missing files for {missing}",
                  file=sys.stderr)
            return {b: None for b, _, _ in BASELINES}
    else:
        # Fall back to legacy naming.
        current = {}
        for baseline, _, _ in BASELINES:
            legacy = paper_out / f"{baseline}_grid.pdf"
            if legacy.exists():
                current[baseline] = legacy.name
        if len(current) != len(BASELINES):
            present = list(current.keys())
            print(f"  [error] {paper}: no decks_map.json and legacy files only for {present}",
                  file=sys.stderr)
            return {b: None for b, _, _ in BASELINES}

    new_map = baseline_to_deckname(paper)
    if current == new_map:
        print(f"  [skip] {paper}: mapping already matches target")
        # still ensure decks_map.json is on disk
        map_path.write_text(json.dumps(new_map, indent=2))
        return {b: str((paper_out / fn).relative_to(out_root)) for b, fn in new_map.items()}

    # Two-pass: rename each baseline's current file to a unique temp, then to its final name.
    tmp_for = {b: paper_out / f".__tmp_{b}.pdf" for b in current}
    for b, fn in current.items():
        (paper_out / fn).rename(tmp_for[b])
    for b, tmp in tmp_for.items():
        tmp.rename(paper_out / new_map[b])
    map_path.write_text(json.dumps(new_map, indent=2))

    moved = [(current[b], new_map[b]) for b in current]
    print(f"  [rename] {paper}: " + ", ".join(f"{a}->{c}" for a, c in moved))
    return {b: str((paper_out / fn).relative_to(out_root)) for b, fn in new_map.items()}


def process_paper(paper: str, decks_dir: Path, out_root: Path, dpi: int,
                  soffice_bin: str, force: bool):
    paper_out = out_root / paper
    paper_out.mkdir(parents=True, exist_ok=True)
    mapping = baseline_to_deckname(paper)
    results = {}
    for baseline, fname, kind in BASELINES:
        src = decks_dir / paper / fname
        out_name = mapping[baseline]
        grid_pdf = paper_out / out_name

        if not src.exists():
            print(f"  [skip] {paper}/{baseline}: missing {src.name}", file=sys.stderr)
            results[baseline] = None
            continue

        if grid_pdf.exists() and not force:
            print(f"  [cache] {paper}/{baseline}: {out_name} exists")
            results[baseline] = str(grid_pdf.relative_to(out_root))
            continue

        # Render slides + compose grid pages in a temp dir; only the final PDF is kept.
        with tempfile.TemporaryDirectory(prefix=f"{baseline}_") as tmp:
            tmp_dir = Path(tmp)
            pages_dir = tmp_dir / "slides"
            grid_pages_dir = tmp_dir / "grid_pages"
            try:
                if kind == "pdf":
                    slides = render_pdf_to_pngs(src, pages_dir, dpi)
                else:
                    slides = render_pptx_to_pngs(src, pages_dir, dpi, soffice_bin)
            except Exception as e:
                print(f"  [error] {paper}/{baseline}: render failed: {e}", file=sys.stderr)
                results[baseline] = None
                continue

            if not slides:
                print(f"  [error] {paper}/{baseline}: no slides rendered", file=sys.stderr)
                results[baseline] = None
                continue
            print(f"  [render] {paper}/{baseline}: {len(slides)} slides")

            pages = compose_grid_pages(slides, grid_pages_dir)
            write_pdf(pages, grid_pdf)
            print(f"  [pdf]    {paper}/{baseline}: {len(pages)} grid page(s) -> {out_name}")
            results[baseline] = str(grid_pdf.relative_to(out_root))

    # Write the per-paper baseline -> filename map (for the page + analysis).
    (paper_out / "decks_map.json").write_text(json.dumps(mapping, indent=2))

    # Clean up leftover cache dirs and any old <baseline>_grid.pdf files from prior runs.
    for d in paper_out.glob("*_pages"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    for d in paper_out.glob("*_grid_pages"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    for stale in paper_out.glob("*_grid.pdf"):
        stale.unlink()

    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parent
    ap.add_argument("--decks", type=Path, default=here / "decks",
                    help="Input decks/ directory (default: ./decks)")
    ap.add_argument("--out",   type=Path, default=here / "preprocessed_decks",
                    help="Output directory (default: ./preprocessed_decks)")
    ap.add_argument("--papers", type=Path, default=here / "papers.json",
                    help="JSON list of paper IDs to process (default: ./papers.json)")
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI,
                    help=f"Rendering DPI (default {DEFAULT_DPI})")
    ap.add_argument("--soffice", default="soffice",
                    help="Path to soffice/libreoffice binary (default: 'soffice' on PATH)")
    ap.add_argument("--force", action="store_true",
                    help="Re-render and overwrite cached outputs")
    ap.add_argument("--only", nargs="*",
                    help="Process only these paper IDs (subset of papers.json)")
    ap.add_argument("--rename-only", action="store_true",
                    help="Skip rendering; just re-shuffle existing PDFs in preprocessed_decks/ "
                         "using the current paper-name -> mapping function. Reads existing "
                         "decks_map.json (or falls back to legacy <baseline>_grid.pdf names) "
                         "to know what each file currently is, then renames to the new mapping "
                         "and rewrites decks_map.json. Source decks/ is not needed.")
    args = ap.parse_args()

    if not args.papers.exists():
        print(f"ERROR: {args.papers} not found. Run sample_papers.py first.", file=sys.stderr)
        sys.exit(1)
    papers = json.loads(args.papers.read_text())
    if args.only:
        papers = [p for p in papers if p in set(args.only)]

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"dpi": args.dpi, "grid": [GRID_H, GRID_W], "papers": {}}

    for paper in papers:
        print(f"\n=== {paper} ===")
        if args.rename_only:
            manifest["papers"][paper] = rename_paper(paper, args.out)
        else:
            manifest["papers"][paper] = process_paper(
                paper, args.decks, args.out, args.dpi, args.soffice, args.force
            )

    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nDone. Manifest -> {args.out / 'manifest.json'}")


if __name__ == "__main__":
    main()
