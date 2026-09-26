# UAAF v1.6 Adaptive Learning

Adaptive Learning & Context Optimization consumes v1.5 metadata-first telemetry and produces advisory recommendations for retrieval, memory, planning, and delivery-gate review.

Rules:

- recommendations are advisory, not authoritative;
- policy mutation is disabled by default;
- intent mutation is never automatic;
- memory deletion is never automatic;
- insufficient telemetry produces insufficient-data states rather than invented conclusions.

Use `uaf adapt <project> analyze` or `uaf adapt <project> recommend`.
