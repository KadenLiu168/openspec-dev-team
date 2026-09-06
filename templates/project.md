# Project Configuration

Keep this file specific to the project. It configures the shared OpenSpec dev
team without defining another development lifecycle.

## Project identity

```yaml
project_name: "example-project"
project_realpath: "/absolute/path/to/example-project"
main_branch: "main"
expected_remote: "git@github.com:example/example-project.git"
```

## Stack

```yaml
stack:
  - "Python 3.13"
  - "PostgreSQL"
```

## OpenSpec root

```yaml
openspec_root: "openspec"
```

## Quality gates

```yaml
quality_gates:
  - "python3 -m unittest discover -s tests -v"
```

## Protected data

```yaml
protected_data:
  - ".env"
  - "secrets/**"
```

## Project constraints

```yaml
project_constraints:
  - "Do not change generated files directly."
```

## Project skills

```yaml
project_skills:
  - "skill-name"
```

## Optional Linear issue mapping

```yaml
linear_issue_mapping:
  "openspec-change-id": "TEAM-123"
```
