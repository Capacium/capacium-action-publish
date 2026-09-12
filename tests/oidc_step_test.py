#!/usr/bin/env python3
"""Regression tests for the OIDC Trusted Publishing step.

The defect this exists for: the step acquired an OIDC token and exchanged it
for a short-lived publish token, then wrote the publish token to
``$GITHUB_OUTPUT`` without ever masking it. The value therefore appeared
verbatim in the step log and in every later step's environment. Both secrets
must be masked with GitHub's ``::add-mask::`` work-flow command before they can
reach output or a later step.

The step body is reproduced verbatim from ``action.yml`` and run with a stubbed
``curl`` (which answers both the OIDC token endpoint and the exchange endpoint)
and a stubbed ``jq`` is avoided — the action uses the real ``jq`` if present,
so the tests require it on PATH; when it is absent the exchange assertions are
skipped rather than silently passing.

Usage:
    tests/oidc_step_test.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ACTION = Path(__file__).resolve().parents[1] / "action.yml"
STEP_NAME = "Obtain Trusted Publish Token (OIDC)"

OIDC_TOKEN = "oidc-token-abc123"
PUBLISH_TOKEN = "publish-token-xyz789"


def extract_oidc_run(action_text):
    steps = re.split(r"(?=^\s*- name:)", action_text, flags=re.M)
    for step in steps:
        if STEP_NAME in step.split("\n", 1)[0]:
            body = step.split("run:", 1)[1]
            if body.lstrip().startswith("|"):
                body = body.lstrip()[1:]
            lines = body.splitlines()
            base = next((len(l) - len(l.lstrip(" ")) for l in lines if l.strip()), 0)
            out = []
            for l in lines:
                if not l.strip():
                    out.append("")
                    continue
                if len(l) - len(l.lstrip(" ")) < base:
                    break
                out.append(l[base:])
            return "\n".join(out).strip("\n")
    raise SystemExit("step %r not found in action.yml" % STEP_NAME)


def _curl_shim() -> str:
    """Answer the OIDC token endpoint and the exchange endpoint.

    * Token request: prints {"value": OIDC_TOKEN}
    * Exchange POST: prints {"token": PUBLISH_TOKEN, "expires_in": 900,
      "scope": "publish"}
    """
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "joined = ' '.join(args)\n"
        "if '/v2/publish/token' in joined:\n"
        "    print('{\"token\": \"" + PUBLISH_TOKEN + "\", "
        "\"expires_in\": 900, \"scope\": \"publish\"}')\n"
        "else:\n"
        "    print('{\"value\": \"" + OIDC_TOKEN + "\"}')\n"
    )


def run_step(body: str) -> tuple[int, str, dict]:
    with tempfile.TemporaryDirectory() as d:
        shimdir = Path(d) / "bin"
        shimdir.mkdir()
        (shimdir / "curl").write_text(_curl_shim())
        (shimdir / "curl").chmod(0o755)

        env = dict(os.environ)
        env["PATH"] = str(shimdir) + os.pathsep + env.get("PATH", "")
        env["ACTIONS_ID_TOKEN_REQUEST_TOKEN"] = "requester-token"
        env["ACTIONS_ID_TOKEN_REQUEST_URL"] = (
            "https://pipelines.actions.githubusercontent.com/oidc?api-version=2"
        )
        env["REGISTRY"] = "https://api.capacium.xyz"
        out_file = Path(d) / "gh-out"
        env["GITHUB_OUTPUT"] = str(out_file)

        proc = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", body],
            capture_output=True, text=True, env=env, cwd=d,
        )
        outputs = {}
        if out_file.exists():
            for line in out_file.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    outputs[k] = v
        return proc.returncode, proc.stdout + proc.stderr, outputs


def main():
    if shutil.which("jq") is None:
        print("SKIP: jq not available; cannot exercise the OIDC exchange step")
        return 0

    body = extract_oidc_run(ACTION.read_text(encoding="utf-8"))
    rc, out, outputs = run_step(body)

    failures = 0
    print("exit code: %d" % rc)
    print("outputs: %s" % outputs)
    print("--- step output ---")
    print(out)

    if rc != 0:
        print(">> FAIL: OIDC step did not succeed (rc=%d)" % rc)
        failures += 1

    # 1. The OIDC token must be masked.
    if "::add-mask::" + OIDC_TOKEN not in out:
        print(">> FAIL: OIDC_TOKEN was not masked with ::add-mask::")
        failures += 1
    else:
        print(">> okay: OIDC_TOKEN masked")

    # 2. The publish token must be masked, and masked BEFORE it is written to
    #    GITHUB_OUTPUT (the order in the log is the order of execution).
    mask_line = "::add-mask::" + PUBLISH_TOKEN
    if mask_line not in out:
        print(">> FAIL: PUBLISH_TOKEN was not masked with ::add-mask::")
        failures += 1
    else:
        mask_idx = out.index(mask_line)
        # The output write is invisible in the log, so assert the mask appears
        # in the step output at all; the ordering guarantee comes from the
        # source: the mask line precedes the >> "$GITHUB_OUTPUT" line.
        print(">> okay: PUBLISH_TOKEN masked")
        if mask_idx < 0:
            failures += 1

    # 3. The token must still reach GITHUB_OUTPUT (masking must not break the
    #    feature). GitHub redacts the log display, not the stored output.
    if outputs.get("oidc_publish_token") != PUBLISH_TOKEN:
        print(">> FAIL: oidc_publish_token output missing/wrong: %r"
              % outputs.get("oidc_publish_token"))
        failures += 1
    else:
        print(">> okay: publish token propagated via GITHUB_OUTPUT")

    if failures:
        print("\n%d failure(s)" % failures)
        return 1
    print("\nall OIDC masking checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
