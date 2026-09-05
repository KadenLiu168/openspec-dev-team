# OpenSpec Dev Team 设计

## 目标

在 `~/openspec-dev-team` 维护一套跨项目复用的开发 Agent Team。当前 Codex 主 session 担任 Orchestrator，按 OpenSpec 生命周期串行调度 5 个专业 sub-agent：

```text
Explore -> Human Approval -> Propose -> Proposal Review
        -> Apply -> Pre-Archive Audit -> Archive / Publish
```

OpenSpec 是 lifecycle 和 implementation 的唯一 source of truth。Superpowers 只提供局部质量方法，不建立第二套 spec、plan 或状态体系。

首版要求 Codex 可实际运行。Pi 与 Claude Code 只提供简短 capability mapping，不承诺端到端兼容。

## 非目标

- 不实现独立 orchestration service、dashboard、共享 mailbox 或通用 plugin framework。
- 不复制 OpenSpec prompt 的完整内容。
- 不通过完整 conversation history 交接。
- 不重复扫描整个 repo，也不为多 Agent 强制并行。
- 不为每个项目复制同一套 Agent 文件。

## 项目布局

```text
~/openspec-dev-team/
├── agents/
│   ├── shared/
│   │   ├── workflow-policy.md
│   │   └── handoff-contract.md
│   └── team/
│       ├── orchestrator.md
│       ├── explore-proposal.md
│       ├── proposal-reviewer.md
│       ├── apply-executor.md
│       ├── pre-archive-auditor.md
│       └── archivist-publisher.md
├── skills/
│   └── openspec-dev-team/
│       ├── SKILL.md
│       └── references/
│           └── state-machine.md
├── profiles/
│   ├── codex/
│   │   ├── agents/
│   │   └── model-map.md
│   ├── pi/
│   │   └── README.md
│   └── claude-code/
│       └── README.md
├── templates/
│   └── project.md
├── scripts/
│   ├── link-project.sh
│   ├── doctor.sh
│   └── workflow-state.py
├── tests/
└── README.md
```

完成验证后创建：

```text
~/.codex/skills/openspec-dev-team
  -> ~/openspec-dev-team/skills/openspec-dev-team
```

Codex custom-agent 配置由 `profiles/codex/agents/` 链接至 `~/.codex/agents/`。

## 架构

```text
Current Codex Session
  Orchestrator + openspec-dev-team skill
            |
            +-- Explore / Proposal Agent
            +-- Proposal Reviewer
            +-- Apply Executor
            +-- Pre-Archive Auditor
            `-- Archivist / Publisher
```

主 session 是 Orchestrator，使用用户当前选择的 model 和 reasoning，不强制映射。它只读取精简 state/handoff，执行 Human Gate 和机械路由；不自行 Explore、review、修改业务代码、archive 或 push。

5 个专业角色使用 Codex native custom agents。每次派发都使用 fresh context，不传主 session 的 conversation history。派发内容仅包含：

```text
ROLE
RUN_ID
CHANGE
CURRENT_STATE
ARTIFACT_PATHS
BASE_SHA
HEAD_SHA
EXPECTED_OUTPUT
```

Agent 根据 artifact 路径读取有限范围的项目事实。各 Agent 共享项目 filesystem；流程默认串行，不建立共享 task board 或 Agent 间直接通信。

## 固定模型

针对 ChatGPT Plus 的用量与质量平衡，5 个专业 Agent 固定为：

| Agent | Model | Reasoning |
|---|---|---|
| Explore / Proposal | `gpt-5.6-sol` | `medium` |
| Proposal Reviewer | `gpt-5.6-terra` | `high` |
| Apply Executor | `gpt-5.6-terra` | `high` |
| Pre-Archive Auditor | `gpt-5.6-terra` | `high` |
| Archivist / Publisher | `gpt-5.6-luna` | `medium` |

配置必须显式声明。指定 model 或 reasoning 不可用时返回 `BLOCKED`，不得静默继承或替换。

## 状态与 owner

| State | Owner | 必须产出 |
|---|---|---|
| `NEW` | Orchestrator | `run-id` 与初始 state |
| `EXPLORING` | Explore / Proposal | Explore Result |
| `AWAITING_EXPLORE_APPROVAL` | Orchestrator + Human | 批准、调整或拒绝 |
| `PROPOSING` | Explore / Proposal | OpenSpec Change |
| `REVIEWING_PROPOSAL` | Proposal Reviewer | Review Findings |
| `REVISING_PROPOSAL` | Explore / Proposal | 修订后的 Change |
| `APPLYING` | Apply Executor | 实现、测试和 SHA handoff |
| `AUDITING` | Pre-Archive Auditor | Audit Findings |
| `FIXING_IMPLEMENTATION` | Apply Executor | 修复、测试和新 `HEAD_SHA` |
| `READY_TO_PUBLISH` | Orchestrator | 等待显式发布授权 |
| `PUBLISHING` | Archivist / Publisher | archive、commit、push、sync 结果 |
| `DONE` | 无 | Final SHA 与最终证据 |
| `BLOCKED` | 当前专业 Agent -> Orchestrator | blocker 证据 |
| `NEEDS_HUMAN` | Orchestrator + Human | 人工决策与恢复状态 |

合法主路径：

```text
NEW -> EXPLORING -> AWAITING_EXPLORE_APPROVAL
    -> PROPOSING -> REVIEWING_PROPOSAL
    -> APPLYING -> AUDITING
    -> READY_TO_PUBLISH | PUBLISHING -> DONE
```

失败循环：

```text
REVIEWING_PROPOSAL --FAIL--> REVISING_PROPOSAL --PASS--> REVIEWING_PROPOSAL
AUDITING --FAIL--> FIXING_IMPLEMENTATION --PASS--> AUDITING
```

Proposal Review 与 Pre-Archive Audit 分别最多自动修订两轮；任一阶段第 3 次仍有 blocking finding 时进入 `NEEDS_HUMAN`。`BLOCKED` 不自动重试。

## OpenSpec 调用边界

`explore`、`propose` 和 `apply` 是 Agent workflow 语义，不是本机 OpenSpec CLI 子命令。Codex adapter 使用 CLI 原语执行：

```text
Propose: openspec new change + status + instructions
Apply:   openspec instructions apply
Verify:  openspec validate <change> --strict + 项目 quality gates
Archive: openspec archive <change>
```

所有路径以 `openspec status --change <name> --json` 返回的 `planningHome`、`changeRoot`、`artifactPaths` 和 `actionContext` 为准，不硬编码 `openspec/changes/<change>/`。

## Human Gate 与发布授权

默认只有 Explore 结束后的一个主动 Human Gate。批准记录必须绑定 Explore Result 的 SHA-256 digest；结果被修改后，批准自动失效。

入口支持发布意图：

```text
$openspec-dev-team <request> --publish
```

`--publish` 表示用户已明确授权通过 Audit 后执行正常 archive、commit、push 和必要的 Linear sync。未指定时，流程停在 `READY_TO_PUBLISH`。额外 destructive 或 security-sensitive 操作仍需单独授权。

## Handoff contract

所有专业 Agent 必须返回结构化 handoff，`STATUS` 仅允许：

```text
PASS
FAIL
BLOCKED
NEEDS_HUMAN
```

最小字段：

```text
STATUS
CHANGE
SUMMARY
EVIDENCE
BLOCKERS
ARTIFACTS
CHANGE_DIGEST
BASE_SHA
HEAD_SHA
NEXT_STATE
```

Proposal Reviewer 的 PASS 绑定 `CHANGE_DIGEST`。Auditor 的 PASS 同时绑定 `CHANGE_DIGEST`、`BASE_SHA` 和 `HEAD_SHA`。Publisher 必须确认三者仍一致；任何变化都会使旧 PASS 失效。

测试证据只记录命令、exit code、时间和日志路径，不把完整日志复制进 handoff。

## Runtime state

项目内保存本地、不可提交的运行状态：

```text
.agents/state/<run-id>.json
.agents/runs/<run-id>/
```

Explore 时 Change 尚不存在，因此 state 使用稳定 `run-id` 命名。state 只保存当前阶段、重试次数、SHA、digest 和 artifact 路径，不保存需求、设计或 implementation plan。

状态更新前必须验证 owner、必填字段、digest、SHA 和合法 `NEXT_STATE`，再原子写入。中断后从最后一个有效 handoff 继续；没有有效 handoff 时用 fresh context 重跑当前 attempt。

## Git 工作流

整个流程直接在项目 `main` 串行执行，不使用 branch 或 worktree。

- Apply 可产生 local commits，但不得 push。
- 启动时记录 `BASE_SHA`。
- 存在 staged 或 tracked dirty change 时进入 `NEEDS_HUMAN`。
- 预先存在的 untracked 文件不阻塞，但不得被暂存、删除或覆盖。
- 禁止 `git add .`、`git add -A`、force-push、reset、clean 和 history rewrite。
- Publisher 只按明确 allowlist 暂存本次文件。
- Publisher 开始前确认 branch、remote、Audit PASS、当前 HEAD 和 Change digest。
- remote 或 main 状态异常时返回 `BLOCKED`，不自行 pull、merge 或 rebase。

`using-git-worktrees` 不作为默认 skill。

## 权限边界

| Agent | 写入范围 | GitHub / Linear |
|---|---|---|
| Explore / Proposal | 仅 OpenSpec Change | READ |
| Proposal Reviewer | READ ONLY | READ |
| Apply Executor | 业务代码、测试、local commit | 无 WRITE |
| Pre-Archive Auditor | READ ONLY | READ |
| Archivist / Publisher | archive、final commit、push、必要同步 | WRITE |

Codex custom agent 可设置 model、reasoning、sandbox 与 MCP，但 sub-agent 会继承父 session 的部分权限。首版权限矩阵是行为约束；文档不得声称它提供了进程级 tool isolation。只读角色在 Codex profile 中显式使用 read-only sandbox。

## Superpowers 使用

- Explore / Proposal：仅在项目事实无法解决重大架构选择时使用 `brainstorming`；仅在 OpenSpec tasks 明显不足时使用 `writing-plans`。
- Apply Executor：按需使用 TDD、subagent execution、systematic debugging 和 verification。
- Auditor：按需使用 code review 与 verification。
- Publisher：使用 verification；可参考 finishing-a-development-branch，但服从项目 Git workflow。
- Orchestrator 和 Proposal Reviewer 默认不加载额外 Superpowers。

Superpowers 输出只能补充 OpenSpec artifact，不能成为平行 lifecycle 或 source of truth。

## 项目接入

每个项目仅复用两个全局目录：

```text
project/.agents/shared -> ~/openspec-dev-team/agents/shared
project/.agents/team   -> ~/openspec-dev-team/agents/team
project/.agents/project.md
```

`project.md` 保存项目名称、main branch、expected remote、技术栈、quality gates、OpenSpec 位置、项目约束和项目 skills。

`link-project.sh` 必须支持 dry-run、重复执行，并拒绝覆盖已有文件或错误链接。它创建本地 `state/`、`runs/` 和 `.agents/.gitignore`，但不修改业务代码、OpenSpec artifacts 或 Git history。

## 平台策略

- Codex：可执行。使用 native custom agents、subagent orchestration、通用 skill 和现有 MCP。
- Pi：只记录 skill discovery、agent definition、fresh-context、model 和 tool mapping。
- Claude Code：只记录 subagent/Agent Team 能力差异和映射模板。

该流程是强依赖的串行 pipeline，不需要 Claude Code Agent Teams 风格的共享任务列表或 Agent 间直接通信。

## 验证

1. 静态检查角色、model map、状态 owner、合法转换和 handoff schema。
2. 临时 fixture 覆盖 PASS、FAIL、两轮修复、`BLOCKED`、digest 失效、stale HEAD 和未授权 publish。
3. `doctor.sh --global` 检查依赖、软链接、custom agents 和显式 model。
4. `doctor.sh --project <path>` 检查 Git/OpenSpec root、project config、runtime ignore 和工作区状态。
5. 对 `/Users/kaden/Vela` 做无写入 smoke test，确认识别 `main`、OpenSpec、quality gates、active changes 和现有 untracked 数据库文件；不得修改或推送 Vela。

## 验收标准

- `~/openspec-dev-team` 是独立 Git 项目。
- `~/.codex/skills/openspec-dev-team` 在完成验证后指向项目内 skill。
- Codex 能发现 5 个固定模型的 custom agents。
- Orchestrator 能从任意合法 state 派发唯一 owner，并拒绝非法 handoff。
- 默认只有 Explore 后 Human Gate；无 `--publish` 时不发布。
- OpenSpec 始终是唯一 lifecycle source of truth。
- Vela smoke test 全程无写入，现有用户数据与未跟踪文件保持不变。
