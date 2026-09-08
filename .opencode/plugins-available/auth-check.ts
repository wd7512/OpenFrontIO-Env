/** Optional plugin: warns the agent when common development tools are missing. */
import { execSync } from "child_process"

function probe(command: string) {
  try {
    execSync(command, { encoding: "utf-8", timeout: 10000, stdio: "pipe" })
    return true
  } catch {
    return false
  }
}

function checkTool(name: string, command: string, fix: string) {
  return probe(command) ? null : `- **${name}**: unavailable. ${fix}`
}

export const AuthCheck = async ({ client }: { client?: any }) => {
  const warnings = [
    checkTool("uv", "uv --version", "Install uv: https://docs.astral.sh/uv/"),
    checkTool("python", "python --version", "Install Python 3.11+."),
    checkTool("gh", "gh auth status", "Run `gh auth login` if GitHub access is needed."),
  ].filter(Boolean)

  for (const warning of warnings) {
    await client?.app?.log?.({
      body: { service: "auth-check", level: "warn", message: warning },
    })
  }

  return {
    "experimental.chat.system.transform": async (_input?: any, output?: any) => {
      if (warnings.length === 0 || !output || !Array.isArray(output.system)) return
      output.system.push(
        "## Tool Availability Warnings\n\n" +
          "Some common tools are unavailable or unauthenticated:\n\n" +
          warnings.join("\n"),
      )
    },
  }
}
