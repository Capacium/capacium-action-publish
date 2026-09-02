#!/usr/bin/env bash
# Stub: `cap publish` exits 0 and prints only a vacuous message — no parseable
# publish evidence, no rejection wording. The follow-up `cap info` read-back
# returns "not found", matching the fact that nothing was listed.
set -u

if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi

echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'Done.'
exit 0
