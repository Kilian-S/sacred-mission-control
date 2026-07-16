# SACRED Mission Control

A small desktop app that lets you see the SACRED thesis project at work: convoys
choosing routes across real city road networks while a hidden adversary tries to
ambush them, and an AI that learns to slip through where an ordinary route
planner keeps getting caught.

Everything runs on your own Mac. Nothing is sent anywhere, and the app only ever
reads the project's data, it never changes it.

## What you'll see

Five tabs along the top (or press Cmd-1 to Cmd-5):

- **Home** puts the industry-standard planner and SACRED side by side on the same
  map and lets them run, each keeping a tally of missions lost.
- **Playground** lets you play: watch the game, take the defender's side, take the
  attacker's side, or compare the different AIs head to head. One plain-language
  bar sets the scene; everything advanced hides behind a "Change the rules" drawer.
- **Objectives** is six short "we promised this, here it is" exhibits, each with
  one thing you can try yourself.
- **History** walks through the project generation by generation.
- **Documents** is the project's own written record, comfortably typeset.

## Before you start

- A **Mac** (this build is for macOS).
- **Python 3.13** (3.11 or newer will do). If you are not sure you have it, install
  it from <https://www.python.org/downloads/> and pick the latest 3.13. The
  installer takes care of everything.
- About **2 GB of free space** and a few minutes the first time, because the app
  quietly downloads the scientific-computing libraries it needs.

## The easy way (double-click)

1. Double-click **"Launch SACRED Mission Control.command"** in this folder.
2. The first time, macOS may say it is *"from an unidentified developer"* and
   refuse. That is normal for anything downloaded. Just **right-click** the file,
   choose **Open**, then **Open** again. You only do this once.
3. A Terminal window opens and, on the first run, sets things up (this is the
   couple-of-minutes download). When it finishes, the app appears. Leave the
   Terminal window open while you use the app.

Every time after that, the same double-click opens the app straight away.

## The reliable way (Terminal)

If the double-click gives you any trouble, open the **Terminal** app and paste
these two lines (adjust the first path if you unzipped somewhere other than your
Downloads folder):

```bash
cd ~/Downloads/SACRED-Mission-Control/sacred-mission-control
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && ./run.sh
```

The first line moves into the app folder; the second builds the private
environment (the one-time download) and launches the app. Next time, just:

```bash
cd ~/Downloads/SACRED-Mission-Control/sacred-mission-control && ./run.sh
```

## What's in this folder

```
SACRED-Mission-Control/
├─ README.md                              ← you are here
├─ Launch SACRED Mission Control.command  ← double-click to run
├─ sacred-mission-control/                ← the app
└─ sacred/                                ← the project's data the app reads
```

The `sacred/` folder is a trimmed copy of the research repository: the city maps,
the results, the trained-AI checkpoints the app actually demonstrates, and the
written ledgers, about half a gigabyte instead of the full nine. The app finds it
automatically because it sits right next to the app folder.

## If something goes wrong

- **"Unidentified developer" when double-clicking** — right-click the launcher and
  choose Open (see step 2 above). This is macOS being cautious about downloads.
- **"needs Python 3.11 or newer"** — install Python 3.13 from
  <https://www.python.org/downloads/> and try again.
- **The app opens but a screen looks empty, or it mentions missing data** — the
  app could not find the `sacred/` data folder. Make sure `sacred/` and
  `sacred-mission-control/` are still side by side inside this folder, exactly as
  they came out of the archive.
- **Anything else** — send Kilian the messages shown in the Terminal window; they
  say exactly what happened.

## A note on the numbers

Every figure on screen is either quoted from the project's written record (with
the exact citation one click away, under "From the record") or computed live in
front of you and labelled as such. The two are never mixed, so you can always tell
what is a stored result and what the app worked out on the spot.
