#!/usr/bin/env bash
set -euo pipefail
sub="$1"
out="$2"
flask --app run.py tenant-export --subdomain "$sub" --out "$out"
