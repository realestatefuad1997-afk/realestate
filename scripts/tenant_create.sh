#!/usr/bin/env bash
set -euo pipefail
name="$1"
sub="$2"
flask --app run.py tenant-create --name "$name" --subdomain "$sub"
