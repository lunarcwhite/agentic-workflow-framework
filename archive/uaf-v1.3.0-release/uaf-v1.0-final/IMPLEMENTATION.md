# UAAF v1.1.0 Implementation Map

| Concern | Artifact | Status |
|---|---|---|
| Master specification | `spec/UAAF-v1.0-MASTER-SPEC.md` | specification freeze candidate |
| Conformance catalog | `spec/UAAF-C-1.0-CONFORMANCE.md` | implemented |
| Agent kernel | `scaffold/AGENTS.md`, `scaffold/.ai/core/` | implemented |
| Adaptive initializer | `tools/uaf_init.py` | implemented |
| Conformance validator | `tools/uaf_check.py` | implemented |
| Contract fingerprint | `tools/uaf_contract.py` | implemented |
| Reality / consistency baseline | `tools/uaf_reconcile.py` | implemented |
| Migration validator | `tools/uaf_migration_check.py` | implemented |
| Diagnostic aggregator | `tools/uaf_doctor.py` | implementation preview |
| Reference project | `examples/northstar/` | validated |
| Profile generation | Minimal / Standard / Full | validated |
| Automated tests | `tests/` | 21 passed |

## Read-only safety

`uaf_check.py`, `uaf_reconcile.py`, and `uaf_migration_check.py` are read-only. `uaf_contract.py --write` performs only mechanical fingerprint insertion into the selected YAML task contract.


Field validation is documented in `FIELD-VALIDATION-REPORT.md`. v1.1 extensions are implemented in `spec/UAAF-v1.1-EXTENSIONS.md`; the remaining roadmap is documented in `V1.1-PROPOSAL.md`. Protocol semantics remain UAAF 1.0; 1.1.0 is an implementation patch.


## UAAF v1.1 implementation increment

| Extension | Artifact | Status |
|---|---|---|
| Capability Override | `tools/uaf_capabilities.py`, `.ai/capabilities.yaml` | implemented |
| Context Impact Graph | `tools/uaf_context_impact.py`, `.ai/context/IMPACT-GRAPH.yaml` | implemented |
| Unified CLI | `tools/uaf.py` | implemented |
| v1.1 validation | `tests/test_v11.py` | implemented |

Both extensions are additive. A v1.0 initialization does not emit v1.1 extension artifacts unless `--extension v1.1` is explicitly supplied.


## UAAF v1.2 implementation

Memory compaction is conservative, deterministic, dry-run by default, and archives duplicate entries instead of deleting them. Strong RCE uses SHA-256 reality snapshots over referenced files and reports later drift. Both features are optional and do not alter UAAF v1.0 semantics.
