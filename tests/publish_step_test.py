#!/usr/bin/env python3
"""Post-condition tests for the publish step.

Exercises the publish step's bash from action.yml against stubbed ``cap`` and
``curl`` programs and a stubbed manifest. The step's own shell body is
reproduced verbatim from ``action.yml`` and run with shims placed on PATH, so
the exact parsing + post-condition shipped in the action is what gets tested.

Three shims:

  * ``cap``   — emits a fixed publish stdout and exits with a fixed code.
  * ``curl``  — writes a fixed confirmation body to the ``-o`` target and
                prints a fixed HTTP status (for ``-w '%{http_code}'``).
  * ``grep``  — Python PCRE/ERE/fixed-string grep (macOS BSD grep lacks -P).

The manifest the action reads is written into the run dir as ``capability.yaml``,
so the action's *independent* name/version come from the file, exactly as in a
real run — never from ``cap publish`` stdout.

A case is a dict:

    name          str   — case label
    manifest      dict  — capability.yaml name/version/owner (or omit owner)
    cap_stdout    str   — what ``cap publish`` prints
    cap_exit      int   — ``cap publish`` exit code
    curl_status   str   — confirmation HTTP status ("200", "404", "500", …)
    curl_body     str   — confirmation response body (may be "" for network fail)
    curl_fail     bool  — if True, curl exits non-zero (network/DNS/timeout)
    expect        bool  — True = step must pass (green), False = must fail
    msg_token     str   — substring the reject message must contain (fail cases)

Usage:
    tests/publish_step_test.py            # run all cases
    tests/publish_step_test.py <case>     # run one case by name
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ACTION = Path(__file__).resolve().parents[1] / "action.yml"

CANONICAL = "skillweave/skillweave"
EXCHANGE_URL = "https://capacium.xyz/listings/skillweave/skillweave"


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
    body = body.replace("${{ inputs.capability_path }}", "./capability.yaml")
    return body


def _grep_shim() -> str:
    """Python replacement for the grep invocations in action.yml.

    Supports:
      * grep -oP 'PCRE'  (lookbehind; print first match only)
      * grep -qF 'str'   (quiet fixed-string match; exit 0/1 only)
      * grep -F 'str'    (fixed-string, print matching lines)
    """
    return r'''#!/usr/bin/env python3
import sys, re, os
a = sys.argv[1:]
oflag = pcre = iflag = ext = fixed = quiet = False
pat = None
flags_seen = True
for x in a:
    if x in ("-oP", "-Po"):
        oflag = True; pcre = True
    elif x == "-P":
        pcre = True
    elif x in ("-iE", "-Ei"):
        iflag = True; ext = True
    elif x == "-i":
        iflag = True
    elif x == "-E":
        ext = True
    elif x == "-F":
        fixed = True
    elif x == "-q":
        quiet = True
    elif x in ("-qF", "-Fq"):
        quiet = True; fixed = True
    elif x == "-o":
        oflag = True
    elif x.startswith("-"):
        pass
    elif pat is None:
        pat = x
# Everything after the pattern that is an existing file is a file operand.
files = [x for x in a if not x.startswith("-") and x is not pat and os.path.exists(x)]
flags = re.IGNORECASE if iflag else 0
flags |= re.MULTILINE
if fixed and pat is not None:
    pat = re.escape(pat)
rx = re.compile(pat, flags) if pat else None
if rx is None:
    sys.exit(0)
text = sys.stdin.read()
if files and text == "":
    parts = []
    for f in files:
        with open(f) as fh:
            parts.append(fh.read())
    text = "\n".join(parts)
matched = False
if oflag:
    for line in text.splitlines():
        m = rx.search(line)
        if m:
            matched = True
            if not quiet:
                print(m.group(0))
            break
else:
    for line in text.splitlines():
        if rx.search(line):
            matched = True
            if not quiet:
                print(line)
if quiet:
    sys.exit(0 if matched else 1)
sys.exit(0)
'''


def _cap_shim(case: dict) -> str:
    """Emit a ``cap`` shim that prints case['cap_stdout'] and exits cap_exit."""
    stdout = case["cap_stdout"]
    exit_code = case["cap_exit"]
    return (
        "#!/bin/sh\n"
        "cat <<'CAPEOF'\n" + stdout + "\nCAPEOF\n"
        f"exit {exit_code}\n"
    )


def _curl_shim(case: dict) -> str:
    """Emit a ``curl`` shim handling the step's exact invocation.

    The step calls::

        curl -sS -o "$confirm_body" -w '%{http_code}' -m 30 "$confirm_url"

    plus ``2>/dev/null``. The shim writes case['curl_body'] to the `-o` target
    and prints case['curl_status'] for the `-w` format. If case['curl_fail'] is
    true, it exits non-zero without writing anything (network/DNS/timeout).
    """
    if case.get("curl_fail"):
        return (
            "#!/bin/sh\n"
            "echo 'curl: (7) Failed to connect' >&2\n"
            "exit 7\n"
        )
    body = case["curl_body"]
    status = case["curl_status"]
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "outfile = None\n"
        "a = sys.argv[1:]\n"
        "i = 0\n"
        "while i < len(a):\n"
        "    if a[i] in ('-o', '--output'):\n"
        "        outfile = a[i+1]; i += 2\n"
        "    elif a[i] == '-m':\n"
        "        i += 2\n"
        "    elif a[i] in ('-w', '--write-out'):\n"
        "        i += 2\n"
        "    else:\n"
        "        i += 1\n"
        "body = " + repr(body) + "\n"
        "if outfile:\n"
        "    with open(outfile, 'w') as f:\n"
        "        f.write(body)\n"
        "print(" + repr(status) + ")\n"
        "sys.exit(0)\n"
    )


def run_step(body: str, case: dict) -> tuple[int, str, dict]:
    env = dict(os.environ)
    env["CAPACIUM_API_TOKEN"] = "test-token"
    body = fill_tokens(body)

    manifest = case.get("manifest", {})
    manifest_lines = ["name: " + manifest.get("name", "skillweave")]
    if "version" in manifest and manifest["version"] is not None:
        manifest_lines.append("version: " + str(manifest["version"]))
    if "owner" in manifest and manifest["owner"] is not None:
        manifest_lines.append("owner: " + str(manifest["owner"]))
    manifest_lines.append("kind: skill")
    manifest_lines.append("description: test")
    manifest_text = "\n".join(manifest_lines) + "\n"

    with tempfile.TemporaryDirectory() as d:
        shimdir = Path(d) / "bin"
        shimdir.mkdir()
        (shimdir / "cap").write_text(_cap_shim(case))
        (shimdir / "cap").chmod(0o755)
        (shimdir / "curl").write_text(_curl_shim(case))
        (shimdir / "curl").chmod(0o755)
        (shimdir / "grep").write_text(_grep_shim())
        (shimdir / "grep").chmod(0o755)
        (Path(d) / "capability.yaml").write_text(manifest_text)
        env["PATH"] = str(shimdir) + os.pathsep + env.get("PATH", "")
        out_file = Path(d) / "gh-out"
        env["GITHUB_OUTPUT"] = str(out_file)
        proc = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", body],
            capture_output=True, text=True, env=env, cwd=str(d),
        )
        outputs = {}
        if out_file.exists():
            for line in out_file.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    outputs[k] = v
        return proc.returncode, (proc.stdout + proc.stderr).strip(), outputs


# --- publish stdout fixtures -------------------------------------------------

OK_PUBLISH = (
    "Publishing skillweave/skillweave@1.5.2...\n"
    "Published: skillweave/skillweave\n"
    "  Kind: skill\n"
    f"  URL: {EXCHANGE_URL}\n"
    "  Trust state:   discovered\n"
    "  Quality score: 45/100\n"
)

OK_CONFIRM_BODY = (
    '{\n'
    '  "$schema": "https://capacium.xyz/schemas/capability-info.json",\n'
    '  "canonical_name": "skillweave/skillweave",\n'
    '  "name": "skillweave",\n'
    '  "owner": "skillweave",\n'
    '  "kind": "skill",\n'
    '  "trust_state": "discovered",\n'
    '  "version": "1.5.2",\n'
    '  "quality_score": 45\n'
    '}\n'
)

GOOD_MANIFEST = {"name": "skillweave", "version": "1.5.2", "owner": "skillweave"}


def ok_case(name, **kw):
    c = {
        "name": name,
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "200",
        "curl_body": OK_CONFIRM_BODY,
        "curl_fail": False,
        "expect": True,
        "msg_token": "",
    }
    c.update(kw)
    return c


CASES = [
    # -- the five recorded defeats (round two) — must now FAIL ----------------

    # 1. fabricated matching `cap info`: an honest Exchange does NOT have the
    #    version, but a lying cap served a fabricated confirm. With direct curl
    #    there is no cap info to fabricate; the Exchange 404 must fail.
    {
        "name": "defeat-fabricated-info",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": (
            "Publishing skillweave/skillweave@1.5.2...\n"
            "HTTP 403 Forbidden — the Exchange rejected this submission.\n"
            "Published: skillweave/skillweave\n"
            "  Kind: skill\n"
            f"  URL: {EXCHANGE_URL}\n"
        ),
        "cap_exit": 0,
        # honest Exchange: the version was never published -> 404, and its body
        # even echoes the queried canonical name (404 echo defeat folded in)
        "curl_status": "404",
        "curl_body": '{"detail": "Capability not found"}\n',
        "curl_fail": False,
        "expect": False,
        "msg_token": "returned HTTP 404",
    },
    # 2. info query fails and falls back to a cached answer: direct curl is the
    #    only channel; if the Exchange is unreachable, we fail (fail closed).
    {
        "name": "defeat-cached-fallback",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "",
        "curl_body": "",
        "curl_fail": True,
        "expect": False,
        "msg_token": "cannot confirm the publish",
    },
    # 3. 404 body that echoes the queried canonical: status is decisive, body
    #    is never trusted, so a 404 that echoes the name/version must fail.
    {
        "name": "defeat-404echo",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "404",
        "curl_body": (
            '{"detail": "Capability not found", "query": {'
            '"name": "skillweave", "owner": "skillweave", '
            '"version": "1.5.2"}}\n'
        ),
        "curl_fail": False,
        "expect": False,
        "msg_token": "returned HTTP 404",
    },
    # 4. success prose with no version token: the version now comes from the
    #    manifest, not the prose, so an omitted @version token is irrelevant.
    #    The Exchange here still lists the OLD version -> must fail.
    {
        "name": "defeat-no-version-prose",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": (
            "Publishing skillweave/skillweave (re-publish attempt)...\n"
            "Published: skillweave/skillweave\n"
            f"  URL: {EXCHANGE_URL}\n"
        ),
        "cap_exit": 0,
        "curl_status": "200",
        "curl_body": OK_CONFIRM_BODY.replace('"1.5.2"', '"1.5.1"'),
        "curl_fail": False,
        "expect": False,
        "msg_token": "not at the just-published version",
    },
    # 5. success prose claiming the OLD version while the new publish failed:
    #    the manifest demands 1.5.2, the Exchange still says 1.5.1 -> fail.
    {
        "name": "defeat-old-version-prose",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": (
            "Publishing skillweave/skillweave@1.5.1...\n"
            "Published: skillweave/skillweave\n"
            f"  URL: {EXCHANGE_URL}\n"
        ),
        "cap_exit": 0,
        "curl_status": "200",
        "curl_body": OK_CONFIRM_BODY.replace('"1.5.2"', '"1.5.1"'),
        "curl_fail": False,
        "expect": False,
        "msg_token": "not at the just-published version",
    },

    # -- THE CENTRAL TEST -----------------------------------------------------
    # a cap that lies in every way it can, combined with an HONEST Exchange that
    # does not have the version. The step must fail.
    {
        "name": "central-lying-cap-honest-exchange",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": (
            "Publishing skillweave/skillweave@1.5.2...\n"
            "Published: skillweave/skillweave\n"
            "  Kind: skill\n"
            f"  URL: {EXCHANGE_URL}\n"
            "  Trust state:   audited\n"
            "  Quality score: 99/100\n"
        ),
        "cap_exit": 0,
        "curl_status": "404",
        "curl_body": '{"detail": "Capability not found"}\n',
        "curl_fail": False,
        "expect": False,
        "msg_token": "returned HTTP 404",
    },

    # -- THE CONVERSE ---------------------------------------------------------
    # an honest publish + an Exchange that confirms the exact version -> pass,
    # all four outputs set.
    ok_case("converse-honest-pass"),

    # -- the three failure modes --------------------------------------------

    # Failure mode 1: confirmation request cannot be made (network fail).
    {
        "name": "failuremode-1-cannot-request",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "",
        "curl_body": "",
        "curl_fail": True,
        "expect": False,
        "msg_token": "cannot confirm the publish",
    },
    # Failure mode 1b: confirmation returns 5xx.
    {
        "name": "failuremode-1b-5xx",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "500",
        "curl_body": "",
        "curl_fail": False,
        "expect": False,
        "msg_token": "returned HTTP 500",
    },
    # Failure mode 2: 404 or non-matching version.
    {
        "name": "failuremode-2-404",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "404",
        "curl_body": '{"detail": "Capability not found"}\n',
        "curl_fail": False,
        "expect": False,
        "msg_token": "returned HTTP 404",
    },
    {
        "name": "failuremode-2-version-mismatch",
        "manifest": dict(GOOD_MANIFEST),
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "200",
        "curl_body": OK_CONFIRM_BODY.replace('"1.5.2"', '"1.5.1"'),
        "curl_fail": False,
        "expect": False,
        "msg_token": "not at the just-published version",
    },
    # Failure mode 3: no independent version known (manifest version empty).
    {
        "name": "failuremode-3-no-independent-version",
        "manifest": {"name": "skillweave", "version": "", "owner": "skillweave"},
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "200",
        "curl_body": OK_CONFIRM_BODY,
        "curl_fail": False,
        "expect": False,
        "msg_token": "no independent version known",
    },
    # Failure mode 3b: version field entirely absent from manifest.
    {
        "name": "failuremode-3b-version-absent",
        "manifest": {"name": "skillweave", "owner": "skillweave"},
        "cap_stdout": OK_PUBLISH,
        "cap_exit": 0,
        "curl_status": "200",
        "curl_body": OK_CONFIRM_BODY,
        "curl_fail": False,
        "expect": False,
        "msg_token": "no independent version known",
    },

    # -- green-path variants ------------------------------------------------

    # Explicit rejection + success lines, but Exchange genuinely lists the
    # correct version (impossible in reality — but the guard keys on the
    # Exchange, so a genuine listing passes). This documents that the guard
    # believes the Exchange, not the prose.
    ok_case("green-despite-hostile-prose",
            cap_stdout=(
                "HTTP 403 Forbidden — rejected.\n"
                "Published: skillweave/skillweave\n"
                f"  URL: {EXCHANGE_URL}\n"
                "  Trust state:   discovered\n"
                "  Quality score: 45/100\n"
            )),
]


def main():
    action_text = Path(ACTION).read_text()
    body = extract_publish_run(action_text)

    only = sys.argv[1] if len(sys.argv) > 1 else None
    failures = 0
    for case in CASES:
        if only and only not in case["name"]:
            continue
        rc, out, outputs = run_step(body, case)
        print(f"=== {case['name']} === (expect {'pass' if case['expect'] else 'fail'})")
        print(f"[manifest] {case.get('manifest')}")
        print(f"[cap exit {case['cap_exit']}] {case['cap_stdout']!r}")
        if case.get('curl_fail'):
            print("[curl] network/DNS/timeout failure")
        else:
            print(f"[curl] HTTP {case['curl_status']} body={case['curl_body']!r}")
        print("--- step output ---")
        print(out)
        print(f"exit code: {rc}")
        print(f"outputs: {outputs}")
        if case["expect"]:
            ok = (
                rc == 0
                and outputs.get("canonical_name") == CANONICAL
                and outputs.get("exchange_url") == EXCHANGE_URL
                and outputs.get("quality_score") == "45"
                and outputs.get("trust_state") == "discovered"
            )
            if not ok:
                print(">> FAIL: expected pass with all four outputs; got rc=%s outputs=%s" % (rc, outputs))
                failures += 1
            else:
                print(">> okay: passed and set all four outputs")
        else:
            if rc == 0:
                print(">> FAIL: expected step to fail, but it PASSED")
                failures += 1
            elif case["msg_token"] not in out:
                print(">> FAIL: reject message missing expected token %r" % case["msg_token"])
                failures += 1
            else:
                print(">> okay: rejected, names %r" % case["msg_token"])
        print()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
