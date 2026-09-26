# UAAF v2.8 — Federation Key Storage & External KMS Integration

## Status
Implementation extension over UAAF v2.7. Protocol semantics v2.0–v2.7 remain unchanged.

## Purpose
Separate key lifecycle from key custody. A project declares an active key provider, health state, and non-export policy without storing provider secrets or private key material in the repository.

## Providers
- `filesystem`: reference local provider; best-effort local custody.
- `os-keychain`: optional keychain adapter; available only when a compatible keyring backend is installed and configured.
- `kms`: external signing/KMS adapter contract. The reference implementation provides configuration and health checks, not a cloud-vendor implementation.
- `hsm`: external signing/HSM adapter contract. The reference implementation provides configuration and health checks, not a vendor-specific HSM implementation.

## Security invariants
- secret export MUST remain `DISABLED`;
- private-key return MUST remain `DISABLED`;
- unavailable active providers MUST fail closed;
- filesystem fallback MUST NOT occur implicitly;
- provider identity is metadata, not proof of provider availability;
- provider health checks MUST NOT print secret material.

## Artifacts
```text
.ai/federation/secure/KEY-PROVIDERS.yaml
.ai/federation/secure/KEY-REFERENCES.yaml
.ai/federation/secure/KEY-STORAGE-HEALTH.yaml
.ai/federation/secure/KEY-STORAGE.yaml
.ai/federation/secure/KEY-CUSTODY-AUDIT.jsonl
.ai/federation/secure/KEY-CUSTODY.md
```

## CLI
```bash
python tools/uaf.py key-storage check <project> --json
python tools/uaf.py key-storage inventory <project> --json
python tools/uaf.py key-storage set-active <project> --provider filesystem
python tools/uaf.py key-storage register <project> --key-id KEY-001 --provider kms --purpose federation-signing
```

`set-active` refuses an unavailable provider. `register` records only key metadata and never prints or stores raw secret material.

## Adapter boundary
External KMS/HSM implementations are intentionally adapter-defined. UAAF does not claim that a cloud or HSM integration exists merely because `kms` or `hsm` appears in configuration. A real adapter MUST provide a non-secret health operation and a signing/key-custody contract appropriate to the provider.

## Compatibility
v2.7 key lifecycle remains valid. v2.8 upgrades the storage metadata schema to `2.8` and adds provider-custody artifacts; transport authority, protocol negotiation, encryption, and lifecycle semantics are unchanged.
