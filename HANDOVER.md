# HANDOVER.md: state and onboarding for the next agent (2026-07-11, updated 2026-07-12)

Built in one day against `MISSION_CONTROL_BRIEF.md` (read it first; it is the contract),
then extended in a second autonomous round (see "Round 3" below and SELF_REVIEW.md).
All five milestones delivered and committed; suite 28 green (+2 opt-in torch anchor
tests via `SMC_SLOW_TESTS=1`); smoke walks every tab and exhibit with ready-predicate
waits and screenshots each (`scripts/smoke_screenshot.py`, output in `screenshots/`).

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
6. **Worker lifetime**: `run_in_background` parks every worker in a module registry
   until its finished/failed signal is DELIVERED on the UI thread. Do not restore
   `setAutoDelete(True)`: with autoDelete, the pool destroys the sender right after
   run(), and queued results are silently dropped whenever the UI thread is busy
   (this was the documented smoke flakiness and the round-2 byte-identical shots).

## Round 3 (2026-07-12): what changed after the second review

- **gen20-23 + d3g folded in** (History records with verbatim quotes, f2/c1 chart
  loaders, exhibit quote cards, verdict lines); **Kyiv is a live Playground city**
  (5 screened ODs, ~0.6 s solves); the transfer ladder gained the Istanbul and Kyiv
  rungs; Home's generation count is computed from the index.
- **Keyboard fixed**: `Meta+` bound the Control key on macOS; everything is `Ctrl+`
  (= Cmd) now.
- **Interception truthfulness**: convoys die ON the ambush edge (scene-length
  `MapView.fraction_of_edge`); the duel's ambush springs at the moment of interception;
  destroyed convoys keep their strategy colour and gain a cross.
- **The adversary made visible**: the duel glows the interdictor's current softmax
  anticipation on the map (absolute-mass opacity, toggleable); Watch compares the
  current defender's route mixture against the LP equilibrium per route.
- **Cartography**: city name + zoom-aware scale bar (drawn in scene coordinates so
  exports keep composition); arterial/minor street weights; Cmd+E exports every visible
  map as vector SVG + 3x PNG.
- **Campaign evidence**: gen01-07 cards now draw their TensorBoard scalars (rolling
  mean over the raw cloud) via `gen_charts.load_tb_chart`.
- **Honesty furniture**: History banners uncurated run families; Home teaches the
  provenance colour language; Obj-3 has loading/error states; the History gif scales.
- **Reliability**: the worker lost-result race fixed (invariant 6 above); the smoke
  waits on ready predicates instead of fixed delays.

## Known limitations / candidate next steps

- Single-convoy trained actors: none exist on disk post-fix except zst_step0's one actor
  (walk-mode), so single-convoy live demos are oracle-level only (honest per DATA_MAP).
- K=3 live solves take ~20-30 s (warned in the UI); K>=4 needs sacred's greedy BR
  (A4) and is not wired.
- The gen12 sweep chart draws ledger values (provenance-tested); live re-solving of all
  10 cells would need ~1 min of ALNS+LP per open and was deliberately not done.
- The Obj-4 live race uses a ridge surrogate (labelled "simplified") over the banked F3
  design table; the banked D1 curves (neural surrogate) are shown alongside.
- Obj-1's attacker-options bars are indexed by interdiction set; linking a bar hover to
  its edge on a mini-map is the next didactic step.
- If the sacred agent lands NEW generations (gen24+), the History banner will flag them;
  add a record to `data/narrative_index.yaml` (quotes verbatim!) and, if it has run
  JSONs, a spec in `gen_charts._FAMILY_SPECS`. Everything else auto-detects.

## Verification

```bash
.venv/bin/python -m pytest tests/ -q                      # 28 green expected
SMC_SLOW_TESTS=1 .venv/bin/python -m pytest tests/ -q    # + 2 torch actor-anchor pins
.venv/bin/python scripts/smoke_screenshot.py /tmp/shots   # 27 screenshots, exit 0
./run.sh                                                  # idle memory well under 1 GB
```
The historical smoke flakiness when piping output was almost certainly the worker
lost-result race (fixed; see invariant 6). Writing the smoke's output to a file remains
the tidy habit.

## v1.1 (2026-07-13): the Blocks A+B fold-in + Compare mode

Sacred's claims-defence programme (gen24/gen25, A2-A8, B1/B3/B4) is folded in; three
standing claims were re-scoped on sacred's own binding wording rules (D3-Gdansk per-seed,
the ZST two-regime synthesis, Obj-4's "simultaneous"). New app surface: the Playground
COMPARE mode (synchronised small multiples, up to four protagonists incl. the Block-A
control actors, one shared convergence chart), the OBJECTIVE selector (mission/threshold/
linear, live re-solves reproducing B3's law; duel gated to mission; banked anchors hidden
off-mission; the sortie engine accumulates the realised objective per family so running
estimates converge to exact values under every objective), the amortiser ladder + A7
gap-closure charts + live intel-error corruption in the ZST exhibit, the A8 prevalence
explorer in Obj-5 (click a dot to open that OD in the Playground), and a live gap-closure
line in the Watch readouts. Roster conventions per arm are in DECISIONS.md items 13-15;
the gen24 centred-TAP-window discovery is documented there and in DATA_MAP §8. B2 (LLM
benchmark) and C3 (HTML export) intentionally out of scope per Kilian, 2026-07-13; when
B2 live results land, the natural home is a three-register ladder column beside the
gen19 anchors in the duel view.
