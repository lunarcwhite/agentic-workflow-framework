# UAAF v1.0 Implementation Map

| Concern | Artifact | Status |
|---|---|---|
| Agent kernel | `AGENTS.md`, `.ai/core/` | baseline |
| Manifest | `.ai/manifest.yaml` | baseline |
| Task contract | `templates/task-contract.yaml` | baseline |
| Context receipt | `templates/context-receipt.yaml` | baseline |
| Evidence receipt | `templates/evidence-receipt.yaml` | baseline |
| Change manifest | `templates/change-manifest.yaml` | baseline |
| Handoff | `templates/handoff.md` | baseline |
| Initialization | `tools/uaf_init.py` | working |
| Conformance | `tools/uaf_check.py` | working baseline |
| Reality/consistency | `tools/uaf_reconcile.py` | working baseline |
| Reference project | `../uaf-northstar-demo/` in distribution archive | validated |

The baseline tools are intentionally read-mostly. Full semantic conformance, traceability, migration orchestration, and advanced RCE remain implementation expansion areas.
