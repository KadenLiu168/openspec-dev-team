# Repository Instructions

## Project Scope

本仓库是 **Codex CLI-only** 的 OpenSpec 多 Agent 开发团队工具。支持边界为：

- Codex 原生 custom-agent profiles；
- OpenSpec 驱动的需求、设计、实施和验证生命周期；
- 在目标项目 `main` 分支上串行运行的五个 specialist profiles。

Authored Codex specialist profiles are maintained under `profiles/codex/agents/`, which is the canonical source.

`profiles/pi/README.md` 和 `profiles/claude-code/README.md` 仅是
**template-only platform mappings**，不表示本仓库支持 Pi、Claude Code adapter、
通用 Agent runtime 或多平台 Agent 协议。

## Stable Guardrails

- OpenSpec artifacts 是生命周期和实现范围的事实来源。实质性修改必须对应一个经过审查和批准的 OpenSpec Change，并保持在其 Scope 内。
- 保留 Human control：Agent 不得绕过 Human Gate、伪造授权、自动扩大范围，或替人作出需要人工决定的发布决策。
- 修改前先阅读相关 Change 和 canonical source；只编辑明确授权的路径，不要顺手修改无关的 profile、skill、script、test、spec 或 archived Change。
- 所有工作在目标项目的 `main` 上串行进行；不要创建 branch 或 worktree。
- 保留既有 tracked changes 和非忽略 untracked files；不要覆盖、删除或提交不属于当前 allowlist 的内容。
- Git/runtime 安全优先：不要使用 `git add .`、`git add -A`、`reset`、`clean`、force-push 或 history rewrite；不要用 pull、merge 或 rebase 掩盖异常。遇到 dirty state、非法路由、未解决 blocker 或授权异常时应停下并升级处理。
- 不手工绕过可执行的 state、handoff、digest 或 receipt 校验；运行时事实由其 canonical owner 维护。

## Canonical Sources by Concern

| Concern | Canonical source |
| --- | --- |
| Specialist identity, model, sandbox and role instructions | `profiles/codex/agents/*.toml` |
| Logical `READ`/`WRITE` capability mapping | `profiles/codex/model-map.md` |
| Orchestration entry point and dispatch behavior | `skills/openspec-dev-team/SKILL.md` |
| State/event routing and publishing-step reference | `skills/openspec-dev-team/references/state-machine.md` |
| Cross-Agent workflow boundaries | `agents/shared/workflow-policy.md` |
| Handoff fields, digests and acceptance rules | `agents/shared/handoff-contract.md` |
| Executable state and handoff enforcement | `scripts/workflow-state.py` |
| Installation and project bootstrap behavior | `README.md`, `scripts/link-project.sh`, `templates/project.md` |
| Global/project diagnostics | `scripts/doctor.sh` |
| Requirements, design, tasks and lifecycle configuration | `openspec/config.yaml`, `openspec/specs/`, `openspec/changes/` |
| Regression and contract evidence | `tests/` |
| Unverified platform mappings (template-only) | `profiles/pi/README.md`, `profiles/claude-code/README.md` |

The five TOMLs under `profiles/codex/agents/` are the authored specialist
sources. Installed copies and project-owned `.agents` configuration are
deployment/project data, not additional role definitions. Update the relevant
canonical source instead of copying its runtime facts into this file.

## Change Boundaries

本文件是稳定的 repository guardrail 和 navigation layer，不是完整的 architecture
specification、role contract、state-machine reference、installation manual 或 CLI
reference。详细的 Agent instructions、state transitions、handoff rules、bootstrap
procedures 和 executable validation 必须留在上表所列的 owner 中。

本仓库当前 Change 的实现应保持最小、可审查且可回滚；不要为未来平台、配置格式或
runtime 引入未获批准的 adapter、registry、generated file 或 dependency。外部项目
管理系统不属于本仓库 Change 的默认修改范围。

## Verification Expectations

完成修改后，确认所有新引用的 authored paths 仍存在，运行适用的 `tests/`，
run applicable diagnostics using their documented invocation，并执行 OpenSpec strict
validation；检查最终 diff 只包含批准范围内的文件。文档对齐不得通过修改测试或运行时
行为来“修复”验证结果。
