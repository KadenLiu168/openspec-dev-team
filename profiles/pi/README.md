# Pi Mapping Template

Status: `template-only`. Confirm all fields against the installed Pi version
before use; this repository has not verified the complete workflow on Pi.

## Discovery

- Install the reusable skill at `~/.pi/agent/skills/openspec-dev-team/SKILL.md`
  for user scope, or `.pi/skills/openspec-dev-team/SKILL.md` for project scope.
- Put adapter-owned agent definitions in the custom-agent or extension
  discovery location selected by the local Pi installation; record that path
  as `AGENT_DEFINITIONS_DIR` rather than copying role contracts per project.
- Keep `agents/shared/` and `.agents/project.md` at the paths referenced by
  each definition; deleted team-role files are not required.

## Fresh context and fields

Start one isolated subagent session for each serial phase. Supply only the
dispatch fields and artifact paths defined by the workflow contract; do not
copy the parent conversation.

Map these values explicitly in the local adapter:

| Required value | Pi mapping |
| --- | --- |
| Agent name and instructions | Local custom-agent or extension definition |
| Model and reasoning | Installed provider/model identifier and effort control |
| `READ` / `WRITE` | Locally configured tools with matching authorization |
| Filesystem boundary | Local tool and sandbox policy |

Missing required model or tool capability returns `BLOCKED`; it must not fall
back silently.

## Why subagents

This workflow has one owner per state, digest-bound handoffs, and ordered Human
Gates. Isolated serial subagents preserve those boundaries. A shared Agent Team
would add a shared task list and peer communication that this pipeline neither
uses nor permits.
