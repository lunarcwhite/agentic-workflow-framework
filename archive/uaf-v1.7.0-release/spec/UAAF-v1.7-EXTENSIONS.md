# UAAF v1.7 — Policy Governance & Safe Adaptation

## Purpose

UAAF v1.6 can propose adaptive improvements. UAAF v1.7 defines how those proposals become governed changes without allowing the optimizer to rewrite its own intent or safety policy.

## Lifecycle

```text
PROPOSED
↓
REVIEWED
↓
APPROVED
↓
APPLIED
↓
VERIFIED
```

Alternative terminal states are `REJECTED` and `EXPIRED`.

## Core rules

- `auto_apply` MUST remain `false`.
- A reviewer/approver is required for governance transitions.
- Applied changes MUST contain an explicit change list.
- Only allowlisted paths may be mutated.
- Intent and safety controls are forbidden mutation targets.
- Approval records file precondition hashes.
- Apply MUST fail when a precondition hash no longer matches.
- Every apply creates a rollback snapshot.
- Rollback is explicit and audited.
- Governance does not replace Git.

## Safe mutation model

v1.7 supports only:

```yaml
changes:
  - path: .ai/optimization/POLICY.yaml
    operation: set
    key: adaptive.max_replan_rate_per_task
    value: 3.0
```

No arbitrary code execution, shell command, file deletion, or intent mutation is supported by the safe-apply path.

## Audit

`.ai/governance/AUDIT.jsonl` is append-oriented metadata. It contains actor, proposal, transition, backup, and change metadata without storing secrets or prompts.

## Rollback

A successful apply creates `.ai/governance/rollback/<proposal-id>/` snapshots. Rollback restores the snapshot and records the operation in the audit log.
