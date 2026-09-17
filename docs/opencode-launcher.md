# Isolated OpenCode launcher

`src/openfront_mcp/opencode_launcher.py` builds a self-contained OpenCode
configuration for the OpenFrontBench playing agent and launches it in a bounded,
isolated child process. `tests/test_opencode_launcher.py` is the executable
specification. No test makes a model call.

## Why isolation is not just `OPENCODE_CONFIG`

OpenCode **merges** configuration files rather than replacing them. Precedence
(highest last) is remote → global (`$HOME/.config/opencode/opencode.json`) →
custom (`OPENCODE_CONFIG`) → project (`opencode.json` found from cwd up to the
git root). Managed config from the OS sits above all of these.

So setting `OPENCODE_CONFIG` alone leaves two leaks:

1. The **global** config still merges in unless `HOME`/`XDG_CONFIG_HOME` are
   redirected.
2. A **project** `opencode.json` still merges over us and can re-enable tools
   unless the working directory is outside any git repository.
3. **Project plugins are discovered upward from the working directory.**
   Verified against the installed binary: a work dir under `Downloads`
   resolved `Downloads/.opencode/plugins` (7 plugins) into the isolated
   config. `prepare_run` therefore refuses any run root with a `.opencode`
   or `opencode.json` ancestor, and live runs use a fresh system temp dir
   for the agent — never a user-chosen output dir.
4. **The isolated run hides the host's refreshed model catalog.** OpenCode
   resolves run-time models from `XDG_CACHE_HOME/opencode/models.json`;
   the fresh isolated cache only has the bundled catalog, so a days-old
   model (`stealth/union-alpha`) was "not found" at run time even though
   the provider lists it. `seed_models_cache` copies the host's refreshed
   cache file into the isolated run (single file, fail-closed when absent).
   Verified: placeholder-key probe went from `ProviderModelNotFoundError`
   to a 401 from OpenRouter after seeding.

The launcher therefore redirects `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`,
`XDG_CACHE_HOME`, `XDG_STATE_HOME`, points `OPENCODE_CONFIG` at the generated
file, and refuses a run root inside a git repository.

## Fail-closed managed config

Managed config (`/Library/Application Support/opencode` and the
`ai.opencode.managed.plist` variants on macOS, `/etc/opencode` on Linux) can
override every other layer and cannot be excluded by any environment variable.
Its presence is a hard `ManagedConfigError` — the launcher refuses to start.

## Config contract

Generated config (`build_config`):

- `permission` (singular, not `permissions`): `{"*": "deny", "game_*": "allow"}`.
  Rules resolve **last-match-wins**, so the wildcard deny is listed first and
  the game MCP allow second. There is deliberately **no** `tools` map for the
  game server: that would be pinned ahead of the wildcard and invert ordering.
- custom `primary` agent named `game` with the same permission map, used as
  `default_agent`.
- `share: "disabled"`, `snapshot: false`, `autoupdate: false`.
- `mcp.game` as a `local` server with an absolute `command` argv, absolute
  `cwd`, and only its own non-secret `environment`.
- provider credential referenced as `{env:ANTHROPIC_API_KEY}`, never a literal.

The model lives in the config; `build_agent_command` produces
`opencode run --format json --agent game --pure <prompt>` with no `-m` /
`--model` flag. `--pure` disables external plugins (including this repo's
`write-size-guard.ts`).
## Run directory and environment

`prepare_run(root, config)` creates `home/`, `xdg/{config,data,cache,state}/`,
`config/opencode.json`, `work/` and writes `events.jsonl` there on launch. It
raises `IsolationError` if `root` is inside a git repository.

`build_isolated_env` copies only an allowlist of benign inherited variables
(`PATH`, locale, TLS certs, temp dirs) and rebuilds `HOME`/`XDG_*`/
`OPENCODE_CONFIG`. Every inherited `OPENCODE_*` variable and every provider key
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, …) is dropped.
`build_child_env` then injects **exactly one** key, named by `key_env_var`. A
missing or blank key raises `MissingApiKeyError` before any process starts, so a
run can never reach a game launch with no credential.

## Verification without a model call

`verify_resolved_config` runs `opencode debug config --pure` (which resolves the
merged config but makes no model request) with a placeholder key, parses the
JSON, and asserts the resolved `model`, `share`, `snapshot`, `autoupdate`,
`default_agent`, permission map, sole `mcp` server, and empty plugin list. It
fails if any secret literal appears in the resolved output. This catches merge
leakage that a static check of the generated file would miss.

## Bounded execution

`run_bounded` starts the child with `start_new_session=True`, so the child
becomes its own session/process-group leader and the group id **is
`proc.pid`**. It enforces `timeout_s`; on expiry it cleans up the group, then
drains the captured pipes under a final bound, so the call always returns.

Cleanup is group-wide, not leader-wide. The leader exiting first is **not**
treated as success, because a descendant can outlive it and keep the inherited
stdout/stderr pipes open. Concretely, on expiry:

1. `SIGTERM` the whole group;
2. wait up to `TERMINATE_GRACE_S` (5s) for the **whole group** to become empty,
   polling with `os.killpg(pgid, 0)` — the leader's exit alone does not end
   this wait;
3. `SIGKILL` the whole group if anything remains, and wait out a second
   bounded grace;
4. drain `communicate(timeout=TERMINATE_GRACE_S)` so a still-open inherited
   pipe cannot block forever.

The worst-case return bound is therefore `timeout_s` plus at most three
bounded graces (TERM wait, KILL wait, final drain); a normal timeout where the
group dies on `SIGTERM` returns almost immediately after `timeout_s`.

**Scope of the guarantee.** Cleanup covers processes that stay in the child's
process group, which is what OpenCode's own children, shell pipelines and
ordinary `Popen` descendants do. It is *not* an OS sandbox: a process that
deliberately escapes the group (`setsid`, a new session, a daemon that
double-forks) is outside the group and is not reclaimed. The launcher does not
attempt to constrain that.

Captured stdout and stderr are redacted with `redact` before being returned,
before being persisted to `events_path`, and before logging — a secret echoed
by the child never reaches the caller or the events file. Resolved-config
verification passes `redact_output=False` so it can still inspect the raw bytes
for a leaked secret. `launch_playing_agent` composes the whole flow:
managed-config check → key check → config → verify → launch, and returns the
run layout, generated config, resolved config and the process result together
for auditing.

## Event fixtures are scripted

`SCRIPTED_EVENT_LINES` in the tests is a hand-written JSON event stream, not
output from any real model. The only test touching the real binary is
`test_verify_resolved_config_against_real_opencode`, which runs
`opencode debug config` (no model call) and is skipped when `opencode` is absent.
## TDD evidence

Tests were written first. With no implementation present, collection failed as
expected:

```
$ uv run pytest tests/test_opencode_launcher.py -q
tests/test_opencode_launcher.py:33: in <module>
    from openfront_mcp import opencode_launcher as ol
E   ImportError: cannot import name 'opencode_launcher' from 'openfront_mcp'
=========================== short test summary info ============================
ERROR tests/test_opencode_launcher.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.04s
```

Implementation followed, then all 27 launcher tests passed:

```
$ uv run pytest tests/test_opencode_launcher.py -v
...
tests/test_opencode_launcher.py::test_verify_resolved_config_against_real_opencode PASSED
tests/test_opencode_launcher.py::test_launch_requires_a_key_before_running_anything PASSED
tests/test_opencode_launcher.py::test_launch_verifies_then_runs_with_scripted_events PASSED
tests/test_opencode_launcher.py::test_launch_logs_never_contain_the_secret PASSED
============================== 27 passed in 1.51s ==============================
```

Real-binary verification (no model call) passed against the installed OpenCode:

```
$ uv run pytest "tests/test_opencode_launcher.py::test_verify_resolved_config_against_real_opencode" -q
1 passed
```

Full suite, lint, format and type check:

```
$ uv run pytest -q
40 passed in 2.19s

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
21 files already formatted

$ uv run ty check
All checks passed!
```

### Output-redaction bug fix (TDD)

`run_bounded` previously returned and persisted **raw** child output — the
secret was redacted only in log lines. The behavioural test below was appended
first and failed (RED) against that code:

```
$ uv run pytest "tests/test_opencode_launcher.py::test_run_bounded_redacts_secrets_from_output_and_persisted_events" -q
F                                                                        [100%]
FAILED tests/test_opencode_launcher.py::test_run_bounded_redacts_secrets_from_output_and_persisted_events
```

The minimal fix redacts stdout/stderr before returning and before writing
`events_path`, and adds `redact_output=False` to the resolved-config
verification call so its raw-bytes leak detection still fires. The same test
then passed (GREEN):

```
$ uv run pytest "tests/test_opencode_launcher.py::test_run_bounded_redacts_secrets_from_output_and_persisted_events" -q
1 passed in 0.02s
```

Full suite, lint, format and type check after the fix:

```
$ uv run pytest -q
41 passed in 2.44s

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
21 files already formatted

$ uv run ty check
All checks passed!
```

### Process-group cleanup bug fix (TDD)

`_terminate_process_group` previously did `proc.wait(timeout=grace_s)` after
`SIGTERM` and returned as soon as the **leader** exited. A descendant that
ignored `SIGTERM` and kept the inherited stdout pipe open was therefore never
`SIGKILL`ed, and the following `proc.communicate()` blocked forever waiting for
EOF — `run_bounded` could hang without bound.

Two behavioural tests were appended first and run against that code. Each
spawns, through the launcher, a real Python leader that starts a real Python
descendant which ignores `SIGTERM` and holds the inherited stdout pipe; one
leader dies on `SIGTERM`, the other exits naturally. Both calls are made behind
a harness with its own outer subprocess timeout that `SIGKILL`s the outer group
(and any fixture pid) in a `finally`, so the RED run fails instead of hanging
and leaks nothing:

```
$ uv run pytest \
  "tests/test_opencode_launcher.py::test_run_bounded_escapes_when_leader_dies_on_term_but_descendant_holds_stdout" \
  "tests/test_opencode_launcher.py::test_run_bounded_escapes_when_leader_exits_naturally_leaving_descendant" -q
...
E       AssertionError: (outer timeout)
E       assert True is not True
FAILED tests/test_opencode_launcher.py::test_run_bounded_escapes_when_leader_dies_on_term_but_descendant_holds_stdout
FAILED tests/test_opencode_launcher.py::test_run_bounded_escapes_when_leader_exits_naturally_leaving_descendant
2 failed in 40.08s
```

The minimal fix identifies the group by `proc.pid` (the child is started with
`start_new_session=True`), waits for the **whole group** to clear with
`os.killpg(pgid, 0)` polling bounded by `TERMINATE_GRACE_S`, escalates to
`SIGKILL` on the group when it does not, and bounds the final
`communicate(timeout=TERMINATE_GRACE_S)`. Both tests then passed (GREEN):

```
$ uv run pytest \
  "tests/test_opencode_launcher.py::test_run_bounded_escapes_when_leader_dies_on_term_but_descendant_holds_stdout" \
  "tests/test_opencode_launcher.py::test_run_bounded_escapes_when_leader_exits_naturally_leaving_descendant" -q
2 passed in 12.23s
```

Full suite, lint, format and type check after the fix (30 launcher tests):

```
$ uv run pytest -q
43 passed in 14.49s

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
21 files already formatted

$ uv run ty check
All checks passed!
```
