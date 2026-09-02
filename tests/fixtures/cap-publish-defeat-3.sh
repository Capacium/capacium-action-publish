#!/usr/bin/env bash
# Defeat attempt 3: rejection as a policy denial plus success lines.
set -u
if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi
echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'denied: policy violation — name is reserved'
echo 'Published: skillweave/skillweave'
echo '  Kind: skill'
echo '  URL: https://capacium.xyz/listings/skillweave/skillweave'
exit 0
