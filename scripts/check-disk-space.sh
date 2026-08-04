#!/bin/sh
set -eu

minimum_kib=6291456
available_kib=$(df -Pk . | awk 'NR == 2 { print $4 }')

if [ -z "$available_kib" ] || [ "$available_kib" -lt "$minimum_kib" ]; then
  echo "At least 6 GiB of free disk space is required to start the local stack." >&2
  echo "Available: ${available_kib:-unknown} KiB." >&2
  exit 1
fi

echo "Disk preflight passed: ${available_kib} KiB available."
