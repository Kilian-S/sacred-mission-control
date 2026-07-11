# DATA_MAP.md: every artefact class in the sacred repo, and what this app does with it

Compiled 2026-07-11 (Step 0 of MISSION_CONTROL_BRIEF.md). The sacred repo is read-only and
GROWING: a separate agent commits new results while this app runs. Everything below is therefore
treated as a snapshot; all loaders tolerate missing/partial files and auto-detect new
generations, cities and run directories.

Roots:
- `SACRED = /Users/kilian/Kilian/ICL/Thesis/code/sacred`
- `THESIS = /Users/kilian/Kilian/ICL/Thesis/thesis`

## 1. Ledgers (`SACRED/experiments/*.md`): the citable numbers

One markdown ledger per generation/arc. 19 generations + 9 expansion/side ledgers as of
2026-07-11 (gen01..gen19, a2/a3/a4/b4/d1/d2/d3/f3/zst_step0). Formats vary (result tables,
verdict headers, blockquotes); parsing is heuristic, so the History tab is driven by the
CURATED narrative index (`data/narrative_index.yaml`) authored from reading every ledger.
Provenance rule: every number string in the index must appear verbatim in the ledger it cites
(enforced by `tests/test_narrative_index.py`).

Era rule (the project's own hard rule): the 2026-07-09 node-ordering fix (SHA `e9acb56`)
divides everything into pre-fix (gen01-gen09 + the banked B2-P3/gen09 numbers) and post-fix
(gen10 onward). Never mixed in one visual; live demos use post-fix artefacts only.

## 2. Run artefacts (`SACRED/models/runs/`)

### JSON shapes (decoded from the writing scripts)

| writer | families | history tuple |
|---|---|---|
| `scripts/train_multiconvoy.py` | gen09, gen10 (mc/mc2/van), gen11, gen12, gen13, gen14 (mc/van), gen17, gen18 | 11-tuple `(sortie, expl, expl_tap, alpha_leader, alpha_foll, stack_rate, follow_rate, H_lead, H_foll, t_train_s, t_eval_s)` |
| `scripts/train_interdiction.py` | gen08_interdiction_I3 (all), gen10 B2P3, gen14 sc, zst_step0 source_retrain | 7-tuple `(sortie, expl_policy, expl_tap, expl_window, expl_avg, alpha, policy_entropy)` inside `arms.{vanilla,sacred}` |
| `scripts/train_generalist.py` | gen15, gen16 | 7-tuple `(sortie, train_ratio, test_ratio, test_ratios_list, route_feat_w, alpha_leader, alpha_foll)` |
| `scripts/train_b1lite1.py` | gen19 | 3-tuple `(sortie_k, sacred_eval_loss, 0.0)` + `refs{v_eq,eq,iid_eq,static_det,history_opt}` |

Multi-convoy result dicts also carry `pol_hist` (per-eval occupancy distributions, len = #evals+1,
each len = #occupancies e.g. 364), `best_tap`/`best_tap_sortie`, `occ_dist`, `tail_*`.
Interdiction JSONs carry `frontier` (list of `[cost, value]` points), `route_costs`,
`equilibrium_defender`, `loss_det`, `loss_mixed`, per-arm readings.

### Actor checkpoints (`*_ckpts/actor_ep{N}.pt`, actor-only state_dicts, ~676 KB)

| family | checkpoints | era | app use |
|---|---|---|---|
| gen09_multiconvoy headline_seed{0,1,2} | 12 each (ep100..1200) | PRE-fix | History charts only (legacy indexing convention) |
| gen10_postfix mc/mc2 | 12/24 each | post-fix | drift charts |
| gen11_menuhead {B,Bp,C,D,E,Ep}_seed* | 12 each x 18 | post-fix | charts |
| gen12_sweeps hl_N3K1_seed* | 12 each | post-fix | charts |
| gen13_lock seed{0,1,2} | 12 each | post-fix | LIVE roster (multi-convoy headline config) |
| gen14_evidence mc_seed{0..9} | 12 each | post-fix | LIVE roster (headline actors, n=10) |
| gen15_generalist seed{0,1,2} | 24 each (ep500..12000) | post-fix | LIVE roster (generalist, Kaliningrad) |
| gen16_multicity seed{0,1,2} | 24 each | post-fix | LIVE roster (multi-city generalist, ZST demos) |
| gen17_lastiterate seed{0,1,2} | 24 each | post-fix | drift charts |
| gen19_b1lite1 seed{0,1,2} | 16 each (ep520..8000) | post-fix | LIVE roster (history-aware policy) |
| gen18_learnedfollower | NONE | post-fix | charts from JSON only |
| gen08_interdiction_I3 | NONE | pre-fix | charts from JSON only |
| zst_step0 `source_actor_3371.pt` | 1 (atypical name) | post-fix | chart/text |
| br_gate (campaign era) | `role/actor.pt` + snapshots | campaign | not loaded (11/13-dim era) |

Loading recipe (from `scripts/train_generalist.py`, `scripts/train_b1lite1.py`,
`scratch/fleet_cost_probe.py`): construct `ProtagonistSAC(node_in_dim=14, edge_in_dim=4 or 5, hidden_dim=64,
num_layers=2, heads=4, device="cpu")`, attach `menu_routes` (+ `follow_w`/`route_feat_w`/`route_bias`
Parameters IF the checkpoint state contains those keys, with `route_feat_w` width 2 for
gen13/14/15/16 and 3 for gen19) BEFORE `load_state_dict`, use `infer_node_in_dim`/`infer_edge_in_dim`
to auto-detect widths, slice features with `_clip_x`/`_clip_ea`, index nodes with `node_index_map`
(post-fix) or dict insertion order (pre-fix legacy, per `fleet_cost_probe.py`).

### Top-level JSONs

`d1_sbo_loop.json` (SBO acquisition curves, 20 repeats), `d2_hardening.json`,
`d3_composite.json` (522 designs, surrogate curves), `a3_amortisation.json`,
`correlated_interception.json` (B4 rho curves), `fleet_cost_probe.json`,
`sbo_placement_demo.json` (F3: 450 designs with rows), `zst_step0.json`,
`a2_graph_transfer_original.json`; `experiments/gen04_gate.json`.

## 3. Maps (`SACRED/data/maps/`)

GeoJSON FeatureCollections, coordinates `[lon, lat]`; nodes = Points keyed `osmid`,
edges = LineStrings with `u`, `v`, `length` (metres):

| city | nodes | edges | notes |
|---|---|---|---|
| kaliningrad_simplified_30m | 290 | 706 | THE training graph (`_DEFAULT_NODES/_EDGES`); has `length` |
| gdansk | 356 | 638 | gen16 held-out city |
| east_london | 564 | 1169 | gen16 train |
| istanbul | 1266 | 2222 | gen16 train |
| kaliningrad_original | 624 | 1273 | A2 held-out graph; NO `length` property (loader default 100 m) |
| kaliningrad_original_curvy | 624 | 1273 | display geometry variant |
| kyiv | 6083 | 10861 | on disk, NOT in CITY_PATHS; not oracle-screened; map-view only |

`koenigsberg1.json` = 1000 synthetic delivery tasks (demand seeds), not a graph.
Loader: `src/utils/graph_utils.load_osm_graph_and_demands(nodes, edges, tasks) -> (nodes_dict,
edges_list)`; game graph = `nx.Graph` with edge attr `w` = length/100 (min 1.0), node ids STRINGS.
Registry: `CITY_PATHS` in `scripts/train_generalist.py` (kaliningrad, gdansk, east_london,
istanbul). The app auto-detects new `data/maps/<city>/` directories.

## 4. Game/oracle code imported live (no torch, milliseconds at K=1-2)

- `src/baselines/interdiction_oracle.py`: `build_route_set` (edge-disjoint + k-shortest),
  `build_interdiction_game(G,s,t,K,k_extra,intercept_fn)`, `solve` -> value/loss_det/
  defender_strategy/attacker_strategy, `best_response_attacker`, `length_band_vulnerability`
  (+ `norm_edges` for absolute norm), `survival_intercept_fn`, `cost_constrained_value` (frontier).
- `src/baselines/multiconvoy_oracle.py`: `occupancies`, `objective_matrix`, `solve_multiconvoy`,
  `best_response_attacker_multi`, `greedy_br_attacker` (K>=4 matrix-free), `objective_value(rho=)`.
- `src/baselines/multiconvoy_planners.py`: `alns_fleet_planner`, `shortest_path_fleet`,
  `classical_baselines` (incl. alns_forced_stack).
- `src/baselines/fp_dynamics.py`: `smooth_fp_probs`, `sample_smooth_iset`.
- `src/envs/multiconvoy_interdiction.py`: `make_multiconvoy_env` (torch only touched when
  `menu_select=True`).
- `scripts/train_b1lite1.py`: importable pure functions `stacked_L`, `softmax_br`, `oracle_refs`
  (static_det / iid_eq / history_opt via value iteration), `route_feats`, `eval_policy`.

Canonical screened instances: 35-159 k8 band(0.15,0.95) N=3 K=1 (post-fix headline + gen19),
62-97 k8 (pre-fix headline, History only), 33-71 k8 (single-convoy headline), 110-135 (B2-S/ZST-0
target). Generalist screened OD pools with per-OD eq/loss_det refs live in the gen15/gen16 JSONs
(train_ods/test_ods/test_refs) and are reused as Playground presets.

## 5. Campaign era (gen01-07)

- tfevents: `SACRED/logs/tb_runs/` (~30 MB, 76 run dirs; nested per-seed dirs for gen01-06 +
  br_gate). 32 scalar tags (Episode/*, Loss/*, Value/Protagonist_Q_Spread, Eval/gap_*...).
  Read with TensorBoard `event_accumulator`, lazily, in workers.
- Figures: `scratch/dynassign_demo.gif` (1.9 MB animated demo), `scratch/chokepoints.png`,
  `scratch/hybrid_geometry*.png`, `scratch/assignment_geometry.png`, `scratch/dynassign_geometry.png`,
  `assets/kaliningrad_{consolidated_compare,demand_heatmap,filter_compare}.png`,
  `scratch/mapgen/*_tolsweep.png`, `scratch/oracle_scaling_output_v2.txt` (the current scaling table).

## 6. Documents

All `*.md` under `SACRED/` (top-level strategy docs + experiments/) and under `THESIS/`.
Key: HANDOVER.md (banner stack), THESIS_STORYLINE.md (the objectives verbatim, "The promise"),
SACRED_PROGRESS.md (chronicle entries 1-18), REDESIGN_INTERDICTION.md, CRITIQUE*.md (4 files),
NEXT_STEPS_11-07-26.md, ROADMAP.md, SYSTEM.md. Git history of sacred = ready-made timeline
(read-only `git -C SACRED log`).

## 7. Demo-ability verdict (scope honesty; drives what each tab offers)

| capability | status |
|---|---|
| LP oracle live solves (single + multi-convoy, K=1-3) | LIVE (ms; sliders re-solve) |
| ALNS plan for an instance | LIVE (~seconds, worker thread) |
| Sortie animation vs any oracle-level strategy | LIVE |
| gen13/gen14 headline actors (35-159) | LIVE (post-fix, ckpts on disk) |
| gen15/gen16 generalists (any screened OD; ZST on Gdansk etc.) | LIVE |
| gen19 history-aware policy + pattern-of-life adversary | LIVE (needs [R,3] route_feat_w) |
| gen18 learned follower | charts only (no ckpts) |
| gen08 single-convoy B2-P3 | charts only (no ckpts; pre-fix anyway) |
| Single-convoy LIVE demos | oracle-level only (trained SC actors: only zst_step0's one actor, walk-mode; treated as chart-only) |
| gen01-07 campaign | text + tfevents charts + existing figures |
| Kyiv | map display only, labelled unscreened |
| gen09/gen10/gen11/gen12/gen17 checkpoint drift | charts from JSONs (pol_hist/history) |
