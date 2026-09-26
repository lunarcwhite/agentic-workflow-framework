# UAAF v2.0 Validation Report

## Release qualification

UAAF v2.0 validation covers the distributed federation layer plus targeted regression coverage of shared v1.x tooling.

```text
v2.0 federation scenarios        8/8   PASS
compatibility smoke              7/7   PASS
field validation                 5/5   PASS
Northstar strict conformance           PASS
Northstar federation doctor            PASS
release extraction smoke               PASS
private-key/package scan               PASS
```

## v2.0 scenarios

```text
initializer + legacy cleanup
cross-project identity + signed handoff + replay
tampered peer identity fail-closed
distributed state merge + conflict
federation deny-by-default action policy
strict cumulative conformance + unified CLI
identity schema tamper + audience mismatch
federation policy signature tamper fails conformance
```

## Compatibility smoke

```text
core profile conformance                     PASS
v1.1 initializer + capability override      PASS
v1.8 initializer + conformance              PASS
v1.9 initializer + bounded doctor           PASS
v1.9 strict signed-bundle conformance       PASS
v2.0 initializer + doctor                   PASS
v2.0 strict signed federation conformance   PASS
```

## Known harness behavior

The combined subprocess-heavy pytest runner can exceed the execution harness timeout even when individual tests pass. Acceptance therefore uses fresh-process exit codes for isolated tests. A harness timeout is not counted as a framework failure.

## Security

Private signing keys are excluded from the repository and release archive. v2 federation rejects tampered identity/policy signatures, audience mismatches, replayed envelopes, expired envelopes, unallowlisted actions, and divergent concurrent state without silently resolving the conflict.
