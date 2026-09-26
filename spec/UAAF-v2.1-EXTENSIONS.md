# UAAF v2.1 — Federation Operations & Resilience

**Status:** Release Candidate
**Version:** 2.1.0
**Framework:** Universal AI Agent Framework
**Federation Protocol:** UAAF-FED-2.1

## 1. Purpose

UAAF v2.1 extends v2.0 federation with operational resilience while preserving the v2.0 trust boundary.

It MUST support:

- explicit federation modes: ONLINE, OFFLINE, PARTITIONED, RECOVERING;
- idempotent synchronization bundles and inventory/cursor tracking;
- explicit conflict-resolution workflow without hidden semantic choice;
- signed revocation propagation with monotonic epochs;
- signed checkpoints and bounded recovery;
- federated operational observability using metadata only.

v2.1 remains transport-agnostic.

## 2. Federation Modes

```text
ONLINE
OFFLINE
PARTITIONED
RECOVERING
```

Mode is operational state, not authority. Going offline MUST NOT broaden permissions.

## 3. Synchronization

Each peer has a sync cursor. A sync bundle contains:

- bundle_id;
- sender project;
- target project;
- source vector clock;
- sequence/cursor;
- created_at / expires_at;
- content hash;
- signed federation envelope.

Import MUST be idempotent. A consumed `bundle_id` MUST NOT be applied twice.

A bundle MAY contain state delta metadata, revocation entries, conflict decisions, or checkpoint references.

## 4. Partition Handling

During PARTITIONED mode:

- local work MAY continue within existing local authority;
- remote authority MUST NOT be inferred;
- stale peer state MUST be marked;
- synchronization MUST reconcile causality before mutation;
- concurrent semantic conflicts MUST remain explicit.

## 5. Conflict Workflow

Conflict lifecycle:

```text
UNRESOLVED
  ↓
PROPOSED
  ↓
APPROVED
  ↓
RESOLVED
```

Alternative terminal state:

```text
REJECTED
```

`RESOLVED` requires an explicit resolution record. Automatic merge MAY happen only for causally dominant or byte-identical state.

## 6. Revocation Propagation

Revocations use a monotonically increasing `revocation_epoch` per federation root.

A revocation record contains:

```yaml
schema_version: '2.1'
revocation_id:
target_type:
target_id:
reason:
effective_at:
revocation_epoch:
```

The record MUST be signed by an authorized federation trust root or key explicitly allowed by policy.

Receivers MUST reject stale epochs and invalid signatures.

Revoked identities/peers MUST fail closed for newly received actions after effective time.

## 7. Checkpoints and Recovery

A checkpoint captures:

- local vector clock;
- register hash;
- conflict state hash;
- replay watermark;
- revocation epoch;
- created_at;
- checkpoint_id.

A checkpoint is signed and can be restored only after verification.

Recovery MUST NOT silently discard unresolved conflicts or replay protections.

## 8. Federation Observability

Federated observability records metadata only:

```text
peer
mode
last_sync
bundle_count
conflict_count
revocation_epoch
checkpoint_age
verification_failures
```

No prompts, source contents, secrets, or private keys may be recorded.

## 9. Conformance

v2.1 adds `CONF-V21-*` checks for:

- Full profile and federation 2.x;
- v2.1 namespace and schema versions;
- valid sync cursor;
- revocation epoch structure;
- conflict workflow schema;
- checkpoint structure;
- metadata-only observability;
- private-key exclusion;
- idempotent bundle ledger;
- v2.1 policy readiness.

## 10. Safety

v2.1 operations MUST fail closed on:

- invalid federation signatures;
- stale revocation epoch;
- checkpoint mismatch;
- replayed sync bundle;
- audience mismatch;
- unknown peer;
- unresolved conflict treated as resolved;
- permission escalation during offline/partitioned operation.
