# UAAF v2.2.0 Release Manifest

version: 2.2.0
protocol: UAAF-FED-2.2
status: release-candidate

included:
  core: UAAF 1.0
  extensions: v1.1, v1.2, v1.3, v1.4, v1.5, v1.6, v1.7, v1.8, v1.9, v2.0, v2.1, v2.2
  tools: unified CLI, conformance, doctor, federation policy, federation intelligence

v2.2:
  policy_inheritance: monotonic_restriction
  conflict_intelligence: advisory_only
  sync_planning: advisory_only
  checkpoint_selection: advisory_only
  recovery_recommendation: advisory_only

security:
  private_keys_in_release_tree: false
  semantic_auto_resolution: false

validation:
  v2.2: 7/7
  field_archetypes: 5/5
  core_tools: 12/12
  archive_smoke: required
