# REDESIGN.md: the humanist redesign (v2.0 plan, 2026-07-14)

Commissioned by Kilian after v1.1.0. The app is factually bulletproof but talks like a
ledger. This plan turns it into something a stranger with a high-school education
understands immediately, the way a keynote communicates a product: plain words first,
one idea per screen, and the advantage over the competition shown, not stated.

**The standing rules do NOT change**: every ledger number keeps its citation, every live
number keeps its "computed live" mark, eras are never mixed, randomness stays seeded and
visible, light mode, the validated palette, no edits to any file in sacred/ or thesis/.
What changes is the LANGUAGE ON TOP and the VISUAL PRESENTATION: proof moves one click
away instead of leading.

## 0. Definition of done: the stranger test

A person who has never heard of SACRED sits down at each screen and, within thirty
seconds and without help, can answer the screen's one question:

| screen | the one question they must be able to answer |
|---|---|
| Home | "What is this project, and what is it better at?" |
| Playground · Watch | "Who is defending, who is attacking, and who is winning?" |
| Playground · You defend | "What am I supposed to do, and how well am I doing?" |
| Playground · You attack | "Why can't I beat the mixed strategy?" |
| Playground · Compare | "Which of these four is best, and by how much?" |
| Objectives (each) | "What was promised, and was it delivered?" |
| History | "How did the project get here?" |
| Documents | "Where is the original evidence?" |

Every jargon term visible WITHOUT clicking must pass: "would a newspaper use this
word?" Codes, metric names, generation numbers and ledger tables live in fine print
and expanders, never in titles.

## 1. The language system (the single biggest change)

### 1.1 One metric, one phrase, everywhere

All variants ("mission-failure exploitability", "interception exploitability",
"expl_TAP", "worst-case mission failure", "ratio to equilibrium") collapse into ONE
consistent phrase pair used on every screen:

- **The number**: "**chance the mission fails**" (0-100%, shown as a percentage, not
  a 0.xxx decimal, wherever a human reads it; charts may keep the 0-1 axis with a %
  formatter). "Mission fails" = at least one convoy is lost (the headline rule); the
  objective selector can change the rule and the phrase adapts ("average share of
  convoys lost", "chance of losing two or more").
- **The condition**: "**against an enemy who has learned your habits**" (this is what
  "worst case / best response / exploitability" means and it is said in exactly these
  words, once per screen, as a subtitle).
- Ratios ("1.68x equilibrium") become "**x% above the proven optimum**" or are shown
  as positions between two labelled goalposts (see §3.4).

### 1.2 The canonical vocabulary (old → new; old form allowed only in fine print)

| today | everywhere visible |
|---|---|
| Kaliningrad 35-159 / "THE post-fix headline instance" | **"The proving ground"** (Kaliningrad; fine print: `35-159 · N=3 K=1 · band 0.15-0.95`) |
| 62-97 pre-fix instance | "The old proving ground (earlier era)" |
| 33-71 single-convoy instance | "The lone-convoy run" |
| 110-135 / B2-S | "The three-corridor crossing" |
| gen15 test ODs | "Unseen crossing 1…6 (Kaliningrad)" |
| gen16 test ODs | "Gdansk crossing 1…6 — a city the AI never saw" |
| shortest path / deterministic stack | "Always the fastest road (predictable)" |
| uniform mixture / uncalibrated noise | "Pick a road at random" |
| independent uniform | "Every convoy rolls its own dice" |
| best cost-calibrated mixture (softmax T=…) | "Random, but favouring fast roads" |
| equilibrium mixture (LP minimax) | "The proven-optimal mix" |
| ALNS | "The professional planner" (fine print: ALNS, reaches the deterministic optimum) |
| SACRED gen13/14/16 | "SACRED" (+ scenario note: "trained here" / "first time on this map") |
| vanilla generalist | "AI trained with no enemy" |
| gen24 distilled | "AI taught by copying the maths (needs the answer key)" |
| gen25 DR | "AI trained against random attacks" |
| random-init | "An untrained AI" |
| oracle best response (committed) | "The enemy knows your strategy (worst case)" |
| equilibrium attacker | "The perfect ambusher" |
| pattern-of-life (softmax BR, w, tau) | "Watches your last few runs, then strikes" |
| committed BR to cumulative play | "Studies your whole history, then commits" |
| Mission: P(≥1 lost) | "Any loss means failure (the headline rule)" |
| Threshold: P(≥2 lost) | "Failure means losing two or more" |
| Risk-neutral: expected fraction | "Count average losses" |
| loss_det | "the best any predictable plan can do" |
| equilibrium / loss_mixed | "the proven optimum" |
| era badges PRE-FIX/POST-FIX | keep badges, add plain tooltip: "before/after a bug fix on 9 July; results from the two are never compared" |
| BASE / FOB markers | "Base" / "Destination" |

Implementation: one module `smc/lexicon.py` holding these strings (single source, so
consistency is enforceable); `data/od_presets.yaml` gains `human:` and `story:` fields
per preset; strategy/attacker labels come from the lexicon keyed by arm.

### 1.3 Proof on demand, not proof as prose

Every ledger quote currently inline in Objectives/Playground moves behind a uniform
collapsed disclosure: a small **"From the record ▸"** row (grey, fine print) that
expands to the verbatim quote + ledger citation. The plain-language sentence above it
is curated paraphrase and NEVER states a number that is not in the expandable quote or
computed live. History is the one exception: it IS the record, so quotes stay visible,
but every quote group gains a leading plain-words line ("In plain words: …").

## 2. Design system refresh ("how would Apple ship this?")

All in `smc/theme.py`; no per-widget ad-hoc styles left behind.

1. **Type scale** (sentence case everywhere, including chart titles, buttons, tabs):
   display 30/700 · title 20/650 · body 15/400 · secondary 13 · fine print 12 muted.
   One rule for capitalisation: sentence case; product names (SACRED, Gdansk) keep
   their own casing. Audit every title/caption/button against this.
2. **Space**: base-8 spacing; cards padding 20; sections separated by whitespace, not
   rules; kill most hairline borders (cards keep a 12px radius and a barely-there
   border; the page breathes).
3. **Buttons**: one accent style (filled blue, 10px radius) for THE primary action per
   screen; everything else quiet text/ghost buttons. Never more than one accent button
   visible per view.
4. **The hero number pattern**: each screen's key metric is one large number with a
   plain caption, not a paragraph (e.g. Compare panels: "12%" big, "missions failed —
   best possible: 21%" small).
5. **Charts**: plain-language axis labels and anchor annotations from the lexicon;
   percentage ticks for failure chances; at most 3 annotations per chart; captions one
   line + "From the record ▸" where applicable.
6. **Map legend**: a compact always-on legend chip on every MapView (grey = city roads;
   line thickness = how often that road is used; orange glow = where the enemy expects
   you; X = ambush; Base/Destination dots). One shared widget.
7. **Outcome legibility** (the "did it work?" fix): when a convoy reaches the
   destination it pulses green with a floating "Delivered ✓"; an intercepted convoy
   gets the red burst plus "Ambushed ✗"; every sortie loop shows a running outcome
   strip (last 20 sorties as green/red dots) so success vs failure is visible at a
   glance. Applies to Watch, Duel, Compare, Home hero.

## 3. Screen-by-screen

### 3.1 Home

- **Title block**: "SACRED — convoy routing that cannot be ambushed by habit." Pitch
  stays three sentences, jargon-free (rewrite: no "LP", no "equilibria").
- **Hero becomes the argument**: replace the single-map hero with a **side-by-side
  mini-duel on the proving ground: "The professional planner" (left) vs "SACRED"
  (right)**, consistent colours (planner aqua, SACRED blue), the SAME ambusher logic on
  both sides (re-positions each sortie against each side's own habits: computed live).
  Left convoys keep dying at the ambush; right mostly gets through. Under each panel a
  live tally: "missions failed: 14 of 20" vs "4 of 20". Caption: one line + fine print.
  This directly replaces the static orange X oddity (the X only ever appears at the
  moment of an ambush, sized to the map, and fades).
- **Ladders**: titles become "Three convoys through Kaliningrad: how often does the
  mission fail?" and "A single convoy through Kaliningrad". Bars stay; axis switches
  to %; row labels from the lexicon; caption = ledger reference only (per Kilian).
  Both keep the era badge with the plain tooltip.
- Entry buttons: sentence case, verbs ("Watch the game", "See the promises kept",
  "Read the story", "Check the sources").

### 3.2 Playground: split into a guided, one-thing-per-screen flow

- **Landing chooser** (replaces the dense sidebar-first layout): four large cards:
  "Watch the game" / "You defend" / "You attack" / "Compare policies", each with a
  one-line description. The mode combo dies.
- **Scenario bar** (shared, top of every mode): "Scenario: [The proving ground ▾]
  [city thumbnail]" + a quiet "Change the rules ▸" disclosure containing EVERYTHING
  advanced: convoys N, ambush teams K, danger level (ONE slider: the band's top;
  low end fixed at 0.15; the two-slider band dies), "every ambush is lethal" toggle,
  objective rule, seed. Defaults just work; the casual user never opens it.
- **Watch**: defender picker + attacker picker (lexicon names, with one-line
  descriptions under the combo), ONE accent Play button, the map with legend, and a
  right column reduced to: the hero number ("chance the mission fails: 21% · the
  proven optimum here is 21%"), the goalpost bar (§3.4), the outcome strip, and ONE
  "From the record ▸" group for banked anchors. Everything else (mixture-comparison
  chart etc.) moves behind "More detail ▸".
- **You defend / You attack**: unchanged mechanics, rewritten copy (instructions in
  imperative second person, two sentences max), outcome strip, score framed as "you vs
  the machine's best" with goalposts.
- **Compare**: keep; relabel panels from the lexicon; per-panel hero number in %; the
  contender menu gains one-line descriptions; "labels needed 🏷" explained in fine
  print ("needs the maths answer key for every training map").
- **First-run tutorial**: a three-step dismissable coach overlay per mode (1. pick a
  scenario, 2. press play, 3. read the score), stored in QSettings; a "?" button in
  the scenario bar replays it. No separate tutorial tab.

### 3.3 Objectives: story first, expert view on demand

Shared pattern per exhibit: a plain **promise → verdict** header ("We promised X.
Here is X happening."), ONE interactive demonstration, plain captions, quotes
collapsed. Specific rebuilds:

- **Obj 1**: slider relabelled "How does the convoy pick its road?" with three stops
  ("always the same road" / "coin flip" / "the proven mix"); hero number = "chance of
  being caught once the enemy learns your habits"; the attacker-options chart retitled
  "every ambush option pays the enemy the same — that is why the mix cannot be beaten";
  drop axis jargon.
- **Obj 3 (training dynamics)**: default view = ONE chart, "SACRED learning: the chance
  of mission failure falls as it trains; we keep the best version" (best-checkpoint dot
  labelled "the version we keep", drift labelled "over-training, discarded"). Runs are
  "run 1/2/3", never "seed 0". Alpha/entropy/pol_hist animation and the gen23
  cold-vs-seeded chart move behind an "Expert view ▸" toggle; the gen23 chart gets
  plain series names ("fresh start" vs "given expert examples first").
- **Obj 4 (SBO)**: rebuild around a MAP, step by step: "Where should the base go?" —
  Kaliningrad map with candidate base sites as dots coloured by risk (from the F3
  design table, ledger-cited); step 2 "the search tries a few dozen sites and homes
  in" (the live race, kept, retitled "smart search vs blind search"); step 3 (B1)
  side-by-side maps: "deciding base, fleet and road-hardening TOGETHER (left) vs one
  after another (right)" with the two chosen designs marked and the honest caption
  ("together never did worse; one-after-another left 19% on the table for one of the
  two AIs"). D3 copy in plain words; numbers in the expander.
- **Obj 5**: "Varied disruption" retitled "Does it still win when the enemy grows
  stronger and the fleet grows bigger?"; sweep chart axis labels plain ("ambush teams:
  1→3", "convoys: 2→5"). The A8 explorer keeps the scatter but leads with the plain
  sentence ("On 7 out of 10 crossings, habits are expensive: we did not pick a lucky
  map — we picked a demanding one on purpose"), verbatim quote collapsed.
- **ZST**: reframe as a story in three beats: (1) "Trained in three cities. Dropped
  into Gdansk." side-by-side maps retitled "SACRED, first time here" vs "An untrained
  AI", each with its hero % and a one-line verdict; (2) "Who else can do this?" the
  amortiser ladder with lexicon names and the one honest headline ("methods that need
  the answer key do as well — SACRED is the only one that needs nothing"); (3) "How
  far does it stretch?" the gap-closure decay as a simple 'battery bar' row (full at
  home → nearly empty in Kyiv) instead of a bare bar chart; intel-error slider keeps
  its demo with the plain caption ("feed it a completely wrong danger map: it barely
  cares").

### 3.4 The goalpost bar (new shared widget)

A horizontal bar with two labelled goalposts: left "the proven optimum", right "the
best any predictable plan can do"; the current policy is a dot between them. This
replaces raw ratios in Watch/Duel/ZST verdicts ("closes 83% of the gap" reads as a
position, instantly).

### 3.5 History and Documents

- History: keep chapters/cards/quotes; add the "In plain words:" line per quote group;
  sentence-case titles; status pills get plain words ("Passed", "Failed, and that
  closed the question", "Retracted").
- Documents: viewer typography only (base 16px, line height 150%, wider margins,
  headings scaled) via `QTextDocument.setDefaultStyleSheet`; **no .md file is ever
  edited**.

## 4. Bug fixes (with root causes)

1. **`oracle.py` divide warning**: `best_cost_mixture` computes `np.exp(-costs/T)` at
   T=0.05 with costs ~26-52 → underflows to all-zeros → 0/0 NaN. Fix: shift in
   log-space (`np.exp(-(costs - costs.min())/T)`), which is exact and never zero-sums.
2. **Map pan artefacts (Home image)**: MapView uses `ItemIgnoresTransformations`
   labels/scale bar with the default minimal viewport update mode → trails. Fix:
   `setViewportUpdateMode(FullViewportUpdate)` on MapView.
3. **Zoom control**: plain scroll no longer zooms (it pans/propagates to the page
   scroll — fixes "scroll doesn't work reliably in Objectives"); zoom happens via a
   small +/− slider chip on every map (bottom-right), pinch, or Cmd+scroll.
4. **Capitalisation**: one pass over every visible string against the sentence-case
   rule (part of the lexicon sweep).
5. **Documents typography**: as §3.5 (render-side only).
6. **Home map re-fit**: hero panels re-fit after layout settles (the compare-panel
   120 ms pattern) so moving/resizing never leaves a mis-fitted scene.

## 5. Implementation order (each step ends runnable + screenshotted)

1. Foundations: `smc/lexicon.py`, theme type/spacing refresh, map legend + zoom chip +
   viewport fix + outcome effects + goalpost widget, oracle fix, documents typography,
   capitalisation sweep. (Everything else consumes these.)
2. Home rebuild (pitch, side-by-side hero, ladder relabels).
3. Playground restructure (landing cards, scenario bar + advanced drawer, per-mode
   simplification, tutorial overlays).
4. Objectives rebuilds in order Obj1 → ZST → Obj4 → Obj3 → Obj5 (impact order), with
   the "From the record ▸" expander rolled out app-wide.
5. History/Compare copy pass, full smoke + fresh screenshots, stranger-test checklist
   run against §0, SELF_REVIEW round 5, docs, tag v2.0.0.

Estimated shape: ~1 day equivalent of focused work; steps 2-4 parallelisable across
sub-agents (disjoint files) once step 1 lands.

## 6. Verification

- The §0 stranger-test table walked screen by screen against fresh screenshots.
- All existing tests stay green (provenance, anchors, convergence); new tests: lexicon
  contains no banned jargon in visible-string tables; goalpost maths; the oracle
  underflow case.
- Palette re-validated (no new hues introduced by this plan).
- The smoke gains shots of: Home hero mid-duel, the Playground landing, one tutorial
  overlay, the advanced drawer, Obj-4's map steps, the ZST story beats.
