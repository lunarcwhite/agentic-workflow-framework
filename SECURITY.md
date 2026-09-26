# Security Policy

The Universal AI Agent Framework (UAAF) takes security seriously, particularly given its cryptographic boundaries, key custody abstractions, and federated peer-to-peer transport layers.

---

## Supported Versions

Only the latest active minor release receives active security patches. Critical security fixes may be backported to previous major/minor versions at the maintainers' discretion.

| Version | Supported          | Security Maintenance Level |
| :---    | :---:              | :---                       |
| 3.0.x   | :white_check_mark: | Full Active Support        |
| 2.9.x   | :warning:          | Critical Fixes Only        |
| < 2.9   | :x:                | End of Life (Unsupported)  |

---

## Cryptographic & Security Boundaries

UAAF implements strict security guarantees within its federation runtime:

1. **Non-Secret Key Custody**: Private key material must never be exported in plaintext or persisted directly in public version control. Key operations (`sign`, `handshake`, `decrypt`) are resolved through custody provider references (`filesystem`, `os-keychain`, `kms`, `hsm`).
2. **Confidential Transport**: Peer-to-peer communication uses authenticated ephemeral key agreement (X25519) combined with ChaCha20-Poly1305 symmetric authenticated encryption.
3. **Fail-Closed Policy**: If identity verification, handshake integrity, or key lifecycle health checks fail, channels are immediately closed or revoked.
4. **Anti-Drift & Anti-Slop Safeguards**: The framework enforces verified evidence collection (`evidence-receipt.yaml`) and task contract invariants before transitions can be declared complete.

---

## Reporting a Vulnerability

We request that you do **not** report security vulnerabilities via public GitHub issues.

### Reporting Process

1. **Private Advisory**: Report vulnerabilities privately via **[GitHub Private Vulnerability Reporting](https://github.com/lunarcwhite/universal-agent-framework/security/advisories/new)** on this repository.
2. **Alternative Disclosure**: If GitHub Private Vulnerabilities are unavailable, contact the project maintainers directly via repository issues by requesting a secure communication channel.

### What to Include

When reporting a vulnerability, please provide:
- A detailed description of the vulnerability and its potential impact.
- Affected components (e.g., `tools/uaf_crypto.py`, `tools/uaf_federation_transport.py`, `tools/uaf_key_ops.py`).
- Step-by-step reproduction instructions or a minimal proof-of-concept (PoC).
- Any proposed mitigations or patch suggestions if available.

### Response Timeline

- **Initial Response**: Within 48 hours acknowledging receipt of your report.
- **Triage & Assessment**: Within 5 business days detailing the severity assessment and remediation timeline.
- **Coordinated Disclosure**: A public security advisory and patched release will be coordinated once the fix is verified.

---

## Bug Bounty & Credits

We maintain a responsible disclosure hall of fame in release notes acknowledging researchers who responsibly report verified security vulnerabilities.
