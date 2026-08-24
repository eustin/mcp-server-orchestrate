# Bug Report — `orchestrate_verify` test runner executes wrong command (`/bin/sh: Bad for loop variable`)

**Reported:** 2026-08-25
**Affected tool:** `orchestrate_verify` → `VerificationEngine.verify_testing` (automated test-runner subprocess)
**Severity:** High (Phase 4 gate cannot run the intended test; may execute garbage as a shell command)
**Component:** `src/orchestrator_mcp/verifier.py` — `TEST_COMMAND_REGEX` (line 7-10) + `verify_testing` (line 141-176)
**Status:** Open

---

## Summary

The Phase 4 automated test-runner (`orchestrate_verify`) fails with:

```
Automated test runner failed (Exit Code 2):
/bin/sh: 1: Syntax error: Bad for loop variable
```

It does NOT run the plan's `Test command: uv run pytest tests/research/test_cfi_corrected.py -x -v`.
Instead, `TEST_COMMAND_REGEX` matches an unrelated bullet from the plan body —
`- **Test command for self-verification**: \`uv run pytest ...\`` in the T8 task spec —
captures `for self-verification**: \`uv run pytest ...\`` as the "test command", and
passes it to `subprocess.run(..., shell=True)`. `/bin/sh` parses the leading
`for self-verification**` as a `for` loop with an invalid variable name, emitting
`Syntax error: Bad for loop variable` and exiting 2.

Observed 3× in one session (reproduced identically before AND after simplifying the
plan's `## Verification` section to a single `Test command:` line — because the real
`Test command:` line is itself never matched, see Secondary defect).

---

## Root cause

`verifier.py:7-10`:

```python
TEST_COMMAND_REGEX = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?Test command:?(?:\*\*)?:?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)
```

**Primary defect — too loose match, grabs a bullet mid-plan:**

`Test command:?` matches the literal string `Test command` even when followed by more
words (`for self-verification**`), because the `:` is optional and there is no word
boundary. With `re.MULTILINE | re.IGNORECASE`, any line that begins (after optional
`- ` / `**`) with the case-insensitive string `Test command` is accepted, regardless of
what follows. The plan's T8 task spec contains exactly such a line:

```
- **Test command for self-verification**: `uv run pytest tests/research/test_cfi_corrected.py -x -v`
```

`re.search` returns the FIRST hit in the document; since the genuine `Test command:` line
is later (or unparseable, see below), the T8 bullet wins. Verified capture:

```
line 456: captured='for self-verification**: `uv run pytest tests/research/test_cfi_corrected.py -x -v`'
test_cmd after strip('`').strip(): 'for self-verification**: `uv run pytest tests/research/test_cfi_corrected.py -x -v'
```

`strip("\`")` only removes backticks at the string ends, so the embedded backtick before
`uv run` and the label text remain. `verify_testing` (line 160-169) then runs:

```python
subprocess.run(test_cmd, shell=True, cwd=root, ...)
```

`/bin/sh -c 'for self-verification**: `uv run pytest ... -x -v'` → dash parses the
`for` keyword with the invalid variable `self-verification**` → `Syntax error: Bad for
loop variable` (exit 2).

**Secondary defect — the intended format is never matched either:**

A well-formed `Test command:` embedded in a labeled bullet is not matched at all:

```
- Primary: `Test command: uv run pytest tests/research/test_cfi_corrected.py -x -v`
```

After `^\s*(?:-\s*)?(?:\*\*)?` the regex requires `Test command` immediately, but the
line has `Primary: ` first. So a plan using the label style yields
`Missing required 'Test command: <cmd>'` (or, as here, silently falls through to the
first loose match). The regex effectively only works when `Test command:` is the very
first token of a line — the exact style the server's own PLAN prompt prescribes
(`Test command: <cmd>`), but which real-world plans deviate from.

**Aggravating factor — `shell=True` on a regex-captured string:**

Whatever the regex captures is executed verbatim by `/bin/sh`. Any markdown residue
(backticks, labels, `**bold**`, parentheticals) becomes shell syntax. This is also an
injection surface if a plan is ever authored by an untrusted source.

---

## Reproduction

1. Write a plan whose body contains a bullet starting with `**Test command for ...**`
   (e.g. a task spec line `- **Test command for self-verification**: \`<cmd>\``) and a
   `## Verification` section that is either absent, uses the `- Label: \`Test command:
   <cmd>\`` style, or is otherwise not the first match.
2. Run `orchestrate_verify`.

**Expected:** the runner executes `uv run pytest tests/research/test_cfi_corrected.py -x -v`.

**Actual:**

```
"Automated test runner failed (Exit Code 2):\n\n/bin/sh: 1: Syntax error: Bad for loop variable"
```

Direct reproduction of the extraction (python):

```python
import re
RX = re.compile(r"^\s*(?:-\s*)?(?:\*\*)?Test command:?(?:\*\*)?:?\s*(.+)$",
                re.MULTILINE | re.IGNORECASE)
# first hit in a plan containing the T8-style bullet:
m = RX.search("- **Test command for self-verification**: `uv run pytest x.py -v`")
print(repr(m.group(1).strip().strip("`").strip()))
# → 'for self-verification**: `uv run pytest x.py -v'
```

---

## Impact

1. **Phase 4 gate blocked** — `orchestrate_verify` cannot return success even though the
   real test suite passes; the Orchestration Lead must fall back to running the test
   commands manually and rely on auditor evidence.
2. **Wrong command execution** — arbitrary plan text can be executed via `shell=True`
   (here: a harmless syntax error; in the worst case, plan-authored markdown injected
   into the shell).
3. **Silent mis-verification risk** — if a loose match happens to look like a valid shell
   command, the runner could run the WRONG command and report pass/fail for it.

---

## Suggested fix

Require the colon + word boundary so the token `Test command:` is exact, and keep the
label/`\``/`**` tolerated only in a controlled way. Minimal change in `verifier.py:8`:

```python
TEST_COMMAND_REGEX = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?Test command\s*:\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
```

- `\s*:` makes the colon mandatory → `Test command for self-verification**` no longer
  matches (the next token after `command` is ` for`, not `:`).
- Keep MULTILINE (line-anchored), drop the permissive `(?:\*\*)?:?` suffix duplication.
- For the `- Primary: \`Test command: ...\`` style, either (a) document that the plan
  MUST use a bare `Test command: <cmd>` line (the server's own PLAN prompt already
  prescribes this), or (b) extend the regex to skip a label:
  `r"^\s*(?:-\s*)?(?:\*\*)?(?:[^:\n]*?:)?\s*\`?Test command\s*:\s*(.+?)\s*\`?$"`.

Also harden `verify_testing` (line 154-176):

- After extraction, assert the command matches a safe-command whitelist
  (e.g. `^[A-Za-z0-9_./\\ -]+$` — no backticks, `$()`, `;`, `&&`, `|`, `>`) and raise a
  clear validation error instead of handing arbitrary text to `/bin/sh`.
- Strip stray backticks/trailing text defensively (`.replace("\`", "")` on the captured
  group, not just `.strip("\`")`).

Add unit tests asserting, for both inputs below, the extracted command equals
`uv run pytest tests/research/test_cfi_corrected.py -x -v`:

- `Test command: uv run pytest tests/research/test_cfi_corrected.py -x -v`
- `- **Test command for self-verification**: \`uv run pytest tests/research/test_cfi_corrected.py -x -v\``
  (must NOT match — this is the regression that fired here)

---

## Workaround (until fixed)

Orchestration Lead: do not rely on `orchestrate_verify`'s automated runner. Execute the
plan's `Test command:` directly in the shell and verify exit code 0, and rely on
independent auditor evidence (tester / implementation-reviewer subagent outputs). Keep
the plan's `## Verification` `Test command:` on its own line with no `- Label:` prefix
and no other `**Test command ...**` bullets earlier in the document.
