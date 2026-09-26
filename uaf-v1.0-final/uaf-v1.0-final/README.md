# UAAF v1.0

Universal AI Agent Framework reference distribution.

## Use

```bash
python tools/uaf_init.py ./my-project --profile standard --name MyProject
python tools/uaf_check.py ./my-project --level standard
python tools/uaf_reconcile.py ./my-project
```

Profiles: `minimal`, `standard`, `full`.

The installer creates only the profile-appropriate project artifacts and never invents project facts.
