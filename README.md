# SACRED Mission Control

A native macOS desktop application (PySide6, no web stack) that gives a human an
interactive feel for the SACRED MSc thesis project: contested convoy routing as a
Stackelberg security game on real city road networks, solved by adversarially-trained
reinforcement learning and scored against computable game-theoretic optima.

Written to be understood by a stranger with a high-school education in under a minute per
screen: plain language leads, one idea per screen, and the proof (verbatim ledger quotes)
is always one click away rather than in your face.

Five tabs (Cmd+1..5):

- **Home**: the pitch in three plain sentences, and a live side-by-side hero: the
  professional planner (left) keeps getting ambushed on its unchanging route while SACRED
  (right) mostly slips through, each with a running "missions failed" tally.
- **Playground**: a four-card chooser (watch the game, you defend, you attack, compare
  policies). One shared scenario bar names each city crossing in plain words (whole-city
  Kyiv included); everything advanced (fleet size, ambush teams, danger level, the loss
  rule, dice seed) folds into a "Change the rules" drawer. Every game shows a big
  percentage ("chance the mission fails"), a goalpost bar between "the proven optimum" and
  "the best any predictable plan can do", and a live outcome strip; when you defend, the
  enemy's anticipation glows on the map. First-run coach tutorials explain each mode.
- **Objectives**: six exhibits, each a plain "we promised X, here is X" with one
  interactive demonstration (the game made a slider, a city turned into a board, training
  that knows when to stop, base-siting on a map, the ladder raced, transfer to a
  never-seen city as a battery bar) and the ledger quotes collapsed into a "From the
  record" drawer.
- **History**: the project generation by generation, each card led by a plain "what
  happened" sentence with the verbatim record beneath, chapter dividers at the pivots and
  an explicit era divider at the 2026-07-09 fix.
- **Documents**: the ledgers themselves, comfortably typeset (large type, generous line
  spacing) and searchable; the source markdown is never modified.

## Run it from a fresh clone (macOS)

The app is a viewer of the SACRED project data (city maps, run results, trained-AI
checkpoints). That data is gitignored at source and is too large for git, so it is
delivered as a **GitHub Release asset** rather than committed. After cloning:

```bash
git clone https://github.com/Kilian-S/sacred-mission-control.git
cd sacred-mission-control
open "setup.command"      # or double-click it in Finder
```

`setup.command` downloads the data (~400 MB, once), builds a private virtual
environment (~2 GB, once), and launches the app. Every later run is just another
double-click. If Finder blocks it ("unidentified developer"), right-click →
Open the first time.

Prefer the Terminal, or already have the data? The two-command path still works:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

The app finds its data automatically in this order: `SACRED_ROOT` if set, else a
sibling `../sacred` (the dev / downloadable-bundle layout), else `./sacred` inside
the clone (what `setup.command` creates). Requires Python 3.11+ (3.13 recommended).

### Maintainer: cutting a data release

```bash
scripts/make_data_asset.sh                 # builds sacred-data.zip from ../sacred
gh release create data-v1 sacred-data.zip -t 'SACRED data' -n 'Runtime data for the app.'
```

`setup.command` always fetches the newest release's `sacred-data.zip`. A fully
self-contained offline bundle (app + data + launcher, no clone needed) can instead
be built with `scripts/make_bundle.sh`.

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
