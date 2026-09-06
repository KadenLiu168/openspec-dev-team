# Claude Code Mapping Template

Status: `template-only`. Confirm all fields against the installed Claude Code
version before use; this repository has not verified the complete workflow on
Claude Code.

## Discovery

- Install the skill at `~/.claude/skills/openspec-dev-team/SKILL.md` for user
  scope, or `.claude/skills/openspec-dev-team/SKILL.md` for project scope.
- Install subagent definitions under `~/.claude/agents/` for user scope, or
  `.claude/agents/` for project scope.
- Definitions reference the shared role contracts and `.agents/project.md`;
  they do not copy those files into each project.

## Fresh context and fields

Dispatch a new subagent for each serial phase and pass only the contract fields
and artifact paths. Do not include the parent conversation or reuse a prior
specialist context.

Map these values explicitly in each local definition:

| Required value | Claude Code mapping |
| --- | --- |
| Agent name and instructions | Subagent name, description, and prompt body |
| Model and reasoning | Available model selector and effort control |
| `READ` / `WRITE` | Tool allowlist and permission policy |
| Filesystem boundary | Permission mode and project settings |

Missing required model or tool capability returns `BLOCKED`; it must not fall
back silently.

## Why subagents, not Agent Teams

The pipeline is serial: one state has one owner, and every transition consumes
a validated handoff. Independent subagents provide fresh context without
introducing a shared task board or direct specialist-to-specialist messaging.
Those Agent Team features add coordination paths that conflict with the
Orchestrator's sole-routing contract.
