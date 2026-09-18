# Brooks-lint (opt-in, OpenCode port)

Full `brooks-lint` suite (PR review, architecture audit, tech debt, test
quality, health dashboard, full sweep) — see `PROVENANCE.md`.
Kept opt-in so the default agent context stays lean.

## Enable

```bash
mkdir -p .opencode/skills .opencode/commands .opencode/plugins
cp -r .opencode/skills-available/brooks/skills/* .opencode/skills/
cp -r .opencode/skills-available/brooks/commands/* .opencode/commands/
cp -r .opencode/skills-available/brooks/plugins/* .opencode/plugins/
# -n: never overwrite an existing .brooks-lint.yaml
cp -n .opencode/skills-available/brooks/.brooks-lint.example.yaml .brooks-lint.yaml
```

Then edit `.brooks-lint.yaml` (all settings optional) and restart OpenCode.
