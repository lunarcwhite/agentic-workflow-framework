# Northstar — UAAF v2.6 Reference Project

Northstar is a deliberately small reference project for exercising the UAAF Full profile and the v2.6 confidential federation transport layer.

It includes a minimal implementation surface plus project-side `.ai/` knowledge. Private keys, live federation contracts, and production transport credentials are intentionally absent.

Expected fresh-project state:

```text
uaf check   → PASS_WITH_WARNINGS
uaf doctor  → PASS
secure      → NOT_CONFIGURED
```

To enable confidential federation, establish the UAAF v2.4 protocol contract and trusted peer roots first, then use `federation-confidential` for channel establishment and message exchange.
