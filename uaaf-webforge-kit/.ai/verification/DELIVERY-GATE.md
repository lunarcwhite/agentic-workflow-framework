# Delivery Gate

A task may be `DONE` only when required intent, requirements, acceptance criteria, verification, scope, and applicable quality/security/documentation gates are satisfied with honest evidence.

## Outcomes

- `DONE`
- `NOT_READY`
- `BLOCKED`

A critical failure prevents `DONE`. `NOT_RUN` is not PASS; `ASSUMED` is not evidence; `PARTIALLY_VERIFIED` is not `VERIFIED`.

## Out-of-Scope Defect Protocol
If a pre-existing defect or missing dependency outside `scope.permitted_files` is encountered:
1. Do not modify files outside permitted_files.
2. Record the defect under `## Known blockers` in `.ai/memory/STATE.md` (or run `python tools/uaf.py blocker "<message>"`).
3. If non-blocking to active code, complete primary deliverables and report the external defect in handoff. If blocking, mark task as `BLOCKED`.

