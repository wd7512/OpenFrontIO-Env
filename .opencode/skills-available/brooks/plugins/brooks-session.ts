/**
 * Brooks-lint opt-in session plugin (OpenCode port).
 *
 * Replaces the Claude Code `hooks/hooks.json` SessionStart hook
 * (`node "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.mjs"`), which cannot
 * resolve under OpenCode, plus the `~/.claude/commands` installer in
 * `session-start.mjs`. In OpenCode, skills/commands are enabled by copying
 * them into `.opencode/skills/` and `.opencode/commands/` (see
 * `skills-available/brooks/README.md`), where native skill discovery picks
 * them up — no install step or path baking needed.
 *
 * On `session.created` this appends `{ts, session_id, event}` to
 * `.opencode/metrics/brooks-session.jsonl` and logs the skill index via
 * `client.app.log`, for observability. Intentionally not replicated: the
 * Claude hook injected the index as agent-visible `additionalContext` —
 * under OpenCode that is unnecessary because native skill discovery lists
 * the six skills to the agent once the bundle is enabled (see
 * `skills-available/brooks/README.md`). Telemetry must never break the
 * session.
 */
import { appendFileSync, mkdirSync } from "fs"
import { dirname, join, resolve } from "path"
import { randomUUID } from "crypto"

const SKILL_INDEX = [
  "You have the brooks-lint plugin installed. It provides six independent skills - load the relevant one via the Skill tool:",
  "  brooks-review  -> PR code review",
  "  brooks-audit   -> Architecture audit",
  "  brooks-debt    -> Tech debt assessment",
  "  brooks-test    -> Test quality review",
  "  brooks-health  -> Codebase health dashboard",
  "  brooks-sweep   -> Full sweep: analyse all dimensions and auto-fix findings",
  "",
  "Triggers when the user asks to review code, discuss architecture, assess tech debt, or discuss test quality. Each skill's own description carries its full trigger phrases and exclusions.",
].join("\n")

export const BrooksSession = async ({
  directory,
  client,
}: {
  directory: string
  client?: any
}) => {
  const instanceId = randomUUID()

  return {
    event: async (ctx?: any) => {
      if (ctx?.event?.type !== "session.created") return
      // Prefer the real OpenCode session ID; fall back to this plugin
      // instance's ID when the event payload shape is unexpected.
      const sessionId = ctx?.event?.properties?.info?.id ?? instanceId

      try {
        const out = join(
          resolve(directory),
          ".opencode",
          "metrics",
          "brooks-session.jsonl",
        )
        mkdirSync(dirname(out), { recursive: true })
        appendFileSync(
          out,
          JSON.stringify({
            ts: new Date().toISOString(),
            session_id: sessionId,
            event: "session_created",
          }) + "\n",
          "utf-8",
        )
      } catch {
        // Telemetry must not break the session.
      }

      try {
        await client?.app?.log?.({
          body: {
            service: "brooks-session",
            level: "info",
            message: SKILL_INDEX,
            extra: { session_id: sessionId },
          },
        })
      } catch {
        // Telemetry must not break the session.
      }
    },
  }
}
