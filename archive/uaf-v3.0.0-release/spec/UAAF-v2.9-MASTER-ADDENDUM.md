# UAAF v2.9 Master Addendum

UAAF v2.9 preserves the v2.0-v2.8 authority, federation, transport, lifecycle, and custody semantics while adding an operational key-signing boundary.

## Normative additions

1. A key reference identifies a provider-managed signing key. Callers use the reference, not a private-key path, for the preferred v2.9 interface.
2. Providers may return signatures and public metadata but must not return private-key material.
3. Every reference is purpose-scoped. Multi-purpose use must be an explicit `allowed_purposes` set; wildcard purpose delegation is not permitted.
4. A reference may only operate while `status: ACTIVE`.
5. Rotation retires the old reference and best-effort removes its filesystem private material in the reference provider.
6. Federation confidential-channel `open`, `accept`, and `resume` may use provider-backed signing through `--key-ref`.
7. Legacy `--private-key` invocation remains backward-compatible.
8. Provider unavailability and reference mismatch fail closed.
9. Operation audit records are hash chained and contain no private-key material.

## Security boundary

The v2.9 reference filesystem provider expects `UAAF_KEY_DIR` to point to a directory outside the project repository. KMS, HSM, and OS-keychain integrations remain adapter contracts unless explicitly configured and available.
