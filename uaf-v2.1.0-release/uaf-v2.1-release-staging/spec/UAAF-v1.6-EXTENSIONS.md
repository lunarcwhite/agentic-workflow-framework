# UAAF v1.6 Extensions

UAAF v1.6 is cumulative over v1.0-v1.5. It introduces Adaptive Learning & Context Optimization (ALCO) using v1.5 metadata-first telemetry as advisory evidence.

## 1. Purpose

The extension identifies recurring retrieval waste, low-value memory reuse, repeated replanning, and weak delivery-gate outcomes. It produces recommendations that may be reviewed and explicitly adopted.

## 2. Artifact Surface

```text
.ai/optimization/POLICY.yaml
.ai/optimization/ANALYSIS.yaml
.ai/optimization/PROPOSALS.yaml
.ai/optimization/README.md
```

## 3. Principles

1. Learning is advisory, not authoritative.
2. Recommendations require evidence from observed project telemetry.
3. Intent MUST NOT be changed automatically.
4. Project policy MUST NOT be mutated automatically.
5. Memory MUST NOT be deleted automatically because of low utility.
6. Missing telemetry is insufficient evidence, not evidence of failure.
7. v1.6 recommendations must remain distinguishable from accepted project policy.
8. Recommendations expire naturally when their evidence becomes stale or contradictory.

## 4. Context Optimization

The optimizer may identify loaded paths with sufficiently repeated observations and high declared unused rates. The default minimum is 3 observations and 60% unused rate.

Suggested action is retrieval-class review, not automatic removal from bootstrap or direct context.

The optimizer may also surface repeated retrieval paths as candidates for session-local caching, but does not alter CLE policy automatically.

## 5. Memory Optimization

Memory utility is derived from explicit `memory_reuse` events. A low reuse rate creates a review recommendation for retrieval selectors and memory quality.

An individual memory entry may be flagged for review when it is repeatedly retrieved without reuse evidence. No deletion occurs automatically.

## 6. Planning Optimization

A replan rate above the configured threshold produces a recommendation to inspect recurring blockers and missing prerequisites. The task contract remains unchanged unless an authorized actor explicitly revises it.

## 7. Delivery Optimization

A low Delivery Gate DONE rate produces a recommendation to inspect recurring evidence or implementation failures. Gates must never be weakened solely to improve the metric.

## 8. Recommendation Contract

Each recommendation contains at least:

```yaml
id:
type:
target:
status: PROPOSED
confidence:
reason:
suggested_action:
evidence:
safety: ADVISORY_ONLY
```

Valid statuses:

```text
PROPOSED
ACCEPTED
REJECTED
EXPIRED
```

## 9. Safety Policy

Default policy:

```yaml
safety:
  auto_apply: false
  allow_policy_mutation: false
  allow_intent_mutation: false
  allow_memory_delete: false
```

Any future mechanism that changes those defaults is a semantic change and requires explicit policy/authorization plus versioning.

## 10. CLI

```bash
python tools/uaf.py adapt ./project analyze
python tools/uaf.py adapt ./project recommend
python tools/uaf.py adapt ./project analyze --write
python tools/uaf.py adapt ./project check
```

`analyze` is read-only unless `--write` is supplied. `--write` writes analysis/proposal artifacts only; it does not mutate policy, intent, memory content, or retrieval rules.

## 11. Compatibility

v1.0-v1.5 projects remain valid without `.ai/optimization/`.

A v1.6 initializer includes v1.1-v1.5 artifacts cumulatively plus the v1.6 optimization layer.
