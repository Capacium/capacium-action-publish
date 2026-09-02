#!/usr/bin/env bash
# DEFEAT-C: the reviewer's exact stub. `cap publish` exits 0 and prints BOTH
# success-shaped evidence lines ("Published:" and "URL:") alongside an explicit
# rejection worded outside any blocklist ("HTTP 403 Forbidden — ... rejected").
# Nothing was actually listed, so the `cap info` read-back returns "not found".
set -u

if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi

echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'HTTP 403 Forbidden — the Exchange rejected this submission.'
echo 'Published: skillweave/skillweave'
echo '  Kind: skill'
echo '  URL: https://api.capacium.xyz/listings/skillweave/skillweave'
exit 0
