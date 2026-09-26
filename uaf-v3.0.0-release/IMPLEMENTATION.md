# UAAF Implementation Notes

The reference implementation is distribution-side tooling plus adaptive project scaffolds. Project-side private key material is never bundled.

## v2.9
`uaf_key_ops.py` resolves key references through the active custody provider, performs signing without returning private-key bytes, supports public-reference verification, and rotates references with explicit retirement of the old key. `uaf_federation_confidential.py` accepts `--key-ref` for provider-backed signing while retaining the legacy `--private-key` path for compatibility.
