#!/usr/bin/env bash
set -euo pipefail
sub="$1"
flask --app run.py tenant-delete --subdomain "$sub"
