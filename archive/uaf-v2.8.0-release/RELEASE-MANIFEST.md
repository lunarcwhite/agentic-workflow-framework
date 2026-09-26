# UAAF v2.8.0 Release Manifest

version: 2.8.0
base: 2.7.0

included:
  key_custody:
    - KEY-PROVIDERS.yaml
    - KEY-REFERENCES.yaml
    - KEY-STORAGE-HEALTH.yaml
    - KEY-STORAGE.yaml
    - KEY-CUSTODY-AUDIT.jsonl
    - KEY-CUSTODY.md
  tools:
    - tools/uaf_key_storage.py
  specification:
    - spec/UAAF-v2.8-EXTENSIONS.md

security:
  private_keys_bundled: false
  secret_export: DISABLED
  private_key_return: DISABLED
  filesystem_fallback: false

adapter_scope:
  os_keychain: optional
  kms: contract_only
  hsm: contract_only

validation:
  v2_8_tests: 8
  v2_8_tests_passed: 8
  field_suites: 2
  field_suites_passed: 2
  doctor: PASS
  archive_smoke: PASS
