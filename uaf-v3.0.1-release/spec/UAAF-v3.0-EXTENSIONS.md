# UAAF v3.0 Extension Contract

## Extension identity

```yaml
version: 3.0
protocol: UAAF-FED-3.0
profile: full
mode: contract_lease_evidence_provenance
```

## Required runtime paths

```text
.ai/federation/runtime/
├── POLICY.yaml
├── ROUTES.yaml
├── TASK-CONTRACTS/
├── LEASE-RECEIPTS/
├── LEASES.yaml
├── CANCELLATIONS/
├── RESULTS/
├── EVIDENCE/
├── PROVENANCE.jsonl
└── AUDIT.jsonl
```

## Policy invariants

```yaml
default_deny: true
require_signed_contract: true
require_signed_result: true
require_evidence: true
allow_silent_scope_expansion: false
authority_escalation: false
private_key_storage: false
require_local_agent_authorization: true
allow_remote_delete: false
```

## Runtime object types

`federated_task_contract`

The signed request to perform remote work.

`federated_lease_receipt`

The signed grant of a bounded execution lease.

`federated_task_cancellation`

The signed request to cancel a task lease.

`federated_task_result`

The signed execution outcome bound to the task contract and lease.

`remote_execution_evidence`

A local receipt recording evidence attested by the remote executor.

`federated_delivery_evidence`

The origin-side receipt emitted only after successful result verification.

## Result verification states

```text
signature_verified
  + contract_hash_match
  + lease_binding_match
  + lease_expiry_valid
  + evidence_attested
  + optional local artifact hash verification
```

Missing local artifacts do not become a false negative or false positive; the receipt reports `METADATA_ONLY` for that portion.

## Failure semantics

The following are hard failures:

- untrusted peer
- invalid signature
- signer not bound to peer identity
- contract hash mismatch
- target project mismatch
- unauthorized action/domain/risk/capability
- lease expired
- lease cancelled
- terminal lease reuse
- missing required evidence
- result bound to a different contract or lease
- private key material under the runtime tree

## State monotonicity

The implementation must not move a terminal lease back into `ACTIVE` or `RUNNING`. Recovery mechanisms from lower federation layers may preserve or reconstruct context but cannot resurrect terminal execution state.

## Provider-backed signing

Preferred v3 signing resolves the local federation identity key through the v2.9 key-reference/custody layer.

Purpose separation:

```text
federation-task-delegation
federation-task-result
federation-task-cancellation
federation-task-lease
```

The reference implementation rejects a v3 `--key-ref` that does not identify the current local federation identity key.

## Compatibility

v3.0 composes with the v2.5 authenticated transport and v2.6 confidential transport, but the runtime object format remains transport-independent. Legacy `--private-key` compatibility exists for migration and testing; provider-backed key references are the preferred operational boundary.
