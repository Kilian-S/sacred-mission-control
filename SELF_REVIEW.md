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

## Round 2 findings (independent reviewer)

See the appended list below; each item marked with its resolution.
