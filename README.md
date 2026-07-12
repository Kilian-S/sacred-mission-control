# SACRED Mission Control

A native macOS desktop application (PySide6, no web stack) that gives a human an
interactive feel for the SACRED MSc thesis project: contested convoy routing as a
Stackelberg security game on real city road networks, solved by adversarially-trained
reinforcement learning and scored against computable game-theoretic optima.

Five tabs (Cmd+1..5):

- **Home**: the pitch, the provenance legend (computed-live green vs ledger grey; era
  badges), a live hero demo (the deterministic convoy ambushed every sortie, the calibrated
  mixture slipping through) and the two headline ladders.
- **Playground**: pick a city (including whole-city Kyiv, 6083 nodes), a screened OD
  instance, fleet size N, interdiction budget K and the threat band; the LP re-solves live
  in milliseconds. Three modes: watch strategies play (trained SACRED actors join the
  roster, with a live route-mixture comparison against the LP equilibrium), duel the
  pattern-of-life interdictor whose ANTICIPATION glows on the map as it studies your
  recent routes (the gen19 game), or place the ambush yourself and discover why mixing
  beats you. Interceptions happen ON the ambush edge; destroyed convoys keep their
  strategy colour and gain a cross.
- **Objectives**: six exhibits pairing each research objective's verbatim promise with a
  live demonstration (the saddle, the environment, training dynamics incl. the gen23 ERB
  race, the SBO loop raced with click-a-design-onto-the-map, the ladder raced, zero-shot
  transfer to a never-seen city with the gen21 causal control and the Istanbul/Kyiv rungs).
- **History**: the project's development generation by generation (gen01-gen23 plus the
  side arcs), chapter dividers at the three pivots, an explicit era divider at the
  2026-07-09 node-ordering fix, verbatim provenance-checked ledger quotes,
  training-trajectory charts, campaign-era TensorBoard curves, and figures. Run families
  on disk with no curated record yet are flagged in a banner.
- **Documents**: a searchable markdown reader over the sacred repo and the thesis directory.

## Install and run (two commands)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

Requires the sibling `sacred/` repo (read-only data source) at `../sacred`, or set
`SACRED_ROOT`. Python 3.13 recommended (matches sacred's environment).

## Correctness contract

- Every ledger number on screen carries its ledger citation; every live-computed number is
  labelled "computed live" in green. The two are never visually confusable.
- The narrative index and exhibit data hold only strings that appear verbatim in the ledger
  they cite, enforced by `tests/test_narrative_index.py` and `tests/test_exhibits.py`.
- The live oracle pipeline reproduces the ledgers' banked anchors exactly
  (`tests/test_oracle_anchors.py`); trained-actor TAP ensembles reproduce the banked
  per-seed values exactly (`SMC_SLOW_TESTS=1` runs the torch-loading anchor test).
- Pre-fix and post-fix eras are never mixed in one visual; live demos load post-fix
  artefacts only.
- All demo randomness is seeded and the seed is shown.

## Keyboard

Cmd+1..5 tabs · Space play/pause (Playground, Objectives replays) · Cmd+E export the
current view plus every visible chart (publication PNG+SVG) and every visible map
(vector SVG + 3x PNG) to `~/Desktop/sacred-mc-exports/` · Cmd+F search (Documents) ·
Cmd+[ / Cmd+] back/forward (Documents) · arrow keys navigate sidebars.

## Development

```bash
.venv/bin/python -m pytest tests/ -q          # 28 tests incl. provenance + anchor regressions
SMC_SLOW_TESTS=1 .venv/bin/python -m pytest tests/ -q   # + the torch actor-anchor pins
.venv/bin/python scripts/smoke_screenshot.py  # walks every tab/exhibit, waits for async
                                              # work via ready predicates, screenshots each
```

Repo map: `smc/sacred_bridge/` (all read-only access to sacred: ledgers, runs, maps,
oracle wrappers, torch policy loading), `smc/game/` (sortie loop + the stacked dynamic
game), `smc/tabs/` (the five tabs), `smc/widgets/` (map engine, charts, cards),
`data/` (curated narrative index + presets, provenance-tested), `DATA_MAP.md` (artefact
inventory), `DECISIONS.md` (choices the brief left open), `SELF_REVIEW.md` (the hostile
review record).
