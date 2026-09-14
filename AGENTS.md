# AGENTS.md

## 1. Project Context

OpenSpec Dev Team 是一个基于 **Codex CLI** 的 OpenSpec 多 Agent 开发团队工具。

当前目标：

* 提供标准化的 Codex CLI Multi-Agent 软件开发流程。
* 使用 OpenSpec 作为需求、设计、实施、验证的生命周期来源。
* 通过多个职责明确的 Agent 协作，提高 AI 辅助开发质量。

当前 MVP 范围：

* Codex CLI only
* OpenSpec workflow
* Multi-agent development team

非目标：

* Claude Code adapter
* Pi adapter
* 通用 Agent Runtime
* 多平台 Agent 协议

## 2. Core Design Principles

### Simplicity First

优先选择简单、明确、可维护的设计。

避免：

* 为未来需求提前抽象
* 不必要的平台兼容层
* 复杂配置系统

### Spec Driven Development

OpenSpec 是项目生命周期唯一事实来源。

所有重要修改必须：

1. 明确 Change
2. 生成 Proposal
3. Review
4. Apply
5. Verify

### Single Source of Truth

Agent 配置必须保持单一来源。

当前原则：

```
One Agent = One TOML File
```

不要引入：

* TOML + Markdown 双配置
* 重复 Agent 描述文件

### Human Control

关键阶段必须保留 Human Gate。

Agent 不应：

* 自动绕过审批
* 自主扩大修改范围
* 修改未授权内容

## 3. Architecture Constraints

当前架构：

```
Codex CLI
    |
    |
OpenSpec Skill
    |
    |
Agent Team
    |
    |
Project Code
```

Agent 定义：

```
agents/
 ├── explore.toml
 ├── reviewer.toml
 ├── implementer.toml
 └── auditor.toml
```

每个 Agent TOML 必须包含：

* name
* description
* model
* reasoning_effort
* sandbox
* instructions

## 4. Repository Structure

MVP 推荐结构：

```
openspec-dev-team/

├── agents/
├── skills/
├── templates/
├── scripts/
├── docs/
└── README.md
```

禁止：

* 为 Claude/Pi 提前增加目录
* 保留未使用 adapter
* 增加无实际用途的抽象层

## 5. Development Guidelines

修改代码前：

1. 理解当前架构。
2. 检查 OpenSpec Change。
3. 明确修改范围。
4. 评估是否影响 Agent workflow。

代码修改原则：

* 小步修改
* 精准修改
* 删除优先
* 避免过度设计

## 6. Change Rules

每个功能修改必须对应一个 OpenSpec Change。

Change 应包含：

* Problem
* Goal
* Scope
* Design
* Acceptance Criteria

不要：

* 一个 Change 混合多个独立目标
* 未经过 Proposal Review 直接实现

## 7. Testing

修改后必须验证：

* Agent 配置是否可被 Codex CLI 加载
* Skill 是否正常调用
* Workflow 是否正常运行
* README 与实际能力一致

新增能力必须增加：

* 测试
* 示例
* 使用说明

## 8. Git Workflow

原则：

* main 分支作为唯一开发分支
* 一个 Change 对应一次完整修改
* 修改完成后提交清晰 Commit Message

Commit 示例：

```
feat(agent): simplify agent configuration

refactor(repo): remove unused profiles
```

## 9. Agent Workflow

标准流程：

```
Request

↓

Explore Agent

↓

Human Approval

↓

Review Agent

↓

Implement Agent

↓

Audit Agent

↓

Archive
```

Agent 职责：

### Explore

负责：

* 理解需求
* 分析影响范围
* 创建方案

### Reviewer

负责：

* 挑战方案
* 发现风险
* 检查完整性

### Implementer

负责：

* 根据批准方案修改代码
* 保持修改范围

### Auditor

负责：

* 验证实现
* 检查回归问题

## 10. Do Not

禁止：

* 为未来平台提前设计复杂抽象
* 创建重复配置文件
* 绕过 OpenSpec 流程
* 未确认需求直接扩大范围
* 修改与当前 Change 无关代码

## 11. Common Commands

安装：

```
./install.sh
```

项目初始化：

```
openspec-team init
```

运行检查：

```
./scripts/doctor.sh
```

## 12. Decision Records

当前关键决策：

### Agent Configuration

采用：

```
Single TOML Agent Definition
```

原因：

* 符合 Codex CLI 原生模式
* 降低维护成本
* 避免配置漂移

### MVP Scope

当前只支持：

```
Codex CLI + OpenSpec + Multi-Agent Workflow
```

未来扩展必须独立 Change 评估。
