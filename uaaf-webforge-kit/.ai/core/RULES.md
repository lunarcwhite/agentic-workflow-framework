# Rules

Use IDs for project-specific hard rules.

## RULE-001
Do not fabricate project facts, implementation state, or verification results.

## RULE-002
Do not silently change user intent or add unrelated scope.

## RULE-003
Do not store secrets in UAAF documentation or memory.

## RULE-004
Framework lifecycle metadata (`.ai/memory/STATE.md`, `.ai/evidence/`, task status updates) is always authorized for tracking reality, blockers, and handoffs, regardless of task `scope.permitted_files`. Pre-existing out-of-scope defects must be recorded in `.ai/memory/STATE.md` (or via `python tools/uaf.py blocker`), not left solely in chat.

