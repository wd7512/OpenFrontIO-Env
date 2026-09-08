/** Optional plugin: logs tool usage to .opencode/metrics/tool-calls.jsonl. */
import { appendFileSync, mkdirSync } from "fs"
import { dirname, join, resolve } from "path"
import { randomUUID } from "crypto"

const FILE_TOOLS = new Set(["read", "glob", "grep", "edit", "write", "apply_patch"])

function appendJsonl(filePath: string, obj: Record<string, unknown>) {
  mkdirSync(dirname(filePath), { recursive: true })
  appendFileSync(filePath, JSON.stringify(obj) + "\n", "utf-8")
}

function classifyTool(toolName: string) {
  if (toolName === "bash") return "bash"
  if (FILE_TOOLS.has(toolName)) return "file"
  if (toolName === "webfetch" || toolName === "websearch") return "web"
  if (toolName === "task") return "subagent"
  if (toolName === "skill") return "skill"
  return "other"
}

function extractMeta(toolName: string, args: Record<string, any>) {
  if (toolName === "bash") return { command_preview: (args.command || "").slice(0, 200) }
  if (toolName === "skill") return { skill_name: args.name || "" }
  if (toolName === "task") return { subagent_type: args.subagent_type || "" }
  if (args.filePath) return { file_path: args.filePath }
  if (args.pattern) return { pattern: args.pattern }
  return {}
}

export const ToolObserver = async ({ directory }: { directory: string }) => {
  const outPath = join(resolve(directory), ".opencode", "metrics", "tool-calls.jsonl")
  const sessionId = randomUUID()
  let callCounter = 0
  const inflight = new Map<string, Array<{ callId: string; start: number }>>()

  return {
    "tool.execute.before": async (input?: any, output?: any) => {
      try {
        const toolName = input?.tool || "unknown"
        const args = input?.args || output?.args || {}
        const callId = `${toolName}-${++callCounter}`
        if (!inflight.has(toolName)) inflight.set(toolName, [])
        inflight.get(toolName)?.push({ callId, start: Date.now() })
        appendJsonl(outPath, {
          ts: new Date().toISOString(),
          session_id: sessionId,
          tool: toolName,
          type: classifyTool(toolName),
          call_id: callId,
          ...extractMeta(toolName, args),
        })
      } catch {
        // Telemetry must not break tool execution.
      }
    },
    "tool.execute.after": async (input?: any, output?: any) => {
      try {
        const toolName = input?.tool || "unknown"
        const stack = inflight.get(toolName)
        const frame = stack && stack.length ? stack.pop() : null
        appendJsonl(outPath, {
          ts: new Date().toISOString(),
          session_id: sessionId,
          tool: toolName,
          event: "after",
          call_id: frame ? frame.callId : null,
          duration_ms: frame ? Date.now() - frame.start : null,
          success: output?.error == null,
        })
      } catch {
        // Telemetry must not break tool execution.
      }
    },
  }
}
