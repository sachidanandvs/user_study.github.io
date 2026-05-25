# New User Study — Preprocessing

Pipeline to build a slide-refinement user study comparing 3 baselines:
**autoslides**, **convdeck**, **html**.

Source: `/work/nvme/bgbc/sv69/llm_test/PPTAgent-experiment/user_study_data/`

## Status

| Stage | Script | State |
| --- | --- | --- |
| 1. Sample papers + stage final decks + normalize goals | `sample_papers.py` | **Done** (not yet executed — needs a compute/login env with Python ≥ 3.7) |
| 2. Render each deck (PDF & PPTX) → slide PNGs → 2×2-grid PDF | `preprocess_decks.py` | **Done** (not yet executed) |
| 3. HTML user-study UI (per-evaluator sampling, anonymized A/B/C, True/False per goal) | `index.html` + `apps_script.js` | **Done** — needs `APPS_SCRIPT_URL` filled in |

---

## Stage 1 — `sample_papers.py` (done)

### What it does

1. **Discovers** paper folders in all 3 baselines under `--src`. For `convdeck_user_sim`, strips the `paper\d+_` prefix so folders match across baselines.
2. **Intersects** the three sets and **samples** `--n` papers (default 30) with a fixed `--seed` (default 42) for reproducibility.
3. For each sampled paper:
   - **autoslides**: copies the `*_final.pdf` (last round, e.g. `round5_final.pdf`) → `decks/<paper>/autoslides.pdf`. Goals come from `goals.json` (already `[{category, requirement}, …]`).
   - **convdeck**: copies `final.pptx` → `decks/<paper>/convdeck.pptx` (conversion deferred to Stage 2). Goals come from `satisfaction_eval.json` → `goal_evaluations[*]`, with `goal` renamed to `requirement`.
   - **html**: copies `final.pdf` → `decks/<paper>/html.pdf`. Goals come from `summary.json` → `final_gemini_verdicts[*]`, with `goal` renamed to `requirement`.
4. Writes normalized goals to `goals/<paper>/{autoslides,convdeck,html}.json` as `[{category, requirement}, …]`.
5. Skips any paper missing a required file and tops up from the shuffled pool until `--n` are staged (or pool exhausted).

### Run it

```bash
python3 sample_papers.py            # uses defaults
# or
python3 sample_papers.py --n 30 --seed 42 --force
```

Requires Python ≥ 3.7 (the login node's `/usr/bin/python3` is 3.6 — use `python3.11` or `python3.12`).

### Output layout

```
new_user_study/
  papers.json                 # ["<paper_id>", ...] (length n)
  manifest.json               # full per-paper paths + goal counts + list of skipped papers
  decks/<paper>/autoslides.pdf
  decks/<paper>/convdeck.pptx
  decks/<paper>/html.pdf
  goals/<paper>/autoslides.json
  goals/<paper>/convdeck.json
  goals/<paper>/html.json
```

Each `goals/*.json` has the uniform shape:

```json
[
  {"category": "Content Inclusion/Exclusion Requirements",
   "requirement": "The slide deck should not include more than one equation across the whole deck."},
  ...
]
```

The goal *sets are not aligned* across baselines for the same paper — that's expected and OK for this study (each baseline was refined against its own goals).

---

## Stage 2 — `preprocess_decks.py` (done)

For each paper in `papers.json` and each baseline:

1. **Render slides** to per-slide PNGs (cached under `<baseline>_pages/`):
   - PDF (autoslides, html) → `pdf2image.convert_from_path`
   - PPTX (convdeck) → `soffice --headless --convert-to pdf` then `pdf2image`
2. **Compose 2×2 grid pages** (`<baseline>_grid_pages/page_NN.png`) — same logic as [`../img2pdf_custom.py`](../img2pdf_custom.py): tile every 4 slides into a 2-wide × 2-tall canvas, white-pad the last page if needed, draw black separator lines.
3. **Write a scrollable PDF** `<baseline>_grid.pdf` via `img2pdf`.

### Run it

```bash
python3 preprocess_decks.py                       # all papers, default dpi=100
python3 preprocess_decks.py --dpi 144 --force     # higher res, re-render
python3 preprocess_decks.py --only 3DLinker_...   # subset
python3 preprocess_decks.py --soffice ~/libreoffice/opt/libreoffice25.8/program/soffice
```

Dependencies: `pip install pdf2image img2pdf Pillow`, plus Poppler (`pdftoppm`) and a LibreOffice (`soffice`) on PATH (or pass `--soffice <path>`).

### Output layout

```
preprocessed_decks/
  manifest.json
  <paper>/
    autoslides_grid.pdf
    convdeck_grid.pdf
    html_grid.pdf
```

Intermediate per-slide PNGs and 2×2 composite PNGs are written to a temp directory and discarded — only the final grid PDFs are kept (this directory gets committed to git for the site, so we don't want the bulk). Outputs are idempotent — re-runs skip any paper whose `<baseline>_grid.pdf` already exists. Pass `--force` to re-render. The script also deletes any `*_pages/` / `*_grid_pages/` folders left over from earlier runs.

## Stage 3 — UI (planned)

Re-skin `../index.html`:
- One block per paper, three columns (one per baseline) showing the `*_grid.pdf` in an iframe.
- Below each column, render that baseline's goals list (from `goals/<paper>/<baseline>.json`) grouped by category.
- Decide ranking / scoring schema with the user before wiring submission.

Open question for Stage 5: ranking criteria + whether to also show the source paper PDF anywhere.
