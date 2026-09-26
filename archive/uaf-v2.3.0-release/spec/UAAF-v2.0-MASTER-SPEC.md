# UAAF v2.0 — Distributed Agent Federation

**Status:** Stable
**Version:** 2.0.0
**Framework:** Universal AI Agent Framework
**Federation Protocol:** UAAF-FED-2.0

## 1. Purpose

UAAF v2.0 extends the v1.x trust and governance model from a single repository into a transport-agnostic federation of projects, agents, and machines.

The framework MUST support:

- cross-project agent identity;
- signed handoff envelopes;
- replay protection;
- federated, deny-by-default policy;
- vector-clock based distributed state convergence;
- explicit conflict detection without silent semantic resolution;
- portable bundles that can be exchanged over Git, files, CI artifacts, or another transport.

UAAF v2.0 does **not** define a network protocol, service discovery system, or enterprise IAM replacement.

## 2. v1.x Compatibility

UAAF v2.0 retains the semantics of v1.0–v1.9 unless this specification explicitly changes a contract.

The v2.0 profile is Full-only. Existing local task, memory, governance, trust, verification, and cryptographic integrity mechanisms remain valid.

## 3. Core Trust Model

```text
LOCAL TRUST ROOT
      ↓
FEDERATION IDENTITY
      ↓
PINNED PEER
      ↓
FEDERATED POLICY
      ↓
SIGNED ENVELOPE
      ↓
REPLAY CHECK
      ↓
ACTION-SPECIFIC VERIFICATION
```

The identity of an agent is not sufficient to authorize an action. Authorization remains bounded by local trust, federation policy, peer action allowlist, risk ceiling, and current task policy.

## 4. Federation Namespace

```text
.ai/federation/
├── IDENTITY.yaml
├── IDENTITY.yaml.sig
├── PEERS.yaml
├── FEDERATION-POLICY.yaml
├── FEDERATION-POLICY.yaml.sig
├── REPLAY.yaml
├── AUDIT.jsonl
├── HANDOFFS/
├── BUNDLES/
├── peers/
└── state/
    ├── VECTOR.yaml
    ├── REGISTERS.yaml
    └── CONFLICTS.yaml
```

Private keys MUST NOT exist in this namespace.

## 5. Cross-Project Identity

A federation identity contains:

```yaml
schema_version: '2.0'
identity:
  project_id:
  agent_id:
  machine_id:
  key_id:
  algorithm: Ed25519
  public_key:
  fingerprint_sha256:
  created_at:
  status: ACTIVE
```

The identity document is signed by a trusted project root using purpose `federation-identity`.

Remote projects MUST pin the peer project root and the identity public-key fingerprint before accepting federated actions.

## 6. Peer Registration

A peer record MUST identify:

- peer project;
- agent identity key;
- root fingerprint;
- root public key or an equivalent pinned root reference;
- allowed federation actions;
- maximum risk;
- whether signed handoff/state is required;
- status.

Default federation behavior is deny.

## 7. Federated Policy

The policy document is signed and determines federation-wide defaults:

```yaml
schema_version: '2.0'
default_deny: true
require_signed_handoff: true
require_signed_state: true
allowed_actions:
  - handoff
  - state-pull
  - state-push
  - capability-sync
  - policy-sync
```

A peer-level grant MAY further restrict the policy, but MUST NOT expand a global deny.

## 8. Signed Envelope

All remote federation actions use a canonical envelope:

```yaml
schema_version: '2.0'
type: UAAF_FEDERATION_ENVELOPE
action:
envelope_id:
nonce:
sequence:
issued_at:
expires_at:
sender:
audience:
payload:
signature:
```

The signature covers the canonical envelope body, not the transport wrapper.

## 9. Replay Protection

Every remotely accepted envelope MUST contain:

- unique `envelope_id`;
- unpredictable `nonce`;
- bounded `issued_at` / `expires_at` window.

The receiving project records accepted envelope IDs/nonces in `REPLAY.yaml`.

A second verification of an already consumed envelope MUST fail with `REPLAY_DETECTED`.

Replay protection MUST fail closed for expired envelopes and invalid time windows.

## 10. Signed Handoff

A handoff payload is transport independent. It may embed the canonical handoff Markdown or another declared handoff representation.

Required audience fields prevent a signed handoff intended for one project from being replayed against another.

The receiver MUST validate:

```text
identity
→ signature
→ audience
→ time window
→ peer policy
→ risk ceiling
→ replay state
```

before accepting the handoff.

## 11. Distributed State

UAAF v2.0 uses vector clocks for state merge.

Relation:

```text
A dominates B
B dominates A
A == B
A concurrent with B
```

If one version dominates another, the newer causally dominant value may replace the older value.

If two values are concurrent and different, UAAF MUST record a conflict and MUST NOT silently choose one.

Identical concurrent values may converge without a semantic conflict.

## 12. State Conflict

Conflicts are recorded in:

```text
.ai/federation/state/CONFLICTS.yaml
```

Example:

```yaml
status: UNRESOLVED
key: product.feature_flag
local: ...
incoming: ...
detected_at: ...
```

Resolution authority remains outside automatic merge.

## 13. Federated State Bundle

State export is signed using action `state-push` and includes the sender's vector clock and register set.

Import MUST verify the remote identity and policy before mutating local state.

Replay consumption occurs before merge so a partially processed bundle cannot be replayed later.

## 14. Audit

Federation events are recorded in an append-oriented hash chain.

Audit records are metadata only and MUST NOT store prompts, secrets, or source contents.

## 15. Transport Independence

UAAF-FED-2.0 defines envelope semantics, not transport.

A bundle MAY travel through:

- filesystem exchange;
- Git;
- CI artifacts;
- an API;
- a message broker;
- another trusted transport.

Transport authentication does not replace federation signature verification.

## 16. Security Rules

The federation layer MUST:

- use signed content for remote control-plane actions;
- use deny-by-default policy;
- check peer risk ceilings;
- reject audience mismatch;
- reject replay;
- reject expired envelopes;
- keep private keys outside the project;
- fail closed on verification errors.

## 17. Conformance

UAAF-C v2 adds `CONF-V20-*` checks for:

- Full profile;
- framework 2.x;
- federation protocol version;
- required namespace;
- federation schemas;
- deny-by-default policy;
- private-key exclusion;
- replay storage;
- state vector/register/conflict structure;
- identity/policy signature readiness;
- unresolved conflict visibility.

## 18. Non-Goals

UAAF v2.0 does not provide:

- central identity authority;
- TLS termination;
- network discovery;
- OS process authentication;
- enterprise authorization replacement;
- automatic conflict resolution with hidden semantic choices.
