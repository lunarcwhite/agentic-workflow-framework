# UAAF v2.6.0 — Field Validation

# UAAF v1.0.1 — Field Validation Report

Date: 2026-09-25

## Scope

A deterministic field-style validation was run against five representative project archetypes:

1. automation / script
2. frontend / UI
3. backend / API
4. data pipeline
5. complex multi-capability application

The exercise validates initialization behavior, conservative capability detection, adaptive documentation selection, preservation of existing files, conformance, and RCE baseline behavior.

## Results

```text
5/5 archetypes initialized successfully
5/5 conformance checks completed without structural errors
5/5 RCE checks reported CONSISTENT
16 automated UAAF tests passed including field archetype coverage
```

Fresh project scaffolds intentionally retain placeholder context and therefore report `PASS_WITH_WARNINGS` until project-specific context is populated. This is expected behavior, not a failed initialization.

## Capability findings

| Archetype | Detected capabilities | Result |
|---|---|---|
| Automation | none | correct conservative baseline |
| Frontend | frontend, ui, design_system | expected |
| Backend/API | backend, api, testing | expected |
| Data pipeline | data, database | expected |
| Complex | frontend, ui, design_system, database, mobile, testing, infrastructure, deployment | expected |

The detector intentionally does not treat generic `pyproject.toml`, `requirements.txt`, or a generic `app/` directory as sufficient proof of a capability.

## Adaptive documentation findings

`--docs auto` produced only documentation families supported by detected capabilities.

Examples:

- frontend → architecture + design + implementation/task documentation
- backend/API → architecture + API + testing + implementation/task documentation
- data → architecture + data + implementation/task documentation + database backup guidance
- automation → no `docs/` tree for the minimal profile

`--docs all` remains available when a complete documentation catalog is explicitly desired.

## Existing-project safety

The initializer now:

- detects capabilities before adding UAAF files;
- preserves existing files by default;
- only prunes files that it copied itself;
- refuses to reinitialize an existing UAAF installation without explicit `--force`;
- does not overwrite an existing project's README or UAAF evidence merely because the scaffold has files with the same names.

## Release-blocking findings fixed

### FIELD-001 — Auto-detect after scaffold copy

**Problem:** detection saw UAAF scaffold files instead of the user's project.

**Fix:** capability detection now runs before scaffold copy.

### FIELD-002 — Generic capability false positives

**Problem:** generic dependency/configuration names such as `pyproject.toml` could imply backend capability.

**Fix:** detection uses stronger project-structure signals and explicitly conservative heuristics.

### FIELD-003 — Minimal CLI mismatch

**Problem:** `uaf check --level minimal` was rejected by the CLI.

**Fix:** `minimal` is accepted as an alias of the core conformance level.

### FIELD-004 — Existing-project prune risk

**Problem:** profile pruning could remove pre-existing files/directories that were not created by UAAF.

**Fix:** pruning is now copy-aware and only removes scaffold paths created during the current initialization.

### FIELD-005 — Documentation over-generation

**Problem:** standard/full initialization generated the entire documentation catalog even when the project had no corresponding capability.

**Fix:** `--docs auto` performs capability-aware documentation selection.

## Remaining findings for UAAF v1.1

These are not blockers for protocol v1.0:

- capability override/confirmation mechanism for ambiguous repositories;
- project-type inference as advisory metadata;
- richer data/ML/domain capability taxonomy;
- Git-aware changed-path impact analysis;
- persistent context cache across sessions;
- semantic conflict resolution assistance with human authority;
- stronger secret scanning;
- real multi-process claim/lease coordination;
- runtime-specific verification adapters.

## Conclusion

The v1.0 protocol semantics remain unchanged. Implementation improvements in this report are backward-compatible and are released as **UAAF implementation 1.0.1**.


## v2.6 archetypes

script, frontend, backend, data, and fullstack were initialized with Full + v2.6 confidential transport. All five completed successfully.
