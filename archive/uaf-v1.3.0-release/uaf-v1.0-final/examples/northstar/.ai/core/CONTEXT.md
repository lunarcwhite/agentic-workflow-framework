# Project Context

## Purpose
Northstar is a small task-management reference application used to exercise the UAAF workflow.

## Users
Authenticated project members manage tasks through a web interface and JSON API.

## Stack
Reference application uses Python for the demonstration backend and a lightweight local data store.

## Architecture summary
The application separates task service logic from the transport layer. The reference project is intentionally small so UAAF behavior can be inspected easily.

## Constraints
Keep the implementation dependency-light and avoid speculative abstractions.

## Special cases
Task IDs are stable identifiers. State changes should remain traceable to an explicit task contract.
