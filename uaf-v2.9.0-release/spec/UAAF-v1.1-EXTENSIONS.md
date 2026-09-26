# UAAF v1.1 Extensions

Status: additive extension specification
Base: UAAF v1.0

## 1. Compatibility

UAAF v1.1 extensions are optional. A UAAF v1.0 project remains valid when the extension layer is absent.

## 2. Capability Override Contract

The effective capability is resolved from a layered record:

```text
DETECTED
  ↓
OVERRIDE
  ↓
EFFECTIVE
```

Override values:

```text
auto
force_true
force_false
review_required
```

`force_true` and `force_false` require a traceable reason and source. `review_required` keeps the detected value as the provisional effective value while signaling that the capability should be reviewed.

Canonical extension file:

```text
.ai/capabilities.yaml
```

Required record shape:

```yaml
frontend:
  detected: true
  override: auto
  confidence: HIGH
  source: detector
  reason: ""
```

The v1.0 boolean `manifest.capabilities.*` fields remain a compatibility projection of the effective capability.

## 3. Context Impact Graph

The Context Impact Graph maps changed paths to impacted domains, capabilities, and canonical knowledge candidates.

```text
CHANGE
→ IMPACT GRAPH
→ AFFECTED KNOWLEDGE
→ TARGETED RETRIEVAL
→ FRESHNESS REVIEW
```

Canonical file:

```text
.ai/context/IMPACT-GRAPH.yaml
```

The graph is advisory in v1.1. It may recommend retrieval or review but must not silently alter source-of-truth documents.

## 4. Source of Change

The tool may use:

- explicit `--paths` input;
- Git working-tree status when available.

No Git repository is required for explicit path analysis.

## 5. Non-goals

The v1.1 extension does not require:

- vector databases;
- automatic semantic conflict resolution;
- automatic rewriting of canonical knowledge;
- mandatory online services.
