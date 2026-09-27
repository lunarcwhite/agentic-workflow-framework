# Claude Code Directives — UAAF WebForge

This project is governed by the Universal AI Agent Framework (UAAF v3.3).
Before making any modifications:
1. Review `.ai/manifest.yaml` and `.ai/tasks/active/`.
2. Find the active task (e.g. `TASK-0001-...yaml`).
3. Only modify files listed within `scope.permitted_files` (framework records in `.ai/` are always permitted for logging status and blockers).
4. If a pre-existing out-of-scope defect is found, record it in `.ai/memory/STATE.md` (`python tools/uaf.py blocker "<message>"`); do not silently touch out-of-scope files.
5. Ensure all Python code adheres to FastAPI async best practices and PEP 8.
6. Ensure all frontend code is clean Vanilla HTML5, CSS3, and ES6 JavaScript (no heavy node_modules).
7. Run `python tools/uaf.py check` to verify deliverables before handoff.
