#!/usr/bin/env bash
# Defeat attempt 1: rejection with "Unauthorized/401" wording plus success lines.
set -u
if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi
echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'ERROR: upstream registry refused the request (401 Unauthorized)'
echo 'Published: skillweave/skillweave'
echo '  URL: https://api.capacium.xyz/listings/skillweave/skillweave'
exit 0
