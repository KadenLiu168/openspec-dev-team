# Codex Capability Map

The Orchestrator uses the model selected for the parent session. Specialist
models and reasoning levels are fixed in `profiles/codex/agents/*.toml`; an
unavailable required model or reasoning level produces `BLOCKED` rather than a
silent substitution.

| Logical capability | Runtime mapping |
| --- | --- |
| `READ` | A parent-session MCP tool configured for read access to the required resource. |
| `WRITE` | A parent-session MCP tool configured and authorized to mutate the required resource. |

Agent definitions refer only to these logical capabilities. Deployments map
them to the parent session's configured MCP tools without embedding server
names in the reusable profiles. If a role requires a capability that is not
configured or authorized, it returns `BLOCKED` with evidence.

Filesystem sandbox settings and inherited parent-session tools are separate
controls. Sandbox inheritance is not process-level tool isolation; every role
must still obey its behavioral permission contract and explicit write
allowlist.
