# UAAF v1.8 Extension — Agent Trust & Delegation

## Purpose

UAAF v1.8 defines a bounded authorization layer for multi-agent operation. It distinguishes:

```text
CAPABILITY
→ what an agent can technically perform

AUTHORITY
→ what the project policy permits that agent to perform

DELEGATION
→ a time-bounded grant of authority from one registered agent to another
```

UAAF v1.8 does not authenticate operating-system identities or replace IAM/Git/CI permissions. It provides project-level policy metadata and deterministic authorization decisions for UAAF workflows.

## Authorization decision

```text
AUTHORIZED
DENIED
REVIEW_REQUIRED
```

Authorization checks:

```text
registered + active agent
→ capability
→ domain
→ risk ceiling
→ evidence floor
→ delegation chain
→ policy deny list
```

## Delegation invariants

A delegation MUST:

- have a unique ID;
- identify a registered delegator and delegatee;
- have explicit capabilities and domains;
- have a maximum risk;
- have a minimum evidence floor;
- have a future expiry time;
- remain bounded by the delegator's effective authority;
- never escalate capability, domain, or risk;
- be revocable;
- never create a self-delegation or active cycle.

Expiry does not silently create a new owner. Reassignment or replacement requires an explicit new delegation.

## Evidence posture

`min_evidence` is a policy floor for the action. The value uses the UAAF evidence ladder `E0`–`E5`.

This is intentionally not a trust score. Historical evidence may satisfy a required floor when the consuming workflow records it, but evidence history MUST NOT silently increase authority.

## Root authority

A root/direct authority agent is explicitly marked in `TRUST.yaml`. Root authority does not make every action safe; hard policy denials, safety gates, and project-specific authorization still apply.

## Revoke semantics

A revoked delegation immediately ceases to authorize its delegatee through that delegation chain. Descendant chains that depend on it become invalid.

## Audit

Trust operations append metadata-only events to `TRUST-AUDIT.jsonl`. Secrets, credentials, prompt contents, and source contents MUST NOT be stored there.

## Configuration

```yaml
schema_version: '1.8'
policy:
  enabled: true
  deny_actions: []
agents:
  - id: AGENT-HUMAN
    status: ACTIVE
    direct_authority: true
    authority: ROOT
    can_delegate: true
    capabilities: ['*']
    domains: ['*']
    max_risk: CRITICAL
    min_evidence: E0
```

## CLI

```bash
python tools/uaf.py trust ./my-project check
python tools/uaf.py trust ./my-project status --json
python tools/uaf.py trust ./my-project evaluate --agent AGENT-CODE --capability write --domain backend --risk HIGH --min-evidence E3
python tools/uaf.py trust ./my-project delegate --from-agent AGENT-HUMAN --to-agent AGENT-CODE --delegation-id DEL-0001 --capability write --domain backend --risk HIGH --min-evidence E3 --expires-at 2026-10-01T00:00:00+07:00
python tools/uaf.py trust ./my-project revoke --delegation-id DEL-0001
```

`evaluate` is decision-only. It never grants authority.

## Delivery integration

v1.8 does not replace Delivery Gate. A task can only be `DONE` when its existing delivery requirements pass and any applicable trust/authority gate is satisfied.

## Backward compatibility

v1.8 is additive and Full-profile only. A v1.0–v1.7 initialization does not emit v1.8 trust artifacts unless explicitly requested.
