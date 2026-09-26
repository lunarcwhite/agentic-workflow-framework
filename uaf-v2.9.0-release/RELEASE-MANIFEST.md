# UAAF v2.9.0 Release Manifest

Version: 2.9.0
Framework: UAAF
Profile support: minimal / standard / full
v2.9 extension: Full profile

New in v2.9:
- provider-backed signing through key references
- explicit multi-purpose allowlists
- provider-side key resolution
- no private-key export/return
- provider-backed signature verification
- key rotation with old-reference retirement
- provider operation audit
- federation confidential-channel handshake integration via `--key-ref`

Release exclusions:
- private key material
- runtime key directories
- pytest caches / Python bytecode
- temporary validation projects
