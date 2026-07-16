#!/bin/zsh
# One-click setup + launch for a fresh git clone of SACRED Mission Control (macOS).
#
# On the first run this downloads the project data (~400 MB, a GitHub Release
# asset, because it is too large to live in git) and builds a private Python
# environment (~2 GB). After that it just opens the app.
#
# If macOS blocks the double-click ("unidentified developer"), right-click this
# file in Finder and choose Open, just once.

cd "${0:A:h}" || { echo "Could not find the app folder."; echo "Press return to close."; read _; exit 1; }

DATA_URL="https://github.com/Kilian-S/sacred-mission-control/releases/latest/download/sacred-data.zip"

# --- 1. project data -------------------------------------------------------
if [ ! -d "sacred/experiments" ] && [ ! -d "../sacred/experiments" ]; then
  echo "Downloading the project data (about 400 MB, one time)..."
  if command -v curl >/dev/null 2>&1 && curl -fL --retry 3 -o sacred-data.zip "$DATA_URL"; then
    echo "Unpacking..."
    if command -v ditto >/dev/null 2>&1; then ditto -x -k sacred-data.zip .; else unzip -oq sacred-data.zip; fi
    rm -f sacred-data.zip
  fi
  if [ ! -d "sacred/experiments" ]; then
    echo ""
    echo "Could not fetch the data automatically."
    echo "Please download sacred-data.zip from:"
    echo "  https://github.com/Kilian-S/sacred-mission-control/releases/latest"
    echo "unzip it inside this folder so that a 'sacred' folder appears next to 'smc',"
    echo "then run this launcher again."
    echo "Press return to close."; read _; exit 1
  fi
  echo "Data ready."
fi

# --- 2. Python environment -------------------------------------------------
PYTHON=""
for c in python3.13 python3.12 python3.11 python3; do
  p=$(command -v $c 2>/dev/null) || continue
  if "$p" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON="$p"; break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "SACRED Mission Control needs Python 3.11 or newer (3.13 recommended)."
  echo "Install it from https://www.python.org/downloads/  then run this launcher again."
  echo "Press return to close."; read _; exit 1
fi
echo "Using $($PYTHON --version) at $PYTHON"

if [ ! -x .venv/bin/python ]; then
  echo ""
  echo "First run: building a private Python environment (about 2 GB, a few minutes)."
  "$PYTHON" -m venv .venv || { echo "Could not create the environment."; echo "Press return to close."; read _; exit 1; }
  .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
  if ! .venv/bin/pip install -r requirements.txt; then
    echo ""; echo "The install did not finish. Please read the messages above."
    echo "Press return to close."; read _; exit 1
  fi
  echo "Setup complete."
fi

# --- 3. launch -------------------------------------------------------------
echo "Launching SACRED Mission Control..."
exec .venv/bin/python -m smc.app
