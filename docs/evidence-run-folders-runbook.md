# Evidence run-folders runbook (T4 dry-run port, keyless)

Every run flows: preflight → plan → harbor run → resume on failure →
reconcile gate → evidence. Evidence is written only on reconcile PASS;
never bless an unverified run.

## Preflight (keyless, no network)

```sh
uv run openfront-harbor preflight
```

## Plan (dry-run only, no live run)

```sh
uv run openfront-harbor plan \
  --config jobs/active/main-grid-openfront-amd64.yaml \
  --jobs-dir runs --run-id <run-id>
```

The plan prints the JSON artifact to stdout: job, ports (8801+), per-cell
ledger dirs under `runs/<run-id>/proxy-ledger/cell-<port>/`, and the
`harbor run --config <yaml> --jobs-dir runs/<run-id>` command the live
T9 wiring will execute.

## Harbor run (live; T9 wiring)

```sh
harbor run --config <yaml> --jobs-dir runs/<run-id>
```

On failure, resume (never restart into a fresh dir that would orphan the
proxy ledger):

```sh
harbor jobs resume -p runs/<run-id>/<job-name>
```

## Reconcile gate (ledger loss)

```sh
uv run openfront-harbor reconcile \
  --runs-dir runs --run-id <run-id> --ports 8801,8802,8803
```

Each expected cell must hold `ready.json` + `usage.jsonl`. Any gap is
loss: exit 1, no evidence.

## Evidence

```sh
uv run openfront-harbor evidence \
  --evidence-dir evidence --run-id <run-id> --gate-pass
```

Writes `evidence/<run-id>/summary.json` (run id, job, ports, gate
result — no secrets). Refuses to overwrite an existing dir.

## Hygiene

- `runs/` and `evidence/` are gitignored; never commit run artefacts.
- Never commit secrets (no API keys exist in this keyless skeleton).
