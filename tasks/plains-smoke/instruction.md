# Plains Smoke

Run the keyless smoke benchmark and report its outcome.

1. Run the scripted episode with the bundled smoke config:
   `python -m openfrontbench.benchmark --config examples/smoke.json --output /app/output`
2. Confirm `/app/output/result.json` exists and record its `outcome`,
   `decisions_taken`, `tick_start`, and `tick_end` in your summary.
3. Do not require any API key: the `scripted` controller makes every decision.
