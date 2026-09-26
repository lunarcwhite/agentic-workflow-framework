# UAAF v2.8.0 Release Validation Report

## Release result
PASS — v2.8 key-custody extension validated and packaged.

## Dedicated tests
- v2.8 provider/custody tests: 8/8 passed.
- v2.8 field archetype tests: 2/2 passed (five archetypes inside the suite plus existing Git project smoke).
- v2.8 doctor fresh-project smoke: PASS.
- v2.8 explicit downgrade to v2.7: PASS.

## Compatibility evidence
- v2.7 impacted lifecycle tests excluding the historical doctor subprocess test: 5/5 passed.
- v2.7 downgrade semantics: PASS.
- Existing core suite excluding the historical doctor subprocess test: 11/11 passed; the doctor test was independently exercised through the current v2.8 doctor path.
- Earlier v2.6 encrypted send/receive and rekey paths are retained unchanged in the source tree; no v2.8 code modifies their cryptographic primitives.

## Known harness limitation
The repository contains subprocess-heavy historical test groups. In this environment, some combined/file-level pytest runs can stall without an assertion failure. Those runs are not counted as PASS. Acceptance numbers above come from completed fresh-process/per-suite executions.

## Security checks
- No private key material is intentionally bundled.
- Provider inventory exposes metadata only.
- `secret_export` is `DISABLED`.
- `private_key_return` is `DISABLED`.
- Implicit filesystem fallback is disabled.
- External KMS/HSM support is an adapter contract and health interface only; no vendor client is falsely claimed.
