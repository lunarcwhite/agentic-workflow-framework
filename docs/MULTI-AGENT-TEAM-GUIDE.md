# UAAF v3.1 Multi-Agent Team Orchestration Guide

Complete guide for coordinating multiple heterogeneous coding agents (Claude Code, Google Antigravity, Cursor, Open Code, and Pi) simultaneously within a single shared repository without merge collisions or unpermitted scope expansion.

---

## 📑 Table of Contents
1. [The Multi-Agent Problem in Software Engineering](#1-the-multi-agent-problem-in-software-engineering)
2. [The UAAF Solution: Protocol UAAF-TEAM-1.0](#2-the-uaaf-solution-protocol-uaaf-team-10)
3. [The 6 Team Architectural Patterns](#3-the-6-team-architectural-patterns)
4. [The Disjoint Perimeter Invariant](#4-the-disjoint-perimeter-invariant)
5. [Atomic Claims Locking (.claims.lock)](#5-atomic-claims-locking-claimslock)
6. [Universal Multi-Target Persona Exporters](#6-universal-multi-target-persona-exporters)
7. [Step-by-Step Hands-On Tutorial](#7-step-by-step-hands-on-tutorial)
8. [Deliverable Verification & Evidence Gates](#8-deliverable-verification--evidence-gates)

---

## 1. The Multi-Agent Problem in Software Engineering

When deploying multiple autonomous coding agents onto a single repository concurrently, three fatal failure modes commonly occur:
1. **File Overwrite Collisions**: Agent A and Agent B modify the same file at the same time, leading to corrupted diffs or destructive git merge conflicts.
2. **Silent Scope Creep**: Unchecked agents wander beyond their assigned module, refactoring unrelated files, deleting comments, or altering shared configurations without permission.
3. **Mock Stubs & False Completions**: Agents declare victory by adding placeholder functions (`// TODO: implement later`) without verifiable evidence receipts.

---

## 2. The UAAF Solution: Protocol UAAF-TEAM-1.0

UAAF v3.1 treats multi-agent coordination as a **deterministic architectural governance problem**. Rather than relying on heavyweight, fragile LLM API wrappers in Python, UAAF acts as the **Architect, Governor, and Scaffolder**:

```
                       [ High-Level Goal / Feature Request ]
                                         │
                                         ▼
                     [ uaf team compose --pattern <pattern> ]
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
 [ TASK-0001 Contract ]         [ TASK-0002 Contract ]         [ TASK-0003 Contract ]
 Backend Specialist             Frontend Specialist            Reviewer / QA
 Scope: src/api/*               Scope: src/components/*        Scope: tests/*
         │                               │                               │
         └───────────────────────────────┼───────────────────────────────┘
                                         ▼
                           [ Atomic Claims Locking ]
                             (.ai/agents/CLAIMS.yaml)
                                         │
                                         ▼
                     [ Universal Multi-Target Persona Export ]
     ┌──────────────────────┬──────────────────────┬──────────────────────┐
     ▼                      ▼                      ▼                      ▼
Claude Code             Antigravity             Cursor                    Pi
(.claude/agents/)    (.agents/skills/)     (.cursor/rules/)        (.pi/agents/)
```

---

## 3. The 6 Team Architectural Patterns

UAAF provides 6 pre-built architectural topologies to match different development tasks:

| Pattern | Name | Primary Structure | Default Roles | Best Suited For |
|---|---|---|---|---|
| `pipeline` | **Pipeline** | Sequential chain | `architect` &rarr; `engineer` &rarr; `reviewer` &rarr; `verifier` | Migration, refactoring, linear feature delivery |
| `producer_reviewer` | **Producer-Reviewer** | Iterative pair | `producer`, `reviewer` | High-assurance bug fixes, security patches |
| `fan_out_fan_in` | **Fan-Out / Fan-In** | Parallel orthogonal split | `coordinator`, `backend_specialist`, `frontend_specialist`, `integrator` | Full-stack feature delivery, high-throughput tasks |
| `expert_pool` | **Expert Pool** | Subsystem dispatch | `planner`, `domain_expert`, `security_auditor`, `qa_engineer` | Mission-critical core algorithms, audit tasks |
| `supervisor` | **Supervisor** | Hierarchical delegation | `supervisor`, `worker_primary`, `worker_secondary` | Iterative backlog processing, release management |
| `hierarchical` | **Hierarchical Swarm** | Multi-tier enterprise | `lead_architect`, `system_engineer`, `qa_lead`, `compliance_officer` | Monorepos, large complex codebases |

---

## 4. The Disjoint Perimeter Invariant

The core security and stability invariant of `UAAF-TEAM-1.0` is:

$$\text{permitted\_files}(A) \cap \text{permitted\_files}(B) = \emptyset \quad \forall A \neq B$$

### How It Works:
1. When `uaf team compose` decomposes a goal, it inspects your repository structure.
2. It assigns disjoint, non-overlapping file path patterns to each role's task contract.
3. If an agent tries to modify files outside its declared `permitted_files`, `uaf check` will reject the change with an invariant failure.

---

## 5. Atomic Claims Locking (`.claims.lock`)

Before an agent begins work on a task contract:
1. **Acquire Lease**: Run `python tools/uaf.py team lock --agent <agent_id> --lease 900`.
   This writes a cryptographic lease entry into `.ai/agents/CLAIMS.yaml` guarded by an atomic filesystem lock (`.claims.lock`).
2. **Conflict Prevention**: If another agent attempts to lock an overlapping resource, the command fails immediately with `RESOURCE_ALREADY_LOCKED`.
3. **Expiration Safety**: Leases expire automatically after the TTL (default: 900s), ensuring that a crashed agent session does not deadlock the repository.
4. **Release**: When finished, run `python tools/uaf.py team release`.

---

## 6. Universal Multi-Target Persona Exporters

Run `python tools/uaf.py team export --target all` to project the composed team into native agent configurations:

### Target Outputs:
- **Claude Code** (`.claude/agents/*.md`):
  Generates declarative subagent persona instructions specifying permitted files and quality gate criteria.
- **Google Antigravity** (`.agents/skills/team-*/SKILL.md`):
  Generates team orchestrator skills (`team-<pattern>`) and individual role skills (`team-<role>`) compatible with Antigravity IDE and CLI.
- **Cursor** (`.cursor/rules/team.mdc`):
  Generates unified workspace boundary rules to constrain Cursor agent edits.
- **Pi / pi-agent-harness** (`.pi/agents/*.md`, `.pi/prompts/*.md`):
  Generates harness system prompts and orchestration workflow files.

---

## 7. Step-by-Step Hands-On Tutorial

### Skenario: Mengerjakan Fullstack Feature Secara Paralel

Misalkan Anda ingin membangun fitur **"Sistem Notifikasi Real-time"** dengan:
- **Claude Code** mengerjakan backend WebSocket & API.
- **Antigravity** mengerjakan UI komponen notifikasi di frontend.
- **Cursor** melakukan adversarial review & audit.

#### Langkah 1: Inisialisasi Repositori
```bash
uaf init ./my-app --profile full --extension v3.1.0
```

#### Langkah 2: Komposisi Tim
```bash
python tools/uaf.py team compose "Build real-time notification engine" --pattern fan_out_fan_in
```
Output:
```yaml
schema_version: '3.1'
team_id: TEAM-A94D2B81
pattern: fan_out_fan_in
pattern_name: Fan-Out / Fan-In (Parallel Aggregation)
objective: Build real-time notification engine
status: CONFIGURED
members:
  - role: coordinator
    task_id: TASK-0001
    permitted_files: ['.ai/decisions/*', '.ai/tasks/*']
  - role: backend_specialist
    task_id: TASK-0002
    permitted_files: ['src/api/*', 'src/server/*']
  - role: frontend_specialist
    task_id: TASK-0003
    permitted_files: ['src/components/*', 'src/styles/*']
  - role: integrator
    task_id: TASK-0004
    permitted_files: ['tests/*']
```

#### Langkah 3: Ekspor Persona ke Semua Tool
```bash
python tools/uaf.py team export --target all
```
Semua file `.claude/agents/`, `.agents/skills/`, `.cursor/rules/`, dan `.pi/` selesai dibuat secara otomatis!

#### Langkah 4: Kunci Lease & Mulai Bekerja
Saat menjalankan **Claude Code**:
```bash
python tools/uaf.py team lock TASK-0002 --agent claude-code
# Claude Code bekerja strictly di dalam src/api/* & src/server/*
```

Saat menjalankan **Antigravity**:
```bash
python tools/uaf.py team lock TASK-0003 --agent antigravity
# Antigravity bekerja strictly di dalam src/components/* & src/styles/*
```

Kedua agen dapat bekerja di terminal atau window berbeda secara bersamaan **tanpa risiko tabrakan file**!

#### Langkah 5: Rilis & Verifikasi Deliverable
Setelah selesai:
```bash
python tools/uaf.py team release
python tools/uaf.py team verify
python tools/uaf.py check
```

---

## 8. Deliverable Verification & Evidence Gates

Setiap deliverable tugas diverifikasi terhadap kriteria kontraktual:
1. **Contract Exists**: Setiap tugas dalam `TEAM.yaml` memiliki kontrak aktif di `.ai/tasks/active/`.
2. **Disjoint Boundary Verified**: Tidak ada file tumpang tindih.
3. **Exit Code 0 Evidence**: Pengujian lokal harus menghasilkan exit code 0.
4. **Anti-Slop Hard Gate**: Tidak ada komentar `// TODO`, mock stub, atau file placeholder di output diff.
