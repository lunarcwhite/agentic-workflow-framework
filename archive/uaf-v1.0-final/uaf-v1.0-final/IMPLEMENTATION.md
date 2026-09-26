# UAAF v1.0 Implementation Map

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
| Reference project | `examples/northstar/` | validated |
| Profile generation | Minimal / Standard / Full | validated |
| Automated tests | `tests/` | 5 passed |

## Read-only safety

`uaf_check.py`, `uaf_reconcile.py`, and `uaf_migration_check.py` are read-only. `uaf_contract.py --write` performs only mechanical fingerprint insertion into the selected YAML task contract.
