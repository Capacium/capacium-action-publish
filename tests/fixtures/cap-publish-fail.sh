#!/usr/bin/env bash
# Stub reproducing the observed failing `cap publish`: submission rejected
# (HTTP 403 Cloudflare challenge page) yet the process exits 0. The follow-up
# `cap info` read-back returns "not found" — no listing was actually created.
set -u

if [ "${1:-}" = "info" ]; then
  echo "Capability \"${2:-?}\" not found."
  exit 0
fi

echo 'Publishing skillweave/skillweave@1.5.2...'
echo 'HTTP 403   (a Cloudflare challenge page for https://api.capacium.xyz/v2/v2/submit)'
echo 'Submission failed (HTTP 403)'
exit 0
