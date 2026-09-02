#!/usr/bin/env bash
# Queued-but-unconfirmed submission (acceptance criterion 4): `cap publish`
# prints an "Accepted ... (job ...)" line and success-shaped listing lines, then
# a "Still processing" note, and exits 0. The registry read-back returns "not
# found" because the listing is not yet committed. Must NOT pass.
set -u
if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi
echo 'Accepted: skillweave/skillweave (job 9f8a7b)'
echo 'Published: skillweave/skillweave'
echo '  Kind: skill'
echo '  URL: https://capacium.xyz/listings/skillweave/skillweave'
echo 'Still processing — check later with job id 9f8a7b'
exit 0
