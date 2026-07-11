# SACRED Mission Control

A native macOS desktop application (PySide6, no web stack) that gives a human an
interactive feel for the SACRED MSc thesis project: contested convoy routing as a
Stackelberg security game on real city road networks, solved by adversarially-trained
reinforcement learning and scored against computable game-theoretic optima.

Five tabs (Cmd+1..5):

- **Home**: the pitch, a live hero demo (the deterministic convoy ambushed every sortie,
  the calibrated mixture slipping through) and the two headline ladders.
- **Playground**: pick a city, a screened OD instance, fleet size N, interdiction budget K
  and the threat band; the LP re-solves live in milliseconds. Three modes: watch strategies
  play (including banked trained SACRED actors), duel the pattern-of-life interdictor
  yourself (the gen19 game), or place the ambush yourself and discover why mixing beats you.
- **Objectives**: six exhibits pairing each research objective's verbatim promise with a
  live demonstration (the saddle, the environment, training dynamics, the SBO loop raced,
  the ladder raced, zero-shot transfer to a never-seen city).
- **History**: the project's development generation by generation, chapter dividers at the
  three pivots, an explicit era divider at the 2026-07-09 node-ordering fix, verbatim
  provenance-checked ledger quotes, training-trajectory charts and figures.
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
  per-seed values exactly.
- Pre-fix and post-fix eras are never mixed in one visual; live demos load post-fix
  artefacts only.
- All demo randomness is seeded and the seed is shown.

## Keyboard

Cmd+1..5 tabs · Space play/pause (Playground, Objectives replays) · Cmd+E export the
current view plus every visible chart as publication PNG+SVG to
`~/Desktop/sacred-mc-exports/` · Cmd+F search (Documents) · Cmd+[ / Cmd+] back/forward
(Documents) · arrow keys navigate sidebars.

## Development

```bash
.venv/bin/python -m pytest tests/ -q          # 23 tests incl. provenance + anchor regressions
.venv/bin/python scripts/smoke_screenshot.py  # walks every tab/exhibit, screenshots each
```

Repo map: `smc/sacred_bridge/` (all read-only access to sacred: ledgers, runs, maps,
oracle wrappers, torch policy loading), `smc/game/` (sortie loop + the stacked dynamic
game), `smc/tabs/` (the five tabs), `smc/widgets/` (map engine, charts, cards),
`data/` (curated narrative index + presets, provenance-tested), `DATA_MAP.md` (artefact
inventory), `DECISIONS.md` (choices the brief left open), `SELF_REVIEW.md` (the hostile
review record).
