# MISSION_CONTROL_BRIEF.md: the SACRED Mission Control build brief (2026-07-11)

You are an autonomous builder agent. Your job is to design, build, verify and polish a native
macOS desktop application called **SACRED Mission Control** over roughly one weekend, with
minimal intervention from Kilian. This brief is comprehensive on purpose: read all of it before
writing any code, then execute it end to end. Where it is silent, decide yourself in the spirit
of §1 and record the decision in your repo's DECISIONS.md.

---

## 1. Mission and vision (the paradigm; everything serves this)

Code and massive codebases are not intuitive for a human to understand. SACRED is an MSc thesis
project (Imperial College London; supervisor Dr Panagiotis Angeloudis) with nineteen-plus
experimental generations, two headline results, a zero-shot transfer arc, a surrogate-based
optimisation stack and a rigorous negative campaign, all recorded across dozens of markdown
ledgers, JSON run artefacts, checkpoints and maps. No human can feel what it all means by reading
files.

**SACRED Mission Control gives a human a visual, interactive feel for the AI being built.** It is
a playground for discovery: a user must intuitively know how to use it without instruction, and
after using it they must understand (a) what SACRED does, (b) what it can do, and (c) how it
developed generation by generation. It will be used by Kilian daily and demonstrated to his
supervisor, so **polish and factual correctness are non-negotiable**: every number shown must be
traceable to the project's ledgers, and the app must never fabricate, approximate silently, or
mix incompatible results.

The subject matter, in one paragraph (internalise this; the app must teach it): SACRED frames
contested convoy routing as a Stackelberg security game on real city road networks. A hidden
interdictor commits ambushes on edges; a deterministic router is maximally exploitable; the
optimal defence is a calibrated MIXED strategy (unpredictable routing), which max-entropy SAC
learns through adversarial training against a best-response attacker. The project proved where
this works and where it does not, measured everything against computable game-theoretic optima
(LP equilibria), extended it to fleets (multi-convoy mission-failure objectives), to zero-shot
transfer across unseen cities, to surrogate-based strategic design, and to within-episode
pattern-of-life dynamics.

## 2. Hard constraints

- **Native only: PySide6 (Qt for Python). No web stack anywhere**: no browser, no localhost
  server, no QtWebEngine, no HTML rendering paths beyond Qt's own rich-text/markdown support.
- **macOS only** (Apple Silicon M4, 24 GB RAM). No cross-platform effort.
- **Light mode**, professional and clean (this will be shown to a professor). Tab bar for the
  overarching modes + context sidebar within each tab. Keyboard AND mouse first-class
  (Cmd+1..5 switch tabs, arrow keys navigate sidebars, Space plays/pauses animations, Cmd+E
  exports the current view).
- **Own repo**: create `sacred-mission-control/` as a sibling of the `sacred/` repo
  (`/Users/kilian/Kilian/ICL/Thesis/code/sacred-mission-control/`), with its own git history,
  own `.venv`, README, and a launcher (`./run.sh`). Commit at every milestone.
- **Read-only boundary (absolute):** you may READ the `sacred/` repo
  (`/Users/kilian/Kilian/ICL/Thesis/code/sacred/`) and the thesis directory
  (`/Users/kilian/Kilian/ICL/Thesis/thesis/`), and you may IMPORT sacred's Python modules as a
  library, but you must NEVER write, commit, delete or modify anything inside either. A separate
  agent is actively working in `sacred/` and will keep committing new results while you build:
  treat sacred as a growing, occasionally mid-write data source (tolerate partially-written
  JSON with retry/skip; never assume a fixed set of generations).
- **Lazy loading**: never import torch or load checkpoints/tfevents until a view needs them;
  idle memory under ~1 GB; app start to Home under ~3 seconds. Heavy work in QThread workers,
  never on the UI thread.
- **No AI features.** Fully offline and deterministic.
- **Figure export**: every chart and map view exports to PNG and SVG at publication quality
  (matplotlib-rendered charts make this nearly free); exports land in `~/Desktop/sacred-mc-exports/`
  with descriptive filenames.

## 3. Source-of-truth data contracts (read before designing the data layer)

Scan and inventory FIRST (see §5 step 0). Orientation, to be verified against the actual files:

- **Ledgers** `sacred/experiments/*.md`: the citable numbers and narratives, one file per
  generation/arc (gen01..gen19+, plus a2/a3/a4/b4/d1/d2/d3/f3/zst_step0). Parse pragmatically
  (regex/heuristics for the result tables and verdict lines); where parsing is fragile, curate a
  small YAML/JSON "narrative index" in YOUR repo holding per-generation metadata (title, dates,
  question, verdict, headline numbers, pointer to ledger) that you author once from reading the
  ledgers. Curated metadata is allowed and encouraged; invented numbers are not: every number in
  the index must appear in the ledger it cites.
- **Run artefacts** `sacred/models/runs/<family>/*.json` + `*_ckpts/actor_ep*.pt`: per-eval
  training histories and per-eval actor checkpoints. JSON shapes differ by trainer; inspect
  them: multi-convoy fleet-route JSONs carry `history` tuples (sortie, expl, TAP, alphas, stack,
  follow, entropies, timings) plus `pol_hist` occupancy distributions and best-checkpoint
  fields; generalist JSONs (gen15/gen16) carry `history` = (sortie, train_ratio, test_ratio,
  per-OD ratios, feature weights, alphas); gen19 carries the pattern-of-life eval history and
  oracle refs. These power training-trajectory charts and drift animations.
- **Checkpoints**: actor `state_dict`s only. To load one, construct `ProtagonistSAC` with the
  right dims (`infer_node_in_dim`/`infer_edge_in_dim` from `src/agents/sac.py`), attach the
  menu/head attributes BEFORE `load_state_dict` exactly as the reference loaders do: study
  `scripts/train_multiconvoy.py` (frozen-leader load), `scripts/train_generalist.py`
  (`exact_ratio`) and `scratch/fleet_cost_probe.py`. **Era warning:** pre-fix-era checkpoints
  (gen09 and earlier, before the 2026-07-09 node-ordering fix) used a different indexing
  convention; `scratch/fleet_cost_probe.py` shows how each era must be evaluated under its own
  convention. For live demos use POST-FIX artefacts only (gen13/gen14 headline actors, gen15/
  gen16 generalists, gen19); pre-fix material is History-tab content, never a live demo.
- **Maps** `sacred/data/maps/<city>/` geojson (nodes with lat/long, edges with lengths); loader
  `src/utils/graph_utils.load_osm_graph_and_demands`; the city registry is `CITY_PATHS` in
  `scripts/train_generalist.py`. Auto-detect new city directories (Kyiv may appear).
- **Game/oracle code to reuse live** (imported read-only; all fast): `src/baselines/
  interdiction_oracle.py` (single-convoy games, LP equilibria, vulnerability bands, frontier),
  `src/baselines/multiconvoy_oracle.py` (occupancies, LP, greedy BR), `src/baselines/
  multiconvoy_planners.py` (ALNS, classical baselines), `src/baselines/fp_dynamics.py`,
  `src/envs/multiconvoy_interdiction.py` (`make_multiconvoy_env`), and the gen19 game logic in
  `scripts/train_b1lite1.py`. LP solves are milliseconds at K=1-2: sliders can re-solve live.
- **Campaign era** (gen01-07): tfevents under `sacred/logs/tb_runs/` (read with TensorBoard's
  `event_accumulator`), existing figures `sacred/scratch/*.png` and `dynassign_demo.gif`.
- **Git history** of sacred: commit messages are result summaries; `git log` (read-only) is a
  ready-made project timeline.
- **Documents**: all `*.md` under `sacred/` and `/Users/kilian/Kilian/ICL/Thesis/thesis/`.
- **Key context documents you should read yourself before building** (they teach the story the
  app must tell): `sacred/HANDOVER.md`, `sacred/THESIS_STORYLINE.md`, `sacred/SACRED_PROGRESS.md`,
  `sacred/CRITIQUE_EXPANSION.md`, `sacred/NEXT_STEPS_11-07-26.md`, and the gen08/gen09/gen13/
  gen14/gen15/gen16/gen19 ledgers.

## 4. Correctness rules (the professor-proof bar)

1. Every displayed headline number carries provenance: a small caption or tooltip naming the
   ledger it comes from (e.g. "gen14: 0.256, 95% CI [0.246, 0.266]").
2. Live simulations CONVERGE to citable numbers; when a demo shows a running estimate, show the
   ledger's banked value alongside so agreement is visible, never substituted.
3. Never mix pre-fix and post-fix era results in one visual (the project's own hard rule);
   history views label eras explicitly.
4. Missing artefact = honest "not available for this generation" placeholder, never a fabricated
   or silently-recomputed stand-in.
5. Any number you compute live (oracle solves, rollout estimates) is labelled "computed live";
   any number from a ledger is labelled with its source. The two must never be visually
   confusable.
6. Randomness is seeded and the seed is visible wherever a demo samples.

## 5. Build plan (milestones; each ends demo-able, committed, and screenshotted)

**Step 0: inventory.** Scan both repos; write `DATA_MAP.md` in your repo documenting every
artefact class found (ledgers, JSONs, checkpoints, maps, tfevents, figures), what loads
successfully, which generations are demo-able live vs chart-only vs text-only. Author the
narrative index (§3) for the History tab. This document drives scope honesty for everything
after.

**M1: skeleton + Documents + History.** App shell (tabs, sidebar pattern, light theme,
navigation, shortcuts); the Documents tab (markdown reader: file tree over both roots, Qt-native
markdown rendering, internal links between files navigable, back/forward, full-text search); the
History tab first version (time-ordered generation sidebar from the narrative index; per-
generation cards: question, dates, verdict, headline numbers, era badge, charts from run JSONs
where available, figures where they exist, ledger link into the Documents tab; the three pivots
as chapter dividers: congestion -> interdiction -> multi-convoy -> expansion).

**M2: the map engine + oracle-level Playground.** Interactive city map view (QGraphicsScene:
pan/zoom, edges drawn from geojson, vulnerability heat colouring, route menus highlighted on
hover/select, OD markers); instance picker sidebar (city, OD from screened presets, K, N, band);
live oracle layer: equilibrium mixtures drawn as route-thickness/opacity, loss_det vs loss_mixed
readouts, sliders (K, band) that re-solve the LP live and re-draw. Animated sortie loop at
oracle level: sample defender route(s) from a chosen strategy, sample/commit the attacker, animate
the convoy(s) along the route, flash interceptions, accumulate the running interception /
mission-failure rate toward the anchors.

**M3: policies + the full strategy roster + play-yourself.** Torch loading (lazy, worker
threads): the post-fix headline actors and the gen15/gen16 generalists join the strategy roster.
Playground roster (defender): shortest-path, uniform, cost-calibrated mixture, vanilla SAC,
ALNS plan, equilibrium mixture, SACRED (checkpoint picker), and for gen19 the history-aware
policy vs its pattern-of-life adversary. Attacker roster: oracle best response, equilibrium
attacker, smooth-FP, pattern-of-life (quantal response over a window). Play-yourself modes: (a)
you route the convoy(s) by clicking routes, the committed interdictor punishes predictability;
(b) you place the ambush against a chosen defender and discover why mixing beats you. Score
panels compare the human against the banked strategies.

**M4: Objectives tab + Home.** Six exhibit panels, each pairing the verbatim objective text
(from the literature review; the exact five objectives are quoted in `sacred/THESIS_STORYLINE.md`
"The promise" section) with an interactive exhibit:
- **Obj 1 (zero-sum game)**: the game made tangible: defender-mixture sliders vs live
  exploitability readout; the saddle; why deterministic = 100% intercepted.
- **Obj 2 (simulation environment)**: the city pipeline and env itself: pick any city, see the
  extraction (arterial network), threat map, instance anatomy.
- **Obj 3 (SAC + ATLA + ERB)**: training dynamics replayed: TAP trajectories with best-checkpoint
  markers and the disclosed drift, alpha/entropy traces, FP cycling animation; ERB/demonstration
  bootstrapping panels as artefacts allow.
- **Obj 4 (SBO)**: the design-space explorer: scatter of placement x fleet designs (predicted vs
  true), click a design to see it on the map, and RUN the acquisition loop live (oracle-cheap)
  racing random search to the optimum (D1); the D3 policy-vs-equilibrium target comparison.
- **Obj 5 (evaluation vs baselines)**: the ladder raced: same map, each strategy runs its sorties
  side by side, converging to its ladder value (shortest > vanilla/ALNS > SACRED > equilibrium);
  the K/N disruption sweep curves (gen12).
- **ZST (the aim's promise)**: pick a held-out city, watch the frozen generalist route it
  zero-shot vs a random-init net; the transfer ladder (held-out OD -> held-out city -> the
  measured single-source failure that motivated multi-city training).
**Home**: the one-screen pitch: what SACRED is in three sentences, a hero animation (SACRED
mixing routes on Kaliningrad while shortest-path is ambushed), the two headline ladders as clean
visuals, and four large entry buttons into Playground / Objectives / History / Documents. This is
the opening screen of the supervisor demo.

**M5: polish + verification + self-review.** Consistent typography/spacing/palette
(colour-blind-safe; light); empty/loading/error states everywhere; export on every view;
keyboard audit; performance audit (lazy paths verified, no UI-thread stalls); parser unit tests
+ a scripted smoke that opens every tab/exhibit programmatically and screenshots each; then a
**hostile self-review against this brief**: correctness of every displayed number vs its ledger,
intuitiveness (could a stranger use it unaided?), polish, the §4 rules: write the findings list,
fix them, iterate once. Finish: README (install/run in two commands), HANDOVER.md for your repo,
final commit and version tag.

## 6. Progress protocol with Kilian

- Work autonomously. Ask blocking questions only if the brief is genuinely ambiguous on
  something you cannot decide (expected: none). No multiple-choice prompts; prose.
- At each milestone: capture real screenshots of the running app programmatically
  (`QWidget.grab().save(...)` or macOS `screencapture -l <windowid>`; no user needed) and SEND
  the PNGs to Kilian with a two-line status. He is on his laptop intermittently; do not wait for
  a reply: continue, and fold in his feedback whenever it arrives.
- If an artefact you hoped to demo turns out unusable, degrade the feature gracefully, note it
  in DATA_MAP.md, and move on: scope honesty beats feature count.
- Respect the machine: the sacred implementer agent may be training (it owns the cores during
  its batches); your build work is light, but run any heavy verification with modest thread
  counts and never launch anything from the sacred repo.

## 7. Definition of done

A stranger sits down at the app with no instructions. Within ten minutes they have: watched a
deterministic convoy get ambushed 100% of the time and a SACRED convoy slip through; placed an
ambush themselves and lost to the mixed strategy; seen the policy route a city it never trained
on; watched the SBO loop find an optimal base placement; scrolled the project's history from the
first failed congestion experiments to the latest generation and understood the pivots; opened a
ledger in the Documents tab to check a number they saw on a chart, and found it matched, with
the provenance caption already telling them where to look. Every screen would make Dr Angeloudis
trust the project more, not less.
