# UAAF v3.1 Extension Contract: Team-Architecture Factory & Multi-Agent Orchestrator

## Extension Identity

```yaml
version: "3.1.0"
protocol: "UAAF-TEAM-1.0"
profile: full
mode: disjoint_task_contract_claims_export
```

## Architectural Foundations

UAAF v3.1 builds directly upon the federated runtime foundations of v3.0, introducing the **Team-Architecture Factory & Multi-Agent Orchestrator** (`uaf team`). This enables heterogeneous multi-agent collaboration—coordinating Claude Code, Google Antigravity, Cursor, and custom harness runtimes (such as pi-agent-harness)—within a single shared repository without merge conflicts, scope creep, or hallucinated claims.

## Six Standard Team Patterns

1. **Pipeline (`pipeline`)**:
   Sequential execution chain where predecessor outputs establish immutable context receipts for downstream agents.
   *Roles*: `architect` → `engineer` → `reviewer` → `verifier`.

2. **Producer-Reviewer (`producer_reviewer`)**:
   Paired iterative cycle between an implementer and an adversarial reviewer. No task completes without cryptographically verifiable test evidence.
   *Roles*: `producer`, `reviewer`.

3. **Fan-Out / Fan-In (`fan_out_fan_in`)**:
   High-throughput parallel decomposition across orthogonal subsystems (e.g. backend, frontend, test infrastructure) followed by synchronized assembly.
   *Roles*: `coordinator`, `backend_specialist`, `frontend_specialist`, `integrator`.

4. **Expert Pool (`expert_pool`)**:
   Dynamic routing of tasks to specialized domain roles according to affected subsystems.
   *Roles*: `planner`, `domain_expert`, `security_auditor`, `qa_engineer`.

5. **Supervisor (`supervisor`)**:
   Hierarchical management where a supervisory agent manages task life-cycles, audits lease expirations, and approves releases.
   *Roles*: `supervisor`, `worker_primary`, `worker_secondary`.

6. **Hierarchical Swarm (`hierarchical`)**:
   Multi-tier structure for complex enterprise codebases with strategic leadership, tactical leads, and specialized workers.
   *Roles*: `lead_architect`, `system_engineer`, `qa_lead`, `compliance_officer`.

## Core Invariants

1. **Disjoint Perimeter Invariant**:
   For any concurrent team execution, the sets of `permitted_files` assigned across tasks MUST be disjoint:
   $$\text{permitted\_files}(A) \cap \text{permitted\_files}(B) = \emptyset \quad \forall A \neq B$$
2. **Atomic Claims Locking**:
   Agents must hold a valid, non-expired atomic claim lock (`.claims.lock`) before modifying any file within their permitted perimeter.
3. **Receipt-Driven Handoff**:
   Handoff between agents requires evidence receipts containing exit codes and SHA-256 hashes of modified artifacts.
4. **Universal Multi-Target Export**:
   Team specifications can be projected into native agent configuration formats for:
   - Claude Code (`.claude/agents/*.md`)
   - Antigravity (`.agents/skills/team-*/SKILL.md`)
   - Cursor (`.cursor/rules/team.mdc`)
   - Pi / pi-agent-harness (`.pi/agents/*.md`, `.pi/prompts/*.md`)

## Conformance Assertions

- `CONF-V31-001`: `protocols.team_orchestrator` must be `UAAF-TEAM-1.0`.
- `CONF-V31-002`: `extensions.team_orchestrator` section must be present when extension version is `3.1.0`.
- `CONF-V31-003`: `extensions.team_orchestrator.mode` must be `disjoint_task_contract_claims_export`.
- `CONF-V31-004`: `TEAM.yaml` `schema_version` must be `3.1`.
- `CONF-V31-005`: No two active team members may share identical `permitted_files`.
- `CONF-V31-006`: `TEAM.yaml` must be valid YAML.
