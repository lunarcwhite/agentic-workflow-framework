# UAAF v2.3 — Federation Policy Enforcement & Negotiation

**Status:** Release Candidate
**Version:** 2.3.0
**Protocol:** UAAF-FED-2.3

## Purpose
v2.3 separates federation policy intelligence from federation policy enforcement. A peer may negotiate a bounded capability contract, but negotiation MUST NOT broaden authority.

## Negotiated capability contract
A negotiated contract is the restrictive intersection of local effective policy and remote offer:

- allowed actions: intersection, then deny set wins;
- max risk: most restrictive ceiling;
- minimum evidence: strongest floor;
- domains: intersection when both peers constrain domains; otherwise the non-empty domain set;
- disjoint constrained domains produce `domain_scope: NONE` and MUST deny the contract;
- domain scope is `ALL`, `SET`, or `NONE`; an empty domain list MUST NOT silently imply `ALL` when both peers constrain domains;
- signed handoff/state and approval requirements: logical OR.

An empty allowed-action set or `domain_scope: NONE` produces `DENIED`. A contract that exceeds either input is invalid.

## Negotiation
Negotiation is advisory until an explicit enforcement step consumes an active contract. Remote offers MAY be signature-verified against the trusted peer root when authenticated negotiation is required.

## Enforcement
Enforcement is deny-first. A request is `AUTHORIZED` only when a valid `NEGOTIATED` contract exists and action, risk, evidence, domain, signature, and approval requirements are satisfied. Otherwise it returns `DENIED` or `REVIEW_REQUIRED`.

Offline, remote, or negotiated capability data MUST NOT increase local authority.

## Capability vs authority
A negotiated capability contract describes mutually permitted federation behavior. It does not grant authority beyond local root policy, local delegation constraints, current revocation state, or agent trust.

## Conformance
`CONF-V23-*` checks Full profile, cumulative federation protocols, v2.3 namespace/schema, default-deny enforcement, domain-scope correctness, non-escalation, and valid negotiated state.

## Safety
v2.3 MUST NOT silently broaden authority, auto-approve requirements, bypass signatures, resolve semantic conflicts, or treat a remote offer as sufficient authority without local enforcement checks.
