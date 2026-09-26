# UAAF Project Scaffold

This project contains the UAAF project-side knowledge and protocol artifacts. The UAAF implementation tools remain in the distribution package under `tools/` and are not copied into initialized projects.

## Initialize

Run from the UAAF distribution:

```bash
python tools/uaf_init.py ./my-project --profile standard --auto-detect --docs auto
```

## Validate

```bash
python tools/uaf_check.py ./my-project --level standard
python tools/uaf_reconcile.py ./my-project
python tools/uaf_doctor.py ./my-project --level standard
```

Profiles: `minimal`, `standard`, `full`.

Documentation modes: `--docs auto` (default for standard/full), `--docs all`, or `--docs none`.

The initializer preserves existing project files by default and never invents project facts.


## UAAF v2.0 Federation Reference

This reference project demonstrates the Full-profile UAAF v2.0 federation namespace, signed local identity, signed federation policy, replay store, and vector-clock state files. Private signing keys are kept outside the project.
