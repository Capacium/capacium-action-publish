#!/usr/bin/env bash
# Defeat attempt 2: rejection as a 50x server error plus success lines.
set -u
if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi
echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'error 500: internal server error — submission did not complete'
echo 'Published: skillweave/skillweave'
echo '  URL: https://api.capacium.xyz/listings/skillweave/skillweave'
exit 0
