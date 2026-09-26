# UAAF v2.6.0 Release Manifest

version: 2.6.0
protocol: UAAF-FED-2.6
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
  - v2.6

v2.6_features:
  - ephemeral_x25519_key_agreement
  - hkdf_sha256_key_derivation
  - chacha20_poly1305_aead
  - per_epoch_keys
  - directional_keys
  - authenticated_rekey
  - old_ephemeral_key_file_removal
  - contract_hash_binding
  - peer_project_binding
  - fail_closed_confidential_channel

security:
  confidentiality_provided: true
  integrity_provided: true
  authentication_model: Ed25519_plus_AEAD
  key_agreement: X25519
  cipher_suite: ChaCha20-Poly1305
  kdf: HKDF-SHA256
  traffic_analysis_resistance: false
  memory_zeroization_guarantee: false
  private_keys_in_archive: false

validation:
  dedicated_v26_tests: 9/9
  field_archetypes: 5/5
  manual_e2e: PASS
  fresh_reference_doctor: PASS
  archive_smoke: PASS
  private_keys_in_archive: 0
  cache_artifacts_in_archive: 0

notes:
  - v2.6 secure transport requires an active v2.4 protocol contract with confidential-transport enabled.
  - The reference implementation provides confidentiality and integrity for payloads, but does not claim traffic-analysis resistance, availability, or process-memory zeroization.
