## Context

See `proposal.md` for the motivation. The current root `AGENTS.md` has a canonical-source table but also itemizes every default profile filename in its project-scope section. Its verification paragraph mentions `scripts/doctor.sh` without a mode, while `scripts/doctor.sh` accepts exactly `--global` or `--project PATH`. `tests/test_contracts.py` already owns static repository-contract checks and has `EXPECTED_AGENTS`, making it the appropriate regression-test owner.

## Goals / Non-Goals

**Goals:**

- Keep the root instruction file a stable navigation and guardrail layer whose profile source reference is directory-based rather than a second roster.
- Make diagnostic guidance unambiguously defer to each diagnostic's documented invocation.
- Add a focused invariant test that detects roster reintroduction or loss of the canonical-source and diagnostic guidance.

**Non-Goals:**

- Do not change any profile TOML, runtime script, skill, README installation behavior, OpenSpec requirement, or diagnostic implementation.
- Do not introduce a new profile registry or duplicate the profile roster in the new test; derive checks from the existing test contract data.
- Do not add a delta spec because the requested changes are documentation and regression-test maintenance only.

## Decisions

### Keep the profile source directory as the only root-file reference

Replace the five bullet entries in `AGENTS.md` with a concise statement identifying `profiles/codex/agents/` as the canonical source. Keep the existing canonical-source map and deployment distinction intact. This avoids copying volatile filenames while preserving discoverability; a full file list or a new registry would recreate the duplication this change removes.

### Make diagnostic wording invocation-neutral but explicit

Change only the verification guidance that currently presents a bare `scripts/doctor.sh` command. Use the exact wording `run applicable diagnostics using their documented invocation`, leaving the canonical-source table's `scripts/doctor.sh` path reference unchanged. This directs readers to the existing `--global`/`--project` interface without duplicating command syntax in `AGENTS.md`.

### Test the root instruction invariants from existing contract data

Add a method to `ContractTests` that reads `AGENTS.md`, asserts the canonical profile directory and diagnostic wording are present, and asserts none of the individual names from `EXPECTED_AGENTS` occur in the file. The test should also reject the old verification phrase/context that implied a bare doctor invocation. Reusing `EXPECTED_AGENTS` ensures the test checks the authored default set without creating a second hard-coded roster.

## Risks / Trade-offs

- [The directory-only wording may provide less immediate detail to a reader] → The canonical-source table and existing README/skill remain available for detailed profile and invocation information.
- [A wording-based test can become coupled to editorial text] → Keep assertions limited to the stable source-of-truth path, absence of individual profile names, and the explicit invocation-guidance phrase.
- [The root file can still drift in unrelated ways] → Keep this as a focused invariant regression test rather than expanding it into a duplicate architecture or runtime specification.

## Migration Plan

No runtime migration is required. Apply the two-file documentation/test update, run the documented repository tests and diagnostics plus strict OpenSpec validation, and roll back by reverting those two implementation-file edits if verification fails.
