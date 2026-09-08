/** Optional plugin: logs session lifecycle events to .opencode/metrics. */
import { appendFileSync, mkdirSync } from "fs"
import { dirname, join, resolve } from "path"
import { randomUUID } from "crypto"

const SESSION_EVENT_TYPES = new Set([
  "session.created",
  "session.idle",
  "session.compacted",
  "session.deleted",
  "session.error",
  "session.status",
  "session.updated",
])

function appendJsonl(filePath: string, obj: Record<string, unknown>) {
  mkdirSync(dirname(filePath), { recursive: true })
  appendFileSync(filePath, JSON.stringify(obj) + "\n", "utf-8")
}

export const SessionLifecycle = async ({ directory }: { directory: string }) => {
  const outPath = join(resolve(directory), ".opencode", "metrics", "session-events.jsonl")
  const sessionId = randomUUID()
  let sessionStart: number | null = null
  let compactionCount = 0

  function log(eventName: string, extra: Record<string, unknown> = {}) {
    appendJsonl(outPath, {
      ts: new Date().toISOString(),
      session_id: sessionId,
      event: eventName,
      ...extra,
    })
  }

  return {
    event: async (ctx?: any) => {
      try {
        const event = ctx?.event
        if (!event || !SESSION_EVENT_TYPES.has(event.type)) return
        if (event.type === "session.created") sessionStart = Date.now()
        if (event.type === "session.compacted") compactionCount++
        log(event.type.replace(".", "_"), {
          duration_ms:
            event.type === "session.idle" && sessionStart
              ? Date.now() - sessionStart
              : undefined,
          compaction_count:
            event.type === "session.compacted" ? compactionCount : undefined,
        })
      } catch {
        // Telemetry must not break the session.
      }
    },
  }
}
