#!/bin/zsh
# Double-clickable launcher for SACRED Mission Control (macOS).
# First run builds a private Python environment (a one-time ~2 GB download);
# every run after that just opens the app.
#
# If double-clicking is blocked ("unidentified developer"), right-click this
# file in Finder and choose Open, just once. Or run the two Terminal commands
# in README.md instead.

cd "${0:A:h}/sacred-mission-control" || {
  echo "Could not find the app folder next to this launcher."; echo "Press return to close."; read _; exit 1;
}

# --- find a modern Python (3.11 or newer; 3.13 is what this was tested on) ---
PYTHON=""
for c in python3.13 python3.12 python3.11 python3; do
  p=$(command -v $c 2>/dev/null) || continue
  if "$p" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON="$p"; break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "SACRED Mission Control needs Python 3.11 or newer (3.13 recommended)."
  echo "Install it from https://www.python.org/downloads/  then double-click this launcher again."
  echo "Press return to close."; read _; exit 1
fi
echo "Using $($PYTHON --version) at $PYTHON"

# --- one-time environment setup ---
if [ ! -x .venv/bin/python ]; then
  echo ""
  echo "First run: setting up a private Python environment."
  echo "This downloads about 2 GB and can take several minutes. Please leave this window open."
  echo ""
  "$PYTHON" -m venv .venv || { echo "Could not create the environment."; echo "Press return to close."; read _; exit 1; }
  .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
  if ! .venv/bin/pip install -r requirements.txt; then
    echo ""
    echo "The install did not finish. Please read the messages above and try again."
    echo "Press return to close."; read _; exit 1
  fi
  echo ""
  echo "Setup complete."
fi

echo "Launching SACRED Mission Control..."
exec .venv/bin/python -m smc.app
