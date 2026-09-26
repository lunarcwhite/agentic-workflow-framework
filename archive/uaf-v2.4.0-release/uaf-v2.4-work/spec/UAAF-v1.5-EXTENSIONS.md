# UAAF v1.5 Extensions

UAAF v1.5 is additive over v1.0–v1.4. It introduces measurable observability for context economics and engine effectiveness without changing the semantics of intent, planning, verification, memory, RCE, Git traceability, or claims.

## 1. Context Economics & Observability

Artifact directory:

- `.ai/observability/POLICY.yaml`
- `.ai/observability/EVENTS.jsonl`
- `.ai/observability/README.md`
- `.ai/observability/reports/` (generated reports)

Tool:

```bash
python tools/uaf.py observe ./my-project report
python tools/uaf.py observe ./my-project check
```

### Principles

1. Observability is metadata-first. Prompt contents and source contents MUST NOT be copied into the event log.
2. Context cost uses an explicitly documented estimate, not a false claim of exact model tokenization.
3. Metrics are measurements, not a universal score.
4. Missing telemetry is reported as `NOT_ENOUGH_DATA`, not as zero.
5. Default reporting is read-only.
6. Event recording is append-only and bounded to task/session metadata.

## 2. Context Economics

The baseline metrics are:

- estimated context tokens total/average/max;
- context depth distribution;
- repeated retrieval path rate;
- declared context use rate when the receipt contains `usage.used` and `usage.unused`.

`estimated_tokens` uses a simple size-based heuristic and must not be represented as exact provider token usage.

## 3. Memory Economics

Baseline memory metrics are:

- active/reviewable entry count;
- stale/suspect rate;
- latest compaction ratio;
- memory retrieval count;
- memory reuse rate when explicit memory-reuse events exist.

No memory item is automatically deleted because of an observability threshold.

## 4. Engine Effectiveness

Append-only events may record:

```text
context_load
memory_reuse
gate
replan
```

The reporting layer can expose:

- Delivery Gate DONE rate;
- memory reuse rate;
- replans per observed task;
- context repetition.

These are diagnostic measurements, not agent rankings.

## 5. Budgets

The default policy contains configurable guardrails:

```yaml
budgets:
  max_average_context_tokens: 12000
  max_declared_unused_rate: 0.40
  max_repeated_path_rate: 0.35
  max_memory_stale_rate: 0.25
  min_memory_reuse_rate: 0.25
  max_replans_per_task: 2.0
```

A threshold violation yields `WARN`; it does not silently mutate the project.

## 6. Privacy

The observability layer explicitly stores:

```yaml
privacy:
  store_content: false
  store_prompt: false
  store_secret_values: false
```

The recorder strips `prompt`, `content`, and `secret` fields even when supplied accidentally.

## 7. Compatibility

v1.5 requires the Full profile when enabled through the reference initializer and includes v1.1–v1.4 extension layers cumulatively.

A v1.0–v1.4 project remains valid without v1.5 observability artifacts.
