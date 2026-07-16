#!/bin/zsh
# make_bundle.sh: assemble a self-contained, shareable bundle of SACRED Mission
# Control plus exactly the sacred-repo data the app reads at runtime.
#
# The app is a read-only viewer of the sibling `sacred/` repo. The full sacred
# working tree is ~8.8 GB, almost all of it training checkpoints the app never
# loads. This script copies only what the app touches (curated per DATA_MAP.md):
# the app itself, the sacred source/scripts it imports live, the city maps, every
# run JSON, the live-roster checkpoints, the ledgers, the figures, and the
# campaign TensorBoard logs. Result: ~0.5 GB, laid out so the app runs with no
# environment variables.
#
# Usage:
#   scripts/make_bundle.sh [OUTPUT_DIR]
# Produces:
#   OUTPUT_DIR/SACRED-Mission-Control/          (the unpacked bundle)
#   OUTPUT_DIR/SACRED-Mission-Control.zip       (the shareable archive)
# OUTPUT_DIR defaults to ~/Desktop.

set -e -u
setopt sh_word_split 2>/dev/null || true

# ------------------------------------------------------------------ locations
APP_DIR="${0:A:h:h}"                 # this script is in <app>/scripts/
SACRED_DIR="${SACRED_ROOT:-${APP_DIR:h}/sacred}"
OUT_DIR="${1:-$HOME/Desktop}"
BUNDLE_NAME="SACRED-Mission-Control"
STAGE="$OUT_DIR/$BUNDLE_NAME"

echo "App:     $APP_DIR"
echo "Sacred:  $SACRED_DIR"
echo "Output:  $STAGE"

if [ ! -d "$SACRED_DIR/experiments" ]; then
  echo "ERROR: sacred repo not found at $SACRED_DIR (set SACRED_ROOT)." >&2
  exit 1
fi
if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is required (ships with macOS)." >&2
  exit 1
fi

# The run families whose actor/defender checkpoints the app loads LIVE (roster,
# compare mode, ZST ladder, Home hero). Every OTHER family contributes charts
# from its JSON only, so we ship its JSON but not its multi-gigabyte .pt files.
# Source of truth: DATA_MAP.md section 2 + smc/sacred_bridge/policies.py.
ROSTER_FAMILIES=(
  gen13_lock gen14_evidence gen15_generalist gen16_multicity
  gen19_b1lite1 gen20_f2 gen21_vanilla gen22_rotation
  gen24_distill gen25_dr zst_step0
)

# ------------------------------------------------------------------ clean slate
rm -rf "$STAGE" "$OUT_DIR/$BUNDLE_NAME.zip"
mkdir -p "$STAGE/sacred-mission-control" "$STAGE/sacred"

# ------------------------------------------------------------------ 1. the app
echo "\n[1/5] Copying the app ..."
rsync -a \
  --exclude='.venv/' --exclude='.git/' --exclude='__pycache__/' \
  --exclude='.pytest_cache/' --exclude='.DS_Store' \
  --exclude='screenshots/*.png' \
  "$APP_DIR/" "$STAGE/sacred-mission-control/"

# ------------------------------------------------------------------ 2. sacred code + docs
# Everything the app imports live (src, scripts) or shows in Documents (top-level
# *.md + experiments/*.md), minus the heavy artefact trees handled below.
echo "[2/5] Copying sacred source, scripts, ledgers, figures ..."
rsync -a \
  --exclude='.git/' --exclude='.venv/' --exclude='.idea/' --exclude='.claude/' \
  --exclude='.pytest_cache/' --exclude='__pycache__/' --exclude='.DS_Store' \
  --exclude='cache/' --exclude='tests/' --exclude='notebooks/' \
  --exclude='models/' --exclude='logs/' --exclude='data/' \
  "$SACRED_DIR/" "$STAGE/sacred/"

# maps (the app cannot build a single instance without these); skip the heavy
# erb_assign.pt and empty scaffolding dirs.
mkdir -p "$STAGE/sacred/data"
rsync -a "$SACRED_DIR/data/maps/" "$STAGE/sacred/data/maps/"

# campaign-era TensorBoard curves (History charts).
if [ -d "$SACRED_DIR/logs/tb_runs" ]; then
  mkdir -p "$STAGE/sacred/logs"
  rsync -a "$SACRED_DIR/logs/tb_runs/" "$STAGE/sacred/logs/tb_runs/"
fi

# ------------------------------------------------------------------ 3. run JSONs (all families)
echo "[3/5] Copying every run JSON (charts) ..."
rsync -a --prune-empty-dirs \
  -f'+ */' -f'+ *.json' -f'- *' \
  "$SACRED_DIR/models/runs/" "$STAGE/sacred/models/runs/"

# ------------------------------------------------------------------ 4. roster checkpoints only
echo "[4/5] Copying live-roster checkpoints ..."
for fam in $ROSTER_FAMILIES; do
  if [ -d "$SACRED_DIR/models/runs/$fam" ]; then
    rsync -a "$SACRED_DIR/models/runs/$fam/" "$STAGE/sacred/models/runs/$fam/"
  else
    echo "  note: roster family '$fam' not present, skipping"
  fi
done

# ------------------------------------------------------------------ 5. README + launcher + zip
echo "[5/5] Adding README + launcher, then zipping ..."
cp "$APP_DIR/scripts/bundle_README.md" "$STAGE/README.md"
cp "$APP_DIR/scripts/Launch SACRED Mission Control.command" "$STAGE/"
chmod +x "$STAGE/Launch SACRED Mission Control.command"

# a clean venv will be built on the reviewer's machine; make sure none leaks in
rm -rf "$STAGE/sacred-mission-control/.venv"

# report sizes
echo "\nBundle contents:"
du -sh "$STAGE"/* 2>/dev/null | sort -h
echo "\nTotal unpacked: $(du -sh "$STAGE" | cut -f1)"

( cd "$OUT_DIR" && zip -q -r -X "$BUNDLE_NAME.zip" "$BUNDLE_NAME" \
    -x '*.DS_Store' )
echo "Zipped:         $(du -sh "$OUT_DIR/$BUNDLE_NAME.zip" | cut -f1)  ->  $OUT_DIR/$BUNDLE_NAME.zip"
echo "\nDone. Share $OUT_DIR/$BUNDLE_NAME.zip"
