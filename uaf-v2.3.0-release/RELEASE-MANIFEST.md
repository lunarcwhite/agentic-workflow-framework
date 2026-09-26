# UAAF v2.3.0 Release Manifest

version: 2.3.0
protocol: UAAF-FED-2.3
status: release-candidate
required_profile: full

features:
  federation_policy_negotiation: true
  bounded_capability_contracts: true
  deny_first_enforcement: true
  non_escalating_domain_scope: true
  compact_doctor: true
  conformance_v23: true

validation:
  core_verified: 12
  v22_verified: 7
  v23_verified: 10
  field_suite_verified: 1

security:
  private_keys_in_release: false
  remote_offer_signature_optional: true
  enforcement_default_deny: true
