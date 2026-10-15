#!/usr/bin/env bash
set -e
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi
python3 -m pip install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt
exec python3 main.py
