# UAAF v1.2 Extensions

Status: additive extension specification
Base: UAAF v1.1 / UAAF v1.0 core

## 1. Compatibility

UAAF v1.2 is optional. A v1.0 or v1.1 project remains valid when v1.2 extensions are absent.

## 2. Memory Compaction Contract

Memory compaction reduces duplicate retrieval surface while preserving an auditable history.

Canonical area:

```text
.ai/memory/compaction/
```

The default operation is dry-run. Apply mode may archive duplicate entries, rebuild `MEMORY.md`, and create a compaction report. It must not silently delete knowledge.

Compaction is conservative:

```text
SCAN
→ NORMALIZE
→ CLUSTER DUPLICATES
→ SELECT CANONICAL
→ PREVIEW
→ APPLY (explicit)
→ ARCHIVE
→ REINDEX
→ VERIFY
```

The implementation MUST preserve the original memory ID in archived artifacts and record `superseded_by` in the compaction report.

Duplicate detection is deterministic and may use lexical similarity. Semantic merging of materially different memories is out of scope for v1.2.

## 3. Strong RCE Contract

Strong RCE extends the baseline RCE with fingerprint-based reality snapshots.

Canonical baseline:

```text
.ai/health/REALITY-INDEX.yaml
```

Operations:

```text
uaf rce snapshot
uaf rce scan
```

`snapshot` records SHA-256 fingerprints for relevant referenced files. `scan` compares current reality with the snapshot and reports:

```text
CONSISTENT
DRIFT
CONFLICT
UNKNOWN
```

Strong RCE also checks:

- canonical source-of-truth paths;
- evidence source existence;
- memory source existence, including TASK/DEC/EVD/MEM identifiers;
- impact-graph path existence;
- baseline fingerprint changes.

Strong RCE is read-only during scan. It must not rewrite canonical knowledge to resolve contradictions.

## 4. Safety

Memory compaction and Strong RCE are advisory by default. Any operation that changes project files must be explicit and auditable.

## 5. Non-goals

The v1.2 extension does not require:

- vector databases;
- embeddings;
- probabilistic conflict resolution;
- automatic semantic rewriting;
- remote storage;
- destructive garbage collection.
