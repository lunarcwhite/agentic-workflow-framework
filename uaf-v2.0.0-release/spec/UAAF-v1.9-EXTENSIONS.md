# UAAF v1.9 Extension — Trust Anchoring & Cryptographic Integrity

## Purpose

UAAF v1.9 makes project-level trust metadata independently verifiable. It protects the trust root, public key registry, trust policy, delegations, and audit history against undetected tampering.

The extension is Full-profile only and additive to v1.8.

## Security model

```text
TRUST ROOT
    ↓
PUBLIC KEY REGISTRY
    ↓
SIGNED POLICY / DELEGATIONS
    ↓
AGENT TRUST DECISION
```

UAAF v1.9 does not replace operating-system identity, enterprise IAM, Git signing policy, CI policy, or remote attestation.

## Algorithm

The reference implementation uses Ed25519 detached signatures through the Python `cryptography` library. Ed25519 provides `sign()` on the private key and `verify()` on the public key; exact implementation compatibility should be validated against the installed library version. 

## Trust artifacts

```text
.ai/trust/
├── ROOT.yaml
├── KEYS.yaml
├── KEY-ROTATION.yaml
└── *.sig
```

Public trust material may be committed. Private signing keys MUST remain outside the repository.

## ROOT.yaml

The root contains:

```yaml
schema_version: '1.9'
anchor:
  key_id: AGENT-ROOT-001
  algorithm: Ed25519
  public_key: <base64>
  fingerprint_sha256: <sha256>
  status: ACTIVE
policy:
  enabled: true
  cryptographic_required: false
  external_pin_required: false
  required_purposes:
    - trust-root
    - trust-keys
    - trust-policy
    - delegations
```

The four required signature purposes are explicit so that a verifier cannot accidentally treat an unrelated signature as proof of trust integrity.

## Detached signature envelope

Each `.sig` contains:

```json
{
  "schema_version": "1.9",
  "algorithm": "Ed25519",
  "key_id": "AGENT-ROOT-001",
  "purpose": "trust-root",
  "payload_sha256": "...",
  "signature_b64": "...",
  "created_at": "..."
}
```

The verifier recomputes the payload hash and verifies the signature over the exact file bytes.

## Canonicalization

Structured values used by rotation evidence and audit chaining use deterministic UTF-8 JSON with sorted keys and compact separators.

## External root pinning

A deployment may hold a root fingerprint outside the repository. When `external_pin_required=true`, verification MUST fail closed if the caller does not provide the expected fingerprint.

## Signed bundle

When `cryptographic_required=true`, bundle verification requires valid signatures for:

```text
ROOT.yaml       → trust-root
KEYS.yaml       → trust-keys
TRUST.yaml      → trust-policy
DELEGATIONS.yaml→ delegations
```

The root policy is itself signed, so changing cryptographic requirements requires re-signing the root document.

## Audit integrity

v1.9 upgrades trust audit records to a hash chain:

```text
GENESIS
  ↓
ENTRY-1
  ↓
ENTRY-2
  ↓
ENTRY-N
```

Every entry carries `prev_hash` and `entry_hash`. Tampering or reordering is detected.

Legacy v1.8 audit data may be preserved separately as historical evidence during migration.

## Root rotation

Rotation is explicit:

```text
OLD ROOT
   ↓ signs
ROTATION RECORD
   ↓ proves
NEW ROOT PUBLIC KEY
```

Rotation does not silently activate a new root. Activation remains an explicit policy/registry operation.

## Conformance

v1.9 adds `CONF-V19-*` checks for:

- Full profile requirement;
- trust namespace and schema;
- Ed25519 public-key shape and fingerprint;
- required signature purposes;
- absence of private signing keys;
- signed bundle verification;
- external pin enforcement;
- compatibility with the v1.8 trust layer.

## Privacy and non-goals

The extension does not store prompts, source contents, credentials, or private keys in trust audit data.

It does not provide a remote certificate authority, OS authentication, or enterprise IAM replacement.
