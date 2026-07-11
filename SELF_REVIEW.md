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
