# UAAF v2.9 — Secure Key Operations & Provider-backed Signing

## Purpose
Turn v2.8 key custody into an operational signing interface without exporting private keys.

## Rules
1. Operations use key references rather than private-key paths as the preferred interface.
2. Providers perform signing inside the custody boundary.
3. Private key export and private-key return are disabled.
4. Provider identity and key reference must match the active provider.
5. Registered public fingerprint must match the signing key.
6. Unavailable providers fail closed; no implicit provider fallback.
7. Federation handshake MAY use provider-backed signing via `--key-ref`.
8. Legacy `--private-key` remains for backward compatibility.
9. Audit records must be hash chained and must not contain secret material.
