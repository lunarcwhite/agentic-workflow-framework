# UAAF v3.0 Master Addendum

UAAF v3.0 adds a federated execution runtime on top of the cumulative v2.0-v2.9 federation, trust, transport, confidentiality, key lifecycle, custody, and provider-backed signing layers.

## 1. Purpose

The v3.0 runtime turns federation from a bundle-exchange capability into an explicit, auditable task-execution protocol. A remote agent may execute work only when all of the following are true:

1. A delegating agent is authorized to delegate the requested action, domain, risk, capability, and evidence floor.
2. A trusted route exists to the target peer.
3. The peer's capability and route constraints cover the requested work.
4. A signed task contract binds intent, authority, scope, requirements, acceptance criteria, and change budget.
5. The remote agent authorizes the contract against its own local trust policy.
6. A time-bounded execution lease is granted.
7. Any result is signed and bound to the exact task contract and lease.
8. Required evidence is attached and hash-recorded.
9. The origin verifies the result and records delivery evidence before the remote work is treated as delivered.

## 2. Non-escalation rule

Federation, routing, delegation, lease renewal, protocol negotiation, and transport establishment never increase agent authority.

Capability is not authority. A route advertising `backend` or `write` does not grant those permissions. The target project evaluates the exact contract against its local trust profile.

The effective authorization is bounded by the intersection of:

```text
local delegator authority
∩ route policy
∩ trusted peer ceiling
∩ signed contract authority
∩ remote agent authority
∩ runtime safety policy
```

An empty or incompatible intersection is denied.

## 3. Task contract

A v3.0 task contract is the canonical execution object. It contains at minimum:

- `task_id`
- sender identity
- target peer/project/agent
- intent and optional parent provenance
- requested actions, capabilities, domain, risk, and evidence floor
- in/out scope
- requirements and acceptance criteria
- lease constraints
- execution requirements
- change budget
- contract hash
- Ed25519 signature

The contract hash excludes the `contract_hash` field itself and is computed over the canonical contract body. The signature covers the contract including its hash.

A changed contract is a different contract. Silent mutation after signing is not allowed.

## 4. Routing

Routes are deny-by-default. Selection considers:

- active route status
- required capabilities
- requested execution actions
- requested domain
- requested risk
- route concurrency limit
- trusted peer identity
- trusted peer maximum risk

The effective peer risk ceiling is the lower of route and trusted-peer limits. An active route must declare `execution_actions`; this is an additional outgoing ceiling and does not replace target-side local trust authorization.

## 5. Lease lifecycle

A lease binds one task to one execution owner for a bounded interval.

```text
ACTIVE → RUNNING → COMPLETED
       ↘ RESULT_SUBMITTED
       ↘ CANCELLED
       ↘ EXPIRED
```

`CANCELLED`, `EXPIRED`, `COMPLETED`, and `RESULT_SUBMITTED` are terminal for the current task lease. Terminal leases are never resurrected by renewal, restart, or cancellation.

Renewal is allowed only for a renewable, nonterminal lease and remains bounded by the original contract and runtime ceiling.

## 6. Cancellation

Cancellation is a signed request bound to the task, lease, contract hash, sender project, and reason.

Cancellation is idempotent for an already-cancelled lease. It is rejected when the lease is already `COMPLETED`, `RESULT_SUBMITTED`, or `EXPIRED`, preventing late cancellation from rewriting terminal execution state.

## 7. Result and evidence

A remote result must bind to:

- the original `task_id`
- the exact `contract_hash`
- the exact `lease_id`
- the remote agent identity
- the result status
- the execution summary
- declared changes
- required evidence

Evidence artifacts are recorded with SHA-256 hashes. On the origin, artifacts that are locally present may be independently re-hashed. When the artifact is not available locally, the result is still signature-verified but the artifact verification state is `METADATA_ONLY` rather than an unsupported claim of independent verification.

## 8. Delivery and provenance

Every runtime phase appends a provenance event. Provenance and audit logs use append-only hash chains.

The intended trace is:

```text
user intent
  ↓
local task contract
  ↓
route selection
  ↓
signed delegation
  ↓
remote acceptance
  ↓
execution lease
  ↓
remote execution
  ↓
signed result
  ↓
evidence verification
  ↓
delivery evidence
```

A v3.0 implementation must make the contract hash, lease id, result id, and provenance links available for audit.

## 9. Security boundaries

v3.0 inherits the v2.5-v2.9 security stack. The runtime itself does not provide a new transport security primitive.

- v2.5 provides authenticated channel transport.
- v2.6 provides confidentiality.
- v2.7 governs channel/key lifecycle and revocation.
- v2.8 defines custody provider abstraction.
- v2.9 performs provider-backed key operations without exporting private keys.
- v3.0 uses these layers to sign runtime objects and execute explicit remote contracts.

The reference filesystem provider stores private signing material outside the project and uses `UAAF_KEY_DIR`. No private key material belongs in a v3 release package.

## 10. Delete safety

Remote `delete` is disabled by the v3.0 default runtime policy. The implementation rejects a contract containing `delete` unless a deployment explicitly changes the policy and the full trust/route intersection permits it.

## 11. Transport independence

The runtime creates canonical signed objects; it does not assume a single network transport. A contract, lease receipt, cancellation, or result may be carried by an approved v2.5/v2.6 transport or an external delivery mechanism that preserves the object bytes and verification metadata.

Transport availability is therefore separate from runtime authorization and evidence semantics.

## 12. Downgrade

v3.0 is additive over v2.9. Reinitializing with v2.9 removes the v3 runtime namespace through the initializer's downgrade cleanup while preserving unrelated user files. Downgrade does not silently claim v3 execution semantics.

## 13. CLI surface

```bash
python tools/uaf.py federation-runtime status ./my-project
python tools/uaf.py federation-runtime check ./my-project
python tools/uaf.py federation-runtime route ./my-project --capability backend --domain backend --risk HIGH --select
python tools/uaf.py federation-runtime delegate ./my-project --task-id TASK-3001 --agent-id AGENT-HUMAN --objective '...' --action write --capability backend --domain backend --risk HIGH --min-evidence E3 --peer-id PEER-REMOTE --target-agent AGENT-HUMAN --key-ref O1
python tools/uaf.py federation-runtime accept ./remote-project --contract-file ./TASK-3001.yaml
python tools/uaf.py federation-runtime start ./remote-project --task-id TASK-3001
python tools/uaf.py federation-runtime complete ./remote-project --task-id TASK-3001 --lease-id <LEASE> --result-file ./result.yaml --key-ref R1
python tools/uaf.py federation-runtime verify-result ./my-project --result-file ./.ai/federation/runtime/RESULTS/TASK-3001.yaml
python tools/uaf.py federation-runtime deliver ./my-project --result-file ./.ai/federation/runtime/RESULTS/TASK-3001.yaml
```

## 14. Explicit non-claims

The v3.0 reference runtime does not claim automatic network delivery, universal availability, traffic-analysis resistance, forensic secure erasure, or autonomous authority escalation. It is a contract-and-evidence runtime that composes with the security and transport layers already defined by UAAF.
