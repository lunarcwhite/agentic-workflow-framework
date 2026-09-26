# UAAF v2.1.0 Release Manifest

Major release baseline: UAAF 2.0
Extension release: UAAF-FED-2.1
Release class: backward-compatible operational extension

## Included

- UAAF v1.0–v1.9 specifications, tooling, and templates
- UAAF v2.0 Distributed Agent Federation
- UAAF v2.1 Federation Operations & Resilience
- Unified `uaf` CLI and adaptive initializer
- Minimal / Standard / Full scaffold
- Northstar v2.1 reference project
- Regression, longitudinal, field, federation, and v2.1 tests

## v2.1 additions

- Operational federation modes: ONLINE, OFFLINE, PARTITIONED, RECOVERING
- Idempotent sync bundles and peer cursors
- Signed revocation records and cross-peer revocation propagation
- Explicit conflict-resolution workflow
- Signed checkpoints and bounded recovery with recovery backup
- Federation operations observability
- CONF-V21 conformance and doctor integration

## Validation

- v2.1 isolated scenarios: 8/8 PASS
- v2.1 field archetypes: 5/5 PASS
- v2.1 strict conformance: PASS
- v2.1 doctor: PASS
- v2.0 downgrade isolation: PASS

## Security

Private signing keys remain outside the project. Operational modes never broaden authority. Revocation records are root-signed and verified against the pinned peer root during propagation. Recovery does not remove replay protection or unresolved conflict state.

## Packaging

Release archive excludes Python bytecode, pytest caches, private keys, test Git metadata, and staging directories. The release is verified from a fresh extraction.
