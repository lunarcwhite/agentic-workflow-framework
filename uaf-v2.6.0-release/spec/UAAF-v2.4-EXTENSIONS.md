# UAAF v2.4 — Federation Capability Exchange & Protocol Negotiation

**Status:** Release Candidate
**Version:** 2.4.0
**Protocol:** UAAF-FED-2.4
**Profile:** Full only

## Purpose

v2.4 defines explicit exchange and negotiation of federation protocol capabilities. It determines which protocol versions and optional features may be used between peers. It does not grant authority and does not replace v2.3 policy enforcement.

## Capability document

Canonical artifact:

`.ai/federation/protocol/CAPABILITIES.yaml`

The document advertises:

- supported protocol versions by family;
- feature requirements and optionality;
- minimum protocol version for each feature;
- whether a fallback is safe;
- security/evidence floors;
- explicitly declared fallback versions.

Unknown capability is not equivalent to support.

## Protocol selection

For each protocol family:

1. choose the highest exact common version when one exists;
2. otherwise consider a fallback only when the selected fallback is explicitly declared by **both peers**;
3. otherwise deny the negotiation.

A peer may not silently select a protocol version that it did not advertise.

## Safe fallback

Fallback is not an automatic downgrade privilege.

Safe fallback requires:

- both peers to declare the fallback version;
- the selected version to be supported by the peer that will execute it;
- no required feature to be silently lost;
- no authority escalation;
- explicit review when a required feature becomes unavailable but the peer declares the fallback safe.

## Feature negotiation

A feature is enabled only when both peers support it and the selected protocol satisfies its minimum protocol requirement.

A required feature that cannot be satisfied causes `DENIED`, except when it is explicitly marked fallback-safe on both sides; in that case the result is `REVIEW_REQUIRED` and the feature remains disabled.

## Negotiation statuses

- `NEGOTIATED` — exact compatible protocol set.
- `FALLBACK_NEGOTIATED` — explicit safe fallback selected.
- `REVIEW_REQUIRED` — fallback requires human/policy review because required behavior is altered.
- `DENIED` — no safe compatible contract exists.

## Protocol contract

Canonical artifact:

`.ai/federation/protocol/PROTOCOL-CONTRACT.yaml`

An active contract contains:

- selected protocol versions;
- enabled features;
- disabled features and reasons;
- explicit fallback records;
- contract hash;
- `authority_change: NONE`.

The contract is a compatibility artifact, not an authority grant.

## Enforcement

Canonical command:

`python tools/uaf.py federation-protocol authorize ...`

Authorization succeeds only when:

- an active negotiated contract exists;
- the requested protocol family/version exactly matches the contract;
- the optional feature is enabled.

A version upgrade requested outside the contract is denied. Negotiation cannot silently upgrade or broaden an existing v2.3 policy.

## Signatures

Capability offers MAY be signed with a UAAF v2.4 detached signature envelope using purpose:

`federation-capability-offer`

When remote signature verification is required, the peer root must be pinned under `.ai/federation/peers/<peer-id>/ROOT.pub.pem` and signature schema/purpose/payload hash must match v2.4.

## Audit

`.ai/federation/protocol/AUDIT.jsonl` records metadata-only protocol events. Payload/source contents and private keys must not be written to the audit log.

## Conformance

`CONF-V24-*` checks:

- Full profile;
- cumulative federation protocol declarations;
- v2.4 capability schema;
- protocol and feature compatibility artifacts;
- locally and remotely advertised selected versions;
- non-escalation;
- valid negotiation state;
- valid audit namespace.

## Safety invariants

v2.4 MUST NOT:

- infer support from unknown capability;
- silently downgrade to an undeclared fallback;
- silently drop required features;
- upgrade a protocol outside the negotiated contract;
- grant authority;
- bypass v2.3 enforcement;
- treat protocol negotiation as an authorization mechanism by itself.
