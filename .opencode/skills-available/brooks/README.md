# Brooks-lint (opt-in)

Full `brooks-lint` suite (PR review, architecture audit, tech debt, test
quality, health dashboard, full sweep) vendored verbatim — see `PROVENANCE.md`.
Kept opt-in so the default agent context stays lean.

## Enable

```bash
cp -r .opencode/skills-available/brooks/skills/* .opencode/skills/
cp -r .opencode/skills-available/brooks/commands/* .opencode/commands/
cp .opencode/skills-available/brooks/.brooks-lint.example.yaml .brooks-lint.yaml
```

Then edit `.brooks-lint.yaml` (all settings optional) and restart OpenCode.
