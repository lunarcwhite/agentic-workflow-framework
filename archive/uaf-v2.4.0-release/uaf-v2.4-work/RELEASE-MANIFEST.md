# UAAF v2.4.0 Release Manifest

version: 2.4.0
protocol: UAAF-FED-2.4
status: release-candidate
archive_entries: 688
archive_acceptance: PASS
required_profile: full

features:
  capability_exchange: true
  protocol_negotiation: true
  version_compatibility: true
  explicit_bilateral_fallback: true
  feature_compatibility: true
  signed_capability_offers: true
  deny_first_authorization: true
  protocol_audit: true
  conformance_v24: true

validation:
  v24_verified: 12
  field_suite_verified: 1
  exact_match: true
  signed_offer: true
  tamper_rejection: true
  incompatible_protocol_rejection: true
  fallback_bilateral_declaration: true
  required_feature_rejection: true
  downgrade_to_v23: true
  doctor: true

security:
  private_keys_in_release: false
  unknown_capability_means_supported: false
  silent_fallback: false
  protocol_authority_escalation: false
