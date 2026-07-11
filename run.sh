#!/bin/zsh
# SACRED Mission Control launcher.
# Usage: ./run.sh            (launch the app)
#        ./run.sh --tab N    (open on tab N, 1-5)
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "No .venv found. Create it with:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
exec .venv/bin/python -m smc.app "$@"
