# UAAF v2.5.0 Release Manifest

version: 2.5.0
protocol: UAAF-FED-2.5
profile_requirement: full

components:
  - core
  - v1.1
  - v1.2
  - v1.3
  - v1.4
  - v1.5
  - v1.6
  - v1.7
  - v1.8
  - v1.9
  - v2.0
  - v2.1
  - v2.2
  - v2.3
  - v2.4
  - v2.5

v2.5_features:
  - channel_handshake
  - session_binding
  - signed_messages
  - sequencing
  - anti_replay
  - secure_resume
  - transport_audit
  - deny_on_missing_v24_contract

security:
  confidentiality_provided: false
  private_keys_in_archive: false
  transport_model: transport_agnostic_reference
