# UAAF v2.5 — Secure Federation Transport

**Status:** Release Candidate
**Version:** 2.5.0
**Protocol:** UAAF-FED-2.5
**Profile:** Full only

## Purpose

v2.5 defines a transport-session layer above the v2.4 negotiated protocol contract. The reference implementation is transport-agnostic and uses files as a loopback/reference carrier. It provides authentication, integrity, session binding, message sequencing, reconnect/resume, and replay protection.

**It does not provide confidentiality.** Ed25519 signatures provide authenticity and integrity, not encryption.

## Channel lifecycle

```text
OPEN REQUEST
↓
ACCEPT
↓
CONFIRM
↓
OPEN
↓
SEND / RECEIVE
↓
RESUME when reconnecting
```

The initiator remains `OPENING` until a signed peer `CHANNEL_ACCEPT` is confirmed. The accepting peer creates the corresponding `OPEN` channel state.

## Session binding

A channel binding is derived from:

- channel ID;
- local project ID;
- local peer identity ID;
- remote peer identity ID;
- remote project ID;
- negotiated v2.4 contract hash;
- negotiated protocol family/version;
- channel nonce.

A message or resume token with a different binding is denied.

## Authentication and integrity

Channel open, accept, data messages, and resume tokens use Ed25519 detached signatures with purpose-specific envelopes:

- `federation-transport-channel-open`
- `federation-transport-channel-accept`
- `federation-transport-message`
- `federation-transport-channel-resume`

The receiver verifies the signer against a pinned peer public key under `.ai/federation/peers/<peer-id>/ROOT.pub.pem`.

## Audience binding

Identity and project identifiers are separate fields. `peer identity ID` MUST NOT be used as a substitute for `project ID`.

Messages are accepted only when the audience project matches the receiver's local project.

## Sequencing and replay protection

Every data message has a monotonically increasing sequence number per channel. The reference receiver requires the exact next sequence value.

Therefore:

- duplicate messages are rejected;
- skipped messages are rejected;
- stale/out-of-order messages are rejected;
- a previously accepted message cannot be replayed successfully.

Reconnect uses a signed `resume_epoch`. A resume token whose epoch is not newer than the channel state is rejected.

## Secure reconnect

Resume binds to the original channel binding and records the sender/receiver sequence state. Resume is authenticated by signature and bounded by timestamp/expiry.

A reconnect does not grant new authority. It only restores transport state for an already valid negotiated contract.

## Transport security boundary

v2.5 guarantees:

```text
AUTHENTICITY
INTEGRITY
AUDIENCE BINDING
SESSION BINDING
SEQUENCING
ANTI-REPLAY
SIGNED RECONNECT
```

v2.5 does not guarantee:

```text
CONFIDENTIALITY
TRAFFIC HIDING
NETWORK-LEVEL AVAILABILITY
```

An encrypted network transport may be layered underneath this protocol without changing UAAF authority semantics.

## Canonical artifacts

```text
.ai/federation/transport/CHANNELS/
.ai/federation/transport/INBOX/
.ai/federation/transport/OUTBOX/
.ai/federation/transport/AUDIT.jsonl
```

Each channel record is schema `2.5`.

## CLI

```bash
python tools/uaf.py federation-transport open ...
python tools/uaf.py federation-transport accept ...
python tools/uaf.py federation-transport confirm ...
python tools/uaf.py federation-transport send ...
python tools/uaf.py federation-transport receive ...
python tools/uaf.py federation-transport resume ...
python tools/uaf.py federation-transport resume-accept ...
python tools/uaf.py federation-transport check ...
```

`open` MUST NOT proceed without an active v2.4 protocol contract.

## Conformance

`CONF-V25-*` validates:

- Full profile;
- UAAF-FED-2.5 declaration;
- required transport namespaces;
- explicit non-confidential reference-layer declaration;
- authentication/integrity/anti-replay/session-binding settings;
- dependency on an active v2.4 protocol contract before a channel can open;
- channel schema and sequence invariants.

## Safety invariants

v2.5 MUST NOT:

- treat a project ID as an identity ID;
- accept a message for another project;
- accept a message with the wrong session binding;
- accept a replayed or skipped sequence number;
- accept a stale resume token;
- reopen a channel after peer-root change;
- bypass v2.3 enforcement;
- create authority through reconnect;
- claim confidentiality from signatures alone.
