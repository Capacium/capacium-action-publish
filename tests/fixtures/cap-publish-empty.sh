#!/usr/bin/env bash
# Stub: exits 0 and prints only a vacuous message — no failure marker, no
# parseable publish evidence. Demonstrates the post-condition fires on absent
# evidence alone (not merely on an explicit failure marker), so a future CLI
# regression that swallows the rejection entirely still cannot pass.
echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'Done.'
exit 0
