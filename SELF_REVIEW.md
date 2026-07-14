# SELF_REVIEW.md: the hostile review against the brief (M5, 2026-07-11)

Round 1 = my own audit; round 2 = an independent fresh-eyes reviewer agent run against
the brief (findings appended when received). Status: fixed items marked [FIXED].

## Round 1 findings

1. [FIXED] Watch mode showed banked anchors even when the picker was not at the banked
   cell, without the mismatch warning the M2 version had. Re-added the explicit red note.
2. [FIXED] Space did not reach the Objectives exhibits when a sidebar child had focus
   (QListWidget consumed the key). Replaced keyPressEvent with a WidgetWithChildrenShortcut.
3. [FIXED] The Obj-5 race drew the vanilla ledger row from a hardcoded 0.526 in code;
   now read from `data/exhibits.yaml` (provenance-tested).
4. [FIXED] The duel's running metric is the gen19 estimator (expected loss under each
   sortie's committed ambush); the label now says so instead of implying a sampled rate.
5. [FIXED] Cmd+E exported only a pixmap grab; the brief requires every chart to export
   PNG AND SVG at publication quality. Cmd+E now additionally exports every visible
   matplotlib chart in the current view as PNG+SVG.
6. [FIXED] Home hero used the soft-band 35-159 single-convoy game (interception 0.55 vs
   0.13); the brief's definition of done wants the deterministic convoy ambushed 100% of
   the time, which is the 33-71 hard game (1.000 vs 0.167). Switched.
7. [VERIFIED] K=2 live re-solve: 1.7 s and reproduces the gen12 ledger cell exactly
   (eq 0.412, ALNS/loss_det 0.866). K=3 carries a UI warning (~20-30 s).
8. [VERIFIED] Palette passes the dataviz six-checks validator (worst adjacent CVD dE 24.2);
   the three sub-3:1 contrast slots are relieved by direct value labels on every chart.
9. [ACCEPTED] Campaign-era tfevents charts not wired (honest placeholders + figures +
   verbatim quotes instead); recorded in HANDOVER as the top candidate next step.
10. [ACCEPTED] The smoke script is flaky when its stdout is piped through grep;
    documented (write to a file). Root cause not chased.
11. [VERIFIED] Performance audit: start-to-Home 1.79 s (brief: under ~3 s); idle RSS
    318 MB after load (brief: under ~1 GB); torch only imported on first roster load;
    no UI-thread stalls observed in the smoke (all solves/loads in QThreadPool workers).

## Round 2 findings (independent fresh-eyes reviewer, run against the brief)

16 findings, three demo-breaking. Resolutions:

1. [FIXED] Home forced horizontal scrolling (long entry-button text set a ~1600 px minimum
   width, clipping the tagline, ladder values and the Documents button). Subtitles shortened,
   columns stretch-shared.
   0. [FIXED, pre-round] Home's hero caption said "35-159" while showing 33-71's numbers
   (caught by the reviewer's first pass before it was interrupted).
2. [FIXED] Stale worker results could be applied after an instance rebuild in three places
   (watch policy load, watch ALNS, duel policy load): each callback now carries the instance
   it started on and discards mismatches (the pattern history/obj2 already used).
3. [FIXED] Duel controls were silently dead while the gen19 policy loaded (the smoke even
   captured byte-identical before/after shots). Play/batch/combo now disable during the load
   with an explicit "still loading" message, and re-enable on arrival.
4. [FIXED] The duel's "Best fixed route" played argmin over the worst case (0.617) rather
   than the static_det anchor's definition (0.613, min stationary loss vs its own softmax BR);
   the running mean would have converged visibly above its own anchor line, breaching §4.2.
   Now computes the anchor's own argmin.
5. [FIXED] The banked gen19 card showed at any N/K on 35-159; now gated on N=3 K=1 as banked.
6. [FIXED] Obj-3 era badge could mislabel a late-arriving family payload (pre-fix curves
   under a POST-FIX badge); callbacks now verify the combo has not moved.
7. [FIXED] Interdiction charts drew a hardcoded shortest_path=1.0 reference; now read the
   arm's own expl_tap from the run JSON.
8. [FIXED] Obj-5 race: seeds now printed in the caption (§4.6) and the banked gen14 CI
   annotated beside the live SACRED line (§4.2).
9. [FIXED] K=3 with N>=4 would materialise a multi-GB objective matrix; the picker now
   refuses that region with an explanation (and the K warning says so).
10. [FIXED] Ambush score card claimed "best possible single ambush" while K!=1; now clears
    and asks for K=1.
11. [FIXED] Blank panes before first interaction (ZST maps, Obj-4 race) now carry
    instructions.
12. [FIXED] Duel card headers wrap (the banked header lost its closing bracket at 330 px).
13. [FIXED] ZST result names the OD it scored and the picker is disabled during the eval.
14. [FIXED] Obj-4 race x-axis now starts at the shared 8-evaluation seed budget.
15. [FIXED] Home's single-convoy ladder caption now cites gen14's n=10 CI (0.310
    [0.275, 0.345]) beside the pooled gen10-SC ladder so the two ledger-true numbers cannot
    read as a discrepancy.
16. [FIXED] Cosmetics: "(hard)" preset label renamed (collided with the hard-interception
    toggle); map panes no longer show scrollbars; the duel batch runs in a worker (no ~1-2 s
    UI freeze); History's "Open ledger" now scrolls to the first quoted line.

Reviewer's "convincingly right" list (provenance discipline enforced by tests; live maths
matches the banked record exactly; era hygiene structural; honest degradation throughout)
retained unchanged; none of the fixes touched those paths' behaviour.

## Round 3 (2026-07-12): second independent review, humanist/visual audit + fix round

Findings against the brief and against the humanist/visual principles, all implemented
the same day (commits 71f89b8..HEAD). Ranked as found:

1. [FIXED, demo-critical] The documented Cmd shortcuts were bound to the CONTROL key:
   Qt on macOS maps "Meta" to Control and "Ctrl" to Command. Cmd+1..5/Cmd+E/Cmd+[]
   now work as written; the standard Back/Forward keys stay unbound so Cmd+Left/Right
   keep moving the text cursor in Documents.
2. [FIXED, staleness] The sacred agent had banked gen20-23, D3-on-Gdansk, the whole-Kyiv
   row and the K/N rows since handover; several on-screen verdicts were behind or wrong
   (Kyiv "no banked results"; Obj-3's ERB wording now contradicted by gen23). All folded
   in with verbatim provenance; Kyiv became a live Playground city (measured 0.6 s
   solves); the roster gained gen20 (reproduces its banked 0.355 exactly), gen22, and
   gen21 explicitly labelled as the control.
3. [FIXED, visual truth] Interceptions did not happen at the ambush: the duel killed
   convoys at the FOB after driving through the ambush edge; watch/home stopped dots at
   edge-count fractions that diverge from the drawn geometry; mark_lost repainted every
   victim in the shortest-path red, destroying the red-vs-blue identity on Home.
   Convoys now die ON the committed edge (MapView.fraction_of_edge, monotonicity-tested),
   the duel's ambush springs at the interception moment, and destroyed convoys keep
   their colour and gain a cross.
4. [FIXED, reliability root cause] workers.py used autoDelete + discarded worker
   references, so the pool destroyed the signal sender the moment run() returned and a
   QUEUED finished/failed emission was dropped whenever the UI thread was busy. This is
   the probable root cause of round 1's "smoke is flaky when piped" (accepted then,
   root cause not chased) and round 2's byte-identical duel shots. A module registry now
   holds every worker until delivery; regression tests added (tests/test_workers.py).
5. [ADDED, the two visual gaps that mattered most] The duel shows the interdictor's
   ANTICIPATION as an orange glow (absolute-probability opacity; "fly where the glow is
   not"), and Watch shows the current defender's route mixture beside the LP
   equilibrium's, so the central claim (SACRED sits on the equilibrium) is visible.
6. [ADDED, brief-compliance] Cmd+E now exports every visible map view as true vector
   SVG + 3x PNG (§2 required PNG AND SVG for map views); Obj-4's "click a design to see
   it on the map" line is implemented (live-solved design shown as a game); campaign
   generations draw their tfevents evidence (the ~0.91 plateau) beside the verbatim
   quotes.
7. [ADDED, orientation] Home legend for the provenance colour language; History banner
   for uncurated run families on disk; Obj-3 loading/error states; the History gif
   scales (QMovie.scaledSize is invalid before the first frame); city name + scale bar +
   arterial/minor street weights on every map.
8. [FIXED, self-caught in this round's re-review] drawForeground used resetTransform,
   which broke composition under the 3x export painter (now drawn in scene
   coordinates); Obj-4's design map was a blank pane before the first pick (hidden until
   then); Watch's 500-sortie batch ran on the UI thread (worker + guards now, like the
   duel); the tb series cap leaked past 6.
9. [VERIFIED] Suite 28 green in ~2 s; SMC_SLOW_TESTS=1 adds the torch anchor pins
   (gen14 seed 0 in the banked per-seed set; gen20 seed 0 = 0.355 exactly); the smoke
   walks all 27 states with ready-predicate waits and, for the first time, captures the
   COMPLETED zero-shot evaluation (both Gdansk maps + live-labelled ratios).
10. [ACCEPTED] matplotlib's "constrained_layout collapsed to zero" warning can appear
    for charts first drawn at zero height inside collapsed scroll panes; cosmetic.
    Obj-1's attacker-options bars remain index-labelled (candidate next step in
    HANDOVER).

## Round 4 (2026-07-13): the v1.1 fold-in of sacred's Blocks A+B

Driver: the sacred agent completed the claims-defence programme (gen24/gen25, A2-A8,
B1/B3/B4), three results of which REFRAME standing claims. Alignment fixes applied:

1. [FIXED] D3-Gdansk still led with the retired 0.109 headline; now per-seed
   (0.109/0.443/0.433) with the A5 reliability disclosure everywhere it appears.
2. [FIXED] The ZST act's copy ("map-conditioned", "adversarial training is causal for
   transfer") replaced with the two-regime synthesis and the A2/A3 wording rule
   ("geometry-informed, threat-robust hedge"); gen22's Istanbul PASS reworded per A7.
3. [FIXED] Obj-4's "simultaneous" now carries B1's honest form (joint = safe default,
   0-19% actor-contingent).
4. [VERIFIED] New roster arms reproduce their ledgers exactly: gen25 vanilla 2.351 and
   DR 2.056 (select-on-train), gen24 distilled 1.5268 per-seed (val-stopped selection
   scored as a centred TAP window {100, 200}: discovered by matching valstop.json, and
   recorded in DECISIONS.md); the objective spectrum reproduces B3's law (1.83 /
   degenerate 0-0 at P(>=2) N=3 / 1.29 at N=5); the intel-error path identity-checks
   against the normal forward pass.
5. [FIXED, found by the compare-mode fork] Watch's running label kept stale text across
   instance rebuilds, and its readout nouns assumed the mission objective. Deeper find:
   the sampled running estimate itself used mission semantics under EVERY objective, so
   under linear/threshold it would NOT have converged to the exact value beside it
   (§4.2). The engine now accumulates the realised objective value per family, with a
   convergence regression test for the linear objective.
6. [ACCEPTED] The compare panels and the attacker share orange for the DR control
   (validated-palette ninth-series rule: no invented hues; identity via panel labels
   and glyphs; DECISIONS.md item 12).
7. Smoke extended to 32 shots (compare mode, objective spectrum); all inspected.

## Round 5 (2026-07-14): the humanist redesign (v2.0) + stranger-test audit

Kilian's v1.1 critique: too much technical jargon, ledger-note reliance, and a
"Windows XP" Playground; the definition of done became "a stranger with a high-school
education understands each screen in thirty seconds." Rebuilt per REDESIGN.md.

Built: a single-source lexicon (one metric phrase "chance the mission fails", human
names for every strategy/enemy/scenario/objective, percentages on human surfaces); a
humanist widget kit (hero numbers, goalpost bars, outcome strips, map legends, a
collapsed "From the record" drawer that keeps every ledger quote one click away); a
side-by-side planner-vs-SACRED Home hero; a four-card Playground landing with a shared
scenario bar, an advanced "Change the rules" drawer, and three-step coach tutorials;
story-first Objectives (map-based base-siting, battery-bar transfer decay, one-chart
training default); a plain-words lead on every History card; larger, 150%-line-height
Documents rendering (no .md edits); and the bug fixes (map pan artefacts, zoom chip,
Objectives scroll, the exp-underflow oracle warning, capitalisation).

Stranger-test audit against §0 of REDESIGN.md, every screen walked against fresh
screenshots:

| screen | the one question | verdict |
|---|---|---|
| Home | what is this, what is it better at? | PASS: side-by-side hero, 70% vs 25% worst-case tallies, "SACRED has no habit" |
| Playground landing | what can I do? | PASS: four plain cards, one line each |
| Watch | who defends, who attacks, who wins? | PASS: human pickers, 21% hero, goalpost bar, outcome strip |
| You defend | what do I do, how am I doing? | PASS: "click a road", 5.3% hero, "where the enemy is looking" glow |
| You attack | why can't I beat the mix? | PASS: "62% of perfect play... the mix made you indifferent" |
| Compare | which is best, by how much? | PASS: four labelled panels, big %, one shared chart |
| Objectives 1-6 | promised X, delivered X? | PASS: plain headlines, one demo each, quotes collapsed |
| History | how did it get here? | PASS: "What happened" plain lead, plain pills, verbatim record below |
| Documents | where is the evidence? | PASS: comfortable typography, searchable, unedited md |

Fixes applied during the audit: Home provenance legend wrapped (was forcing horizontal
scroll); coach "Next" button made visible and dismissed on mode change; compare/Obj5
chart axes plainened ("run", "share of missions that failed"); a matplotlib arrow glyph
removed; a doubled "computed live" caption fixed; smoke updated to the open_mode() API
with coach suppression. 34 tests green; smoke 32 shots, exit 0, no glyph/crash warnings.

The provenance contract is unchanged: every number still carries its ledger citation or
"computed live" mark, verified by the same tests; the redesign moved proof one click
away, it did not remove it.
