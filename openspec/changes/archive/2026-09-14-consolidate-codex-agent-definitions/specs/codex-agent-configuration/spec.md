## Purpose

Defines how the default Codex specialists are discovered, configured, and orchestrated without duplicated role definitions or unnecessary startup context.

## ADDED Requirements

### Requirement: One native definition per default specialist
The system SHALL provide exactly five default Codex specialist definitions, with one TOML file per specialist under the native Codex Agent profile directory. Each TOML definition MUST contain a non-empty name, description, model, reasoning effort, sandbox mode, and complete role-specific developer instructions.

#### Scenario: Validate the default Agent set
- **WHEN** repository validation enumerates the default Codex Agent profiles
- **THEN** it finds exactly the five documented specialist TOML files with all required fields

#### Scenario: Load role responsibilities
- **WHEN** Codex discovers and starts any default specialist
- **THEN** that specialist obtains its role-specific input, read, write, forbidden, output, and escalation responsibilities from its TOML definition without requiring a corresponding role Markdown file

### Requirement: Preserve native Codex discovery compatibility
The system SHALL retain the existing five Agent names, profile filenames, model assignments, reasoning effort values, sandbox modes, and Codex installation destinations.

#### Scenario: Discover installed specialists
- **WHEN** the five TOML profiles are installed in the documented Codex custom-Agent directory and a new Codex session starts
- **THEN** Codex can discover the same five named specialists with their existing runtime settings

### Requirement: Separate Agent definitions from shared workflow contracts
Role-specific behavior MUST be defined only in the corresponding TOML profile. Cross-Agent workflow policy and structured handoff requirements MAY remain in shared contracts referenced by the profiles, but those contracts MUST NOT become alternate role definitions.

#### Scenario: Inspect configuration ownership
- **WHEN** a maintainer locates the configuration for a specialist
- **THEN** the specialist's TOML is the only role-specific definition and shared files contain only cross-Agent guarantees

### Requirement: Orchestration belongs to the skill
The system SHALL define the Orchestrator as behavior of the `openspec-dev-team` skill rather than as a sixth Agent or a separate team-role contract. The skill MUST preserve request provenance, serial routing, Human Gate enforcement, handoff validation and persistence, and escalation boundaries.

#### Scenario: Start or resume orchestration
- **WHEN** the development-team skill starts or resumes a run
- **THEN** it can enforce all Orchestrator invariants without reading `agents/team/orchestrator.md`

### Requirement: Orchestration uses progressive disclosure
The orchestration skill SHALL keep its always-loaded guidance concise and layered. It MUST direct the Orchestrator to load detailed canonical references only when required for the current routing or validation operation, rather than requiring every phase-specific contract to be loaded at invocation.

#### Scenario: Enter an early workflow phase
- **WHEN** the skill is invoked for a run that has not reached publishing
- **THEN** publishing-only operational detail is not required as startup context

#### Scenario: Route or validate a handoff
- **WHEN** the Orchestrator needs canonical transition or handoff details
- **THEN** it loads the applicable state-machine or shared contract reference while retaining `SKILL.md` as the concise orchestration entry point

### Requirement: Project bootstrap excludes obsolete team contracts
Project bootstrap and diagnostics SHALL require the shared contracts and project-owned configuration needed by the workflow, but SHALL NOT create or require an `.agents/team` link.

#### Scenario: Bootstrap a project
- **WHEN** a user runs the project-linking script on a valid target project
- **THEN** the resulting `.agents` structure contains the shared-contract link and project runtime/configuration paths but no team-contract link

#### Scenario: Diagnose a bootstrapped project
- **WHEN** project diagnostics run against the simplified structure
- **THEN** diagnostics pass without an `.agents/team` path and continue validating all required shared and project-owned inputs
