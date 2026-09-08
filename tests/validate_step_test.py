#!/usr/bin/env python3
"""Post-condition test for the validate step.

Same shape as ``publish_step_test.py``: the step's shell body is reproduced
verbatim from ``action.yml`` and executed, so what is tested is what ships.

The defect this exists for: the step resolves ``cap_path`` in the shell and
proves the file exists, then hands the path to Python inside a **quoted**
heredoc (``<<'PYEOF'``). A quoted heredoc suppresses every expansion in its
body, so ``pathlib.Path("$cap_path")`` reached Python as those nine literal
characters and every consumer's publish died with

    FileNotFoundError: [Errno 2] No such file or directory: '$cap_path'

three lines after the shell had proven the file was there. The quoting is
correct and stays -- it is what keeps Python's own ``$`` and backslashes
intact. The path has to arrive by another route, and does: as ``sys.argv[1]``.

Usage:
    tests/validate_step_test.py
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ACTION = Path(__file__).resolve().parents[1] / "action.yml"
STEP_NAME = "Validate capability manifest"


def extract_validate_run(action_text):
    """Return the shell body of the validate step, de-indented."""
    steps = re.split(r"(?=^\s*- name:)", action_text, flags=re.M)
    for step in steps:
        if STEP_NAME in step.split("\n", 1)[0]:
            body = step.split("run:", 1)[1]
            if body.lstrip().startswith("|"):
                body = body.lstrip()[1:]
            lines = body.splitlines()
            # The base indent is the FIRST body line's, not the minimum over the
            # chunk: the chunk runs to the next `- name:` and so trails the
            # separator comment that precedes it, which sits four columns further
            # left. Taking the minimum would de-indent by four instead of eight
            # and leave every line indented -- and an indented `PYEOF` does not
            # terminate a `<<` heredoc, so the block would swallow the rest of the
            # script. Stop at the first line that dedents past the base.
            base = next(
                (len(l) - len(l.lstrip(" ")) for l in lines if l.strip()), 0
            )
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


def run_step(body, capability_path, manifest):
    """Run the step in a scratch workspace; return (exit code, combined output)."""
    with tempfile.TemporaryDirectory() as d:
        shim_dir = Path(d) / "bin"
        shim_dir.mkdir()
        # The action invokes `python`; not every runner spells it that way.
        shim = shim_dir / "python"
        shim.write_text("#!/bin/sh\nexec %s \"$@\"\n" % sys.executable)
        shim.chmod(0o755)

        if manifest is not None:
            (Path(d) / "capability.yaml").write_text(manifest)

        script = body.replace("${{ inputs.capability_path }}", capability_path)
        env = dict(
            os.environ,
            PATH="%s:%s" % (shim_dir, os.environ["PATH"]),
            GITHUB_WORKSPACE=d,
        )
        # `shell: bash` on a runner is `bash --noprofile --norc -e -o pipefail`.
        # Running without -e would let a step that prints ::error:: and exits
        # non-zero still finish green, because the trailing `echo ::endgroup::`
        # would set the exit code -- the harness would then disagree with the
        # runner about what passes.
        proc = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", script],
            cwd=d, env=env, capture_output=True, text=True,
        )
        return proc.returncode, proc.stdout + proc.stderr


VALID = "name: skillweave/skillweave\nversion: 1.5.3\nkind: bundle\n"
NO_KIND = "name: skillweave/skillweave\nversion: 1.5.3\n"

CASES = [
    # label, capability_path, manifest, must_pass, token the output must carry
    ("relative file path", "./capability.yaml", VALID, True, "is valid"),
    ("directory path", ".", VALID, True, "is valid"),
    ("bare filename", "capability.yaml", VALID, True, "is valid"),
    ("missing manifest refused", "./capability.yaml", None, False, "not found"),
    ("missing field refused", "./capability.yaml", NO_KIND, False, "Missing required field: kind"),
]


def main():
    body = extract_validate_run(ACTION.read_text(encoding="utf-8"))
    failures = 0
    for label, path, manifest, must_pass, token in CASES:
        code, out = run_step(body, path, manifest)
        ok = (code == 0) == must_pass and token in out
        print("%-4s %-26s exit=%d" % ("PASS" if ok else "FAIL", label, code))
        if not ok:
            failures += 1
            print("     expected %s carrying %r" % ("pass" if must_pass else "fail", token))
            for line in out.strip().splitlines()[-4:]:
                print("     | %s" % line)
    print("\n%d/%d cases passed" % (len(CASES) - failures, len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
