# UAAF Agent Kernel — UAAF WebForge

Read `.ai/manifest.yaml`, `.ai/core/*`, `.ai/memory/STATE.md`, and `.ai/INDEX.md` before consequential work.

## Golden Rules
- Understand before changing.
- Inspect before inventing.
- Search before creating.
- Reuse → extend → modify → create.
- Preserve user intent: Build UAAF WebForge as a high-performance, stateless SaaS web tool.
- Zero-Log Privacy: Never store user prompts/conversations in server databases.
- Strictly adhere to active task perimeter in `.ai/tasks/active/`.
- Framework lifecycle records (`.ai/memory/STATE.md`, `.ai/evidence/`, `.ai/tasks/`) are always authorized for status, blockers, and handoffs without violating task `permitted_files`.
- Out-of-scope defects or environment anomalies must be recorded in `.ai/memory/STATE.md` (or via `python tools/uaf.py blocker`), not left solely in chat.
- Verifiable quality: Execute `python tools/uaf.py check` before claiming completion.

## Active Project Roadmap
1. `TASK-0001`: Backend FastAPI server, Gemini Flash client, and guardrails.
2. `TASK-0002`: SaaS Landing Page (Hero, 3-step value prop, UAAF badges, FAQ).
3. `TASK-0003`: Split-Screen Studio UI (Chat with 8-turn counter, live blueprint canvas).
4. `TASK-0004`: Dynamic in-memory UAAF ZIP packager & scaffold hydrator.
5. `TASK-0005`: Dockerfile, render.yaml, zero-cost cloud deploy verification.
