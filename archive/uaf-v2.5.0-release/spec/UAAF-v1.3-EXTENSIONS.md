# UAAF v1.3 Extensions

UAAF v1.3 is additive to UAAF v1.0/v1.1/v1.2 semantics. The three extensions in this release are operational mechanisms, not changes to the normative intent/context/memory/verification semantics.

## 1. Git Traceability

Purpose: connect task work to observable Git state without rewriting history.

Artifacts:

- `.ai/health/GIT-BASELINE.yaml`
- optional trace output from `uaf git trace --task TASK-xxxx`

Rules:

1. Baseline is explicit; no implicit baseline commit is assumed.
2. Trace records base commit, current HEAD, changed files, and commits in range.
3. Git history is read-only.
4. A missing Git repository yields an explicit error, not fabricated traceability.
5. Git traceability does not replace task/change/evidence traceability.

## 2. Real Claim Leasing

Purpose: make multi-process resource ownership atomic enough for filesystem-backed coordination.

Artifacts:

- `.ai/agents/CLAIMS.yaml`
- `.ai/agents/.claims.lock` during mutation

Claim fields:

```yaml
claim_id:
resource:
agent:
task:
status: ACTIVE | RELEASED | EXPIRED | RECLAIMABLE
acquired_at:
lease_until:
```

Rules:

1. Claim mutation is protected by exclusive lock creation.
2. Claims are compared by normalized resource path.
3. Active conflicting claims block acquisition by default.
4. Expired claims are detected before mutation.
5. An expired claim remains blocking until an explicit `reclaim` operation marks it RECLAIMABLE.
6. Reclaim is explicit; expiry does not silently transfer ownership.
7. Claims are coordination metadata and do not replace Git.

## 3. Runtime Verification

Purpose: turn explicitly authorized runtime commands into observable evidence.

Artifact:

- `.ai/verification/RUNTIME-POLICY.yaml`

Default:

```yaml
enabled: false
allow: []
```

Rules:

1. Runtime verification is disabled unless explicitly enabled.
2. Only exact allowlisted commands may execute.
3. Commands execute with `shell=False`.
4. Timeout produces `BLOCKED` evidence.
5. Non-zero exit produces `FAILED` evidence.
6. Zero exit produces `VERIFIED` evidence.
7. stdout/stderr are bounded in receipts.
8. Runtime evidence is evidence, not a universal proof of system correctness.

## 4. Conformance

A project claiming UAAF v1.3 extension conformance MUST be Full profile and MUST expose all three extension contracts. A v1.0-v1.2 project remains valid without these extension artifacts.
