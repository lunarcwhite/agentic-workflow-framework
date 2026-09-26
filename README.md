# Universal AI Agent Framework (UAAF / UAF)

A systematic protocol, repository scaffold, and reference runtime for autonomous AI coding agents to preserve intent, eliminate hallucination/slop, verify changes with evidence, and coordinate across sessions and distributed peers.

---

## 📦 Repository Structure

This repository contains the cumulative distributions and historical evolution of UAAF from its foundational specification up to the latest release:

| Version | Focus / Milestone |
| :--- | :--- |
| [**`uaf-v3.0.1-release/`**](./uaf-v3.0.1-release) | **Latest Stable Reference**: Zero-warning fresh conformance, Federated Agent Runtime (`UAAF-FED-3.0`), signed execution leases, and key custody. |
| [**`uaf-v3.0.0-release/`**](./uaf-v3.0.0-release) | Federated Agent Runtime, remote delegation contracts, execution leases, and provenance chains. |
| [**`uaf-v2.9.0-release/`**](./uaf-v2.9.0-release) | Provider-backed Key Operations (`--key-ref`) and secure key custody. |
| [**`uaf-v2.6.0-release/`**](./uaf-v2.6.0-release) | Confidential Federation Transport (X25519 + ChaCha20-Poly1305 AEAD). |
| [**`uaf-v2.0.0-release/`**](./uaf-v2.0.0-release) | Distributed Agent Federation, cross-project identity envelopes, vector clocks. |
| [**`uaf-v1.9.0-release/`**](./uaf-v1.9.0-release) | Cryptographic Integrity, Ed25519 root anchoring, and signed trust policies. |
| [**`uaf-v1.0-complete/`**](./uaf-v1.0-complete) | Initial foundational UAAF v1.0 master specification and core engines. |

---

## 🚀 Quick Start (Using Latest v3.0.1)

### 1. Initialize a Project

To install UAF into any new or existing project:

```bash
# Standard profile (recommended for single-repo projects)
python uaf-v3.0.1-release/tools/uaf.py init /path/to/my-project --profile standard --auto-detect

# Full profile with Federated Agent Runtime
python uaf-v3.0.1-release/tools/uaf.py init /path/to/my-project --profile full --extension v3.0.1
```

### 2. Verify Conformance & Health

```bash
# Conformance check
python uaf-v3.0.1-release/tools/uaf.py check /path/to/my-project --level full

# Health diagnostics
python uaf-v3.0.1-release/tools/uaf.py doctor /path/to/my-project
```

---

## 🛡️ Core Invariants

1. **Deny-by-default**: Actions require explicit authorization and contracts.
2. **Intent Preservation**: Intent and requirements must not change silently.
3. **Evidence Required**: No completion claims without verifiable evidence receipts.
4. **No Private Keys in Repositories**: Private keys remain strictly outside project state.
5. **Capability ≠ Authority**: An agent having tools does not grant permission to execute them.

---

## 📄 License & Specifications

All normative specifications are located in the `spec/` folder of each release distribution (e.g. [uaf-v3.0.1-release/spec](./uaf-v3.0.1-release/spec)).
