# UAAF v1.4 Extensions

UAAF v1.4 is an additive extension over UAAF v1.0 through v1.3. It does not change the core meaning of intent, context, memory, verification, claims, or Git history.

## 1. Security Diagnostics

Purpose: provide static, read-only diagnostics for likely secret leakage and unsafe file permissions.

Artifact:

- `.ai/security/SECURITY-DIAGNOSTICS.md`

Tool:

```bash
python tools/uaf.py security ./my-project scan
```

Rules:

1. Diagnostics are read-only.
2. Secret values MUST NOT be printed in diagnostic output.
3. Strongly identifiable private-key/token patterns are reported as `ERROR`.
4. Tracked `.env`-like files are reported as `WARNING` for review.
5. World-writable files are reported as `ERROR`.
6. Diagnostics are bounded to avoid unbounded file reads.
7. Static diagnostics are signals, not proof that a system is secure.

## 2. Semantic Git ↔ Task Traceability

Purpose: connect a task contract to observable Git changes and task-linked commits.

Artifact:

- `.ai/health/GIT-TASK-TRACEABILITY.md`

Tool:

```bash
python tools/uaf.py git-task ./my-project trace --task TASK-0001
```

Rules:

1. The task contract is the semantic scope reference.
2. `expected_changes.files` provides exact file coverage.
3. `expected_changes.modules` provides module-prefix coverage.
4. `.ai/*` framework metadata is ignored from product-change coverage unless explicitly expected by the task.
5. Untracked UAAF bootstrap files (`AGENTS.md`, `README.md`, `CHANGELOG.md`) are ignored unless explicitly expected.
6. A task is `LINKED` when semantic changes are covered and there is no uncovered product change; a recent task-linked commit strengthens the relation but is not mandatory for uncommitted work.
7. A task is `PARTIAL` when some relation exists but coverage is incomplete or only a commit link exists.
8. `UNLINKED` means no task artifact or no meaningful Git/task relationship was found.
9. Git history is never rewritten.

## 3. Runtime Evidence in Delivery Gate

Purpose: make runtime evidence a conditional gate rather than a detached receipt.

Artifact:

- `.ai/verification/RUNTIME-EVIDENCE.md`
- `.ai/verification/RUNTIME-POLICY.yaml`

Tool:

```bash
python tools/uaf.py delivery ./my-project check --task TASK-0001
```

Runtime evidence is required when either:

- the task verification plan explicitly marks a runtime verification item as `required: true`; or
- the manifest declares the task risk in `extensions.runtime_evidence.required_for_risk`.

Rules:

1. Missing required runtime evidence prevents `DONE`.
2. A runtime receipt with status `VERIFIED` can satisfy the runtime evidence condition.
3. `FAILED`, `BLOCKED`, or missing runtime evidence prevents `DONE` when runtime verification is required.
4. Runtime evidence does not replace other delivery gates.
5. Receipt contents remain bounded and are evidence, not a universal proof of correctness.

## 4. Conformance

A project claiming UAAF v1.4 extension conformance MUST use the Full profile and expose all three v1.4 extension contracts.

A v1.0-v1.3 project remains valid without v1.4 artifacts.
