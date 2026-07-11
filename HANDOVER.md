# HANDOVER.md: state and onboarding for the next agent (2026-07-11)

Built in one day against `../MISSION_CONTROL_BRIEF.md` (read it first; it is the contract).
All five milestones delivered and committed; suite 23 green; smoke walks every tab and
exhibit and screenshots each (`scripts/smoke_screenshot.py`, output in `screenshots/`).

## What exists

- **Step 0**: `DATA_MAP.md` (artefact inventory of the sacred repo), `data/narrative_index.yaml`
  (32 generation records, 87 verbatim quotes, provenance-tested), `data/od_presets.yaml`
  (screened instances + banked anchors), `data/exhibits.yaml` (ladders, gen12 cells,
  transfer ladder, verbatim objective texts).
- **M1**: app shell (light Fusion theme in `smc/theme.py`, Cmd+1..5, Cmd+E), Documents tab
  (tree over sacred+thesis, Qt markdown, internal links, back/forward, full-text search),
  History tab (chapters at the three pivots, era divider at the node-ordering fix, quote
  cards linking into Documents, trajectory charts from run JSONs, figures incl. the
  dynassign gif).
- **M2**: `smc/widgets/mapview.py` (QGraphicsScene: pan/zoom, geojson geometry,
  vulnerability heat, route mixtures as thickness/opacity, OD markers, convoy dots,
  interception flash), `smc/sacred_bridge/oracle.py` (live LP layer), Watch mode with
  running-estimate convergence.
- **M3**: `smc/sacred_bridge/policies.py` (post-fix roster; TAP checkpoint ENSEMBLES: the
  deployable object is the trailing-averaged policy, so each roster entry loads the banked
  TAP window and averages route distributions; reproduces every banked per-seed value
  exactly), the pattern-of-life duel (`smc/game/duel.py` reuses sacred's gen19 functions),
  play-yourself defender and attacker modes.
- **M4**: Objectives (six exhibits) + Home (hero on 33-71 hard: 1.000 vs 0.167).
- **M5**: polish fixes, README, this file, `SELF_REVIEW.md`.

## Load-bearing invariants (do not break)

1. **Provenance**: no number reaches the screen without either a ledger citation or the
   green "computed live" label. Curated YAML quotes must be verbatim (whitespace-normalised;
   blockquote `>` markers stripped) in the cited ledger; tests enforce it.
2. **Era discipline**: pre-fix (gen09 and earlier) results never share a visual with
   post-fix; live demos never load pre-fix checkpoints (policies.py has no legacy-indexing
   path on purpose).
3. **Exactness**: `smc/sacred_bridge/maps.py` replicates sacred's graph construction
   byte-for-byte (last duplicate edge feature wins, w = max(1.0, round(length/100, 1)),
   string node ids); `oracle.py` passes `norm_edges=G.edges()` exactly like the env.
   `tests/test_oracle_anchors.py` pins four ledger anchors; if it fails, fix the pipeline,
   never the test.
4. **Read-only boundary**: nothing outside `smc/sacred_bridge/` touches the sacred paths;
   nothing anywhere writes into sacred/ or thesis/. The only write target is
   `~/Desktop/sacred-mc-exports/`.
5. **Laziness**: torch/torch_geometric only imported inside worker threads
   (`policies.py`, `duel.py`); tfevents never loaded eagerly; heavy work through
   `smc/workers.run_in_background`.

## Known limitations / candidate next steps

- Campaign-era tfevents (gen01-07) are indexed in the narrative index (`tb_runs` fields)
  but no tfevents chart loader is wired; campaign cards show figures + verbatim quotes
  only. A worker-side `event_accumulator` reader would slot into
  `smc/sacred_bridge/gen_charts.py`.
- Single-convoy trained actors: none exist on disk post-fix except zst_step0's one actor
  (walk-mode), so single-convoy live demos are oracle-level only (honest per DATA_MAP).
- K=3 live solves take ~20-30 s (warned in the UI); K>=4 needs sacred's greedy BR
  (A4) and is not wired.
- The gen12 sweep chart draws ledger values (provenance-tested); live re-solving of all
  10 cells would need ~1 min of ALNS+LP per open and was deliberately not done.
- The Obj-4 live race uses a ridge surrogate (labelled "simplified") over the banked F3
  design table; the banked D1 curves (neural surrogate) are shown alongside.
- If the sacred agent lands NEW generations (gen20+), add a record to
  `data/narrative_index.yaml` (quotes verbatim!) and, if it has run JSONs, a spec in
  `gen_charts._FAMILY_SPECS`. Everything else auto-detects.

## Verification

```bash
.venv/bin/python -m pytest tests/ -q                      # all green expected
.venv/bin/python scripts/smoke_screenshot.py /tmp/shots   # 27 screenshots, exit 0
./run.sh                                                  # idle memory well under 1 GB
```
Note: pipe the smoke's output to a file, not through `grep`/`head` (piping has produced
flaky empty runs).
