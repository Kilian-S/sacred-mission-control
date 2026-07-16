#!/bin/zsh
# make_data_asset.sh: build sacred-data.zip, the curated slice of the sacred repo
# the app needs at runtime, for attaching to a GitHub Release.
#
# The app is a read-only viewer of the sibling `sacred/` repo, whose data
# (maps, run results, checkpoints, logs) is gitignored, so it never travels with
# a git clone. This packages exactly what the app reads (per DATA_MAP.md) into a
# single `sacred/` folder inside sacred-data.zip. setup.command downloads that
# asset and unzips it, giving the clone a `./sacred` to read.
#
# Usage:  scripts/make_data_asset.sh [OUTPUT_DIR]
# Output: OUTPUT_DIR/sacred-data.zip   (defaults to the app repo root)

set -e -u
setopt sh_word_split 2>/dev/null || true

APP_DIR="${0:A:h:h}"
SACRED_DIR="${SACRED_ROOT:-${APP_DIR:h}/sacred}"
OUT_DIR="${1:-$APP_DIR}"
STAGE="$(mktemp -d)/sacred"

echo "Sacred:  $SACRED_DIR"
echo "Output:  $OUT_DIR/sacred-data.zip"

if [ ! -d "$SACRED_DIR/experiments" ]; then
  echo "ERROR: sacred repo not found at $SACRED_DIR (set SACRED_ROOT)." >&2
  exit 1
fi

# Run families whose checkpoints the app loads LIVE (roster / compare / ZST).
# Every other family ships its JSON only. Source: DATA_MAP.md + policies.py.
ROSTER_FAMILIES=(
  gen13_lock gen14_evidence gen15_generalist gen16_multicity
  gen19_b1lite1 gen20_f2 gen21_vanilla gen22_rotation
  gen24_distill gen25_dr zst_step0
)

mkdir -p "$STAGE"

# 1. code the app imports live (src, scripts) + Documents markdown + figures,
#    minus the heavy artefact trees handled below.
rsync -a \
  --exclude='.git/' --exclude='.venv/' --exclude='.idea/' --exclude='.claude/' \
  --exclude='.pytest_cache/' --exclude='__pycache__/' --exclude='.DS_Store' \
  --exclude='cache/' --exclude='tests/' --exclude='notebooks/' \
  --exclude='models/' --exclude='logs/' --exclude='data/' \
  "$SACRED_DIR/" "$STAGE/"

# 2. maps (essential), campaign TensorBoard curves (History charts)
mkdir -p "$STAGE/data"
rsync -a "$SACRED_DIR/data/maps/" "$STAGE/data/maps/"
if [ -d "$SACRED_DIR/logs/tb_runs" ]; then
  mkdir -p "$STAGE/logs"
  rsync -a "$SACRED_DIR/logs/tb_runs/" "$STAGE/logs/tb_runs/"
fi

# 3. every run JSON (charts), then the roster checkpoint families
rsync -a --prune-empty-dirs -f'+ */' -f'+ *.json' -f'- *' \
  "$SACRED_DIR/models/runs/" "$STAGE/models/runs/"
for fam in $ROSTER_FAMILIES; do
  [ -d "$SACRED_DIR/models/runs/$fam" ] && \
    rsync -a "$SACRED_DIR/models/runs/$fam/" "$STAGE/models/runs/$fam/"
done

echo "\nStaged sacred slice: $(du -sh "$STAGE" | cut -f1)"
rm -f "$OUT_DIR/sacred-data.zip"
( cd "${STAGE:h}" && zip -q -r -X "$OUT_DIR/sacred-data.zip" "sacred" -x '*.DS_Store' )
rm -rf "${STAGE:h}"
echo "Wrote:   $OUT_DIR/sacred-data.zip  ($(du -sh "$OUT_DIR/sacred-data.zip" | cut -f1))"
echo "\nAttach it to a GitHub Release, e.g.:"
echo "  gh release create data-v1 \"$OUT_DIR/sacred-data.zip\" -t 'SACRED data' -n 'Runtime data for SACRED Mission Control.'"
