#!/usr/bin/env bash
# Defeat attempt 4 (version-confirmation): publish prints success lines at 1.5.2
# but the registry read-back returns only the PREVIOUS version 1.5.1 — the
# listing was not updated. Must be rejected by the version check.
set -u
if [ "${1:-}" = "info" ]; then
  cat <<'JSON'
{
  "$schema": "https://capacium.xyz/schemas/capability-info.json",
  "name": "skillweave",
  "owner": "skillweave",
  "kind": "skill",
  "trust": "discovered",
  "version": "1.5.1",
  "description": "SkillWeave"
}
JSON
  exit 0
fi
echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'Published: skillweave/skillweave'
echo '  Kind: skill'
echo '  URL: https://capacium.xyz/listings/skillweave/skillweave'
echo '  Trust state:   discovered'
echo '  Quality score: 45/100'
exit 0
