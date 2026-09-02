#!/usr/bin/env python3
"""Red proof for the publish-step post-condition.

Exercises the publish step's bash logic from action.yml against a stub
``cap publish`` that prints a known output and exits 0. Verifies the step
passes on a good output and fails (naming the missing evidence) on the
recorded failure output — independent of the process exit code.

The step's own shell body is reproduced verbatim from ``action.yml`` and run
with a shim ``cap`` placed on PATH, so the exact parsing + post-condition
shipped in the action is what gets tested.

Usage:
    tests/publish_step_test.py [fixture-stub ...]
Each stub is copied onto PATH as ``cap`` and needs no executable bit (invoked
via sh -c shim). Expectation is derived from the fixture filename: ``*-fail``
must be rejected by the step; ``*-ok`` must succeed and set all four outputs.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ACTION = Path(__file__).resolve().parents[1] / "action.yml"


def extract_publish_run(action_text: str) -> str:
    """Return the shell body of the publish step (id: publish), de-indented."""
    steps = re.split(r"(?=^\s*- name:)", action_text, flags=re.M)
    for step in steps:
        if 'id: publish' in step:
            body = step.split("run:", 1)[1]
            if body.lstrip().startswith("|"):
                body = body.lstrip()[1:]
            lines = body.splitlines()
            indents = [len(l) - len(l.lstrip(" ")) for l in lines if l.strip()]
            base = min(indents) if indents else 0
            # strip the leading '|' of the block scalar if present anywhere
            dedented = []
            for l in lines:
                if not l.strip():
                    dedented.append("")
                else:
                    dedented.append(l[base:])
            return "\n".join(dedented).strip("\n")
    raise SystemExit("publish step (id: publish) not found in action.yml")


def fill_tokens(body: str) -> str:
    """Substitute composite ${{ ... }} tokens with static run values."""
    body = body.replace("${{ steps.package.outputs.tarball }}", "dist/dummy.tar.gz")
    body = body.replace("${{ inputs.registry_url }}", "https://api.capacium.xyz")
    return body


def _grep_shim() -> str:
    """A ``grep`` replacement for the exact invocations in action.yml.

    macOS BSD grep lacks ``-P``. This Python shim supports exactly:
      * ``grep -oP 'PCRE'``  (with lookbehind; prints first match, `head -1`)
      * ``grep -iE 'ERE'``   (case-insensitive ERE; prints matching lines)
    which are the only two forms the publish step uses.
    """
    return r'''#!/usr/bin/env python3
import sys, re
a = sys.argv[1:]
pcre = oflag = iflag = ext = False
pat = None
i = 0
while i < len(a):
    x = a[i]
    if x == "-oP" or x == "-Po":
        oflag = True; pcre = True
    elif x == "-P":
        pcre = True
    elif x == "-o":
        oflag = True
    elif x == "-iE" or x == "-Ei":
        iflag = True; ext = True
    elif x == "-i":
        iflag = True
    elif x == "-E":
        ext = True
    else:
        pat = x
    i += 1
flags = re.IGNORECASE if iflag else 0
rx = re.compile(pat, flags) if pat else None
text = sys.stdin.read()
if rx is None:
    sys.exit(0)
if oflag:
    for line in text.splitlines():
        m = rx.search(line)
        if m:
            print(m.group(0))
            break
else:
    for line in text.splitlines():
        if rx.search(line):
            print(line)
'''


def run_step(body: str, cap_shim: Path) -> tuple[int, str, dict]:
    env = dict(os.environ)
    env["CAPACIUM_API_TOKEN"] = "test-token"
    body = fill_tokens(body)
    with tempfile.TemporaryDirectory() as d:
        # shim dir: `cap` -> the stub; `grep` -> Python PCRE grep
        shimdir = Path(d) / "bin"
        shimdir.mkdir()
        shim = shimdir / "cap"
        shim.write_text(f'#!/bin/sh\nexec sh "{cap_shim}" "$@"\n')
        shim.chmod(0o755)
        grep = shimdir / "grep"
        grep.write_text(_grep_shim())
        grep.chmod(0o755)
        env["PATH"] = str(shimdir) + os.pathsep + env.get("PATH", "")
        out_file = Path(d) / "gh-out"
        env["GITHUB_OUTPUT"] = str(out_file)
        proc = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", body],
            capture_output=True, text=True, env=env,
        )
        outputs = {}
        if out_file.exists():
            for line in out_file.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    outputs[k] = v
        return proc.returncode, (proc.stdout + proc.stderr).strip(), outputs


def main():
    fixtures = sys.argv[1:]
    if not fixtures:
        fixtures = [
            "tests/fixtures/cap-publish-fail.sh",
            "tests/fixtures/cap-publish-empty.sh",
            "tests/fixtures/cap-publish-ok.sh",
        ]
    action_text = Path(ACTION).read_text()
    body = extract_publish_run(action_text)
    failures = 0
    for stub in fixtures:
        stub_p = Path(stub).resolve()
        name = stub_p.name
        expect_fail = "-fail" in name or "-empty" in name
        rc, out, outputs = run_step(body, stub_p)
        print(f"=== {name} ===")
        print(out)
        print(f"exit code: {rc}")
        print(f"outputs: {outputs}")
        if expect_fail:
            if rc == 0:
                print(">> FAIL: expected step to reject the fixture, but it PASSED")
                failures += 1
            else:
                named = (
                    "exchange URL" in out
                    or "canonical name" in out
                    or "failed submission" in out
                )
                if not named:
                    print(">> FAIL: rejection message does not name the missing evidence")
                    failures += 1
                else:
                    print(">> okay: rejected and names missing evidence")
        else:
            ok = (
                rc == 0
                and outputs.get("canonical_name") == "skillweave/skillweave"
                and outputs.get("exchange_url") == "https://capacium.xyz/listings/skillweave/skillweave"
                and outputs.get("quality_score") == "45"
                and outputs.get("trust_state") == "discovered"
            )
            if not ok:
                print(">> FAIL: expected pass with all four outputs parsed; got rc=%s outputs=%s" % (rc, outputs))
                failures += 1
            else:
                print(">> okay: passed and set all four outputs")
        print()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
