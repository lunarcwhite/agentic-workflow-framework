# UAAF Agent Kernel

Read `.ai/manifest.yaml`, `.ai/core/*`, `.ai/memory/STATE.md`, and `.ai/INDEX.md` before consequential work.

## Golden rules
- Understand before changing.
- Inspect before inventing.
- Search before creating.
- Reuse → extend → modify → create.
- Preserve user intent.
- Never silently expand scope.
- Treat memory as hypothesis until consequential facts are verified.
- Evidence before completion claims.
- Keep changes minimal and complete.
- Persist durable knowledge and leave a useful handoff.
- Framework lifecycle records (`.ai/memory/STATE.md`, `.ai/evidence/`, `.ai/tasks/`) are always authorized for tracking status, blockers, and handoffs without violating task `permitted_files`.
- Out-of-scope defects or environment anomalies must be recorded in `.ai/memory/STATE.md` (or via `python tools/uaf.py blocker`), not left solely in chat.

Follow the active UAP lifecycle and the project manifest. Project-specific canonical sources override generic defaults within their domain.
