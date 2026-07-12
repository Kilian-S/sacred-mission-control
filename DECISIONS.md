# DECISIONS.md: choices the brief left open, and how they were resolved

Recorded per §1 of MISSION_CONTROL_BRIEF.md. One entry per decision, dated.

## 2026-07-11

1. **Chart rendering = matplotlib QtAgg canvases; map rendering = QGraphicsScene.**
   Matplotlib gives publication-quality PNG/SVG export for free (brief §2) and is already the
   sacred repo's plotting stack; the interactive map needs scene-graph hit-testing, hover and
   animation, which QGraphicsScene does natively. No web stack anywhere.
2. **Dependency pins match sacred's .venv** (numpy 2.4.4, networkx 3.6.1, scipy 1.17.1,
   matplotlib 3.10.9, torch 2.12.0, Python 3.13.7) so sacred modules imported as a library
   behave identically to how they behave inside sacred's own environment.
3. **The narrative index is a curated YAML file** (`data/narrative_index.yaml`) authored from
   reading the ledgers, one record per generation/arc, holding only strings that appear in the
   cited ledger. A unit test (`tests/test_narrative_index.py`) enforces provenance: every
   headline-number string in the index must literally occur in the ledger file it cites.
4. **Sacred repo access is confined to `smc/sacred_bridge/`**; nothing else may touch the
   sacred paths. All reads are tolerant (retry/skip partially-written JSON, missing files =
   typed "unavailable" results, never exceptions crossing into UI code).
5. **sys.path injection, not installation:** sacred's modules are imported by appending the
   sacred repo root to sys.path inside `sacred_bridge` lazily (first use), never at app
   import time. torch import is deferred to the policy worker threads (brief §2 lazy rule).
6. **Kyiv map** exists on disk (6083 nodes) but is not in sacred's CITY_PATHS registry; the
   app auto-detects city directories from `data/maps/` and shows Kyiv in map views where a
   plain graph suffices, labelled "not oracle-screened; no banked results".
7. **Era discipline in code, not convention:** every generation record carries `era:
   pre-fix|post-fix`; chart/compare widgets refuse to draw two eras on one axes (they render
   an explicit era divider instead). Live demos draw strategies/checkpoints only from
   post-fix families (gen13/gen14/gen15/gen16/gen19).
8. **Provenance is a first-class type:** `Provenance(source_kind, label)` with kinds
   `ledger` (grey "ledger:" caption) and `live` (accent "computed live · seed N" caption).
   All number-displaying widgets require one; there is no way to show an unlabelled number.
9. **Light mode only** enforced via a single palette in `smc/theme.py` (Okabe-Ito
   colour-blind-safe accents on warm greys); `QApplication` style "Fusion" so macOS dark
   mode cannot invert it.
10. **British English** throughout UI copy and docs (Kilian's global style rules; no em-dashes).

## 2026-07-12

11. **gen20-23 folded in** (the sacred agent banked them after handover). gen20's deployable
    object is the SINGLE best checkpoint (`defender_ep{N}.pt`, exact per-eval estimator, no TAP
    window), so its roster entry has no ensemble; verified to reproduce the banked 0.355 exactly.
    gen21 joins the roster explicitly labelled as the travel-objective transfer CONTROL, never
    as a SACRED arm. gen23 has no checkpoints; it is chart material (Obj-3 + History).
12. **Kyiv is now a live Playground city**: the whole-city zero-shot row is banked (gen16
    scale-axis), the five screened ODs come from `a2_graph_transfer_kyiv.json`, and a measured
    live solve takes ~0.6 s (the oracle is route-bound, not graph-bound). The old "no banked
    results" label was stale and is gone.
13. **Exhibit ledger quotes live in `data/exhibits.yaml` `quote_cards`**, rendered by
    `ExhibitBase.add_quote_cards`, so new-generation updates to the Objectives tab are data
    edits under the same verbatim-provenance test as everything else, not code edits.
