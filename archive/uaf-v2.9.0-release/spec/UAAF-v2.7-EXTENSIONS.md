# UAAF v2.7 — Secure Key Lifecycle & Channel Management

## Status
Release extension for UAAF v2.7.0.

## Purpose
Menetapkan lifecycle eksplisit untuk channel dan key material setelah v2.6:
- close;
- expiry;
- revocation;
- retirement;
- recovery;
- secure-storage abstraction.

## Normative Rules

### 1. Terminal States
Channel lifecycle states yang terminal:

```text
CLOSED
EXPIRED
REVOKED
RECOVERY_REQUIRED
```

Terminal state tidak boleh berubah kembali menjadi `OPEN` melalui recovery biasa.

### 2. Fail-Closed Transport
Transport v2.6 harus menolak `send`, `receive`, dan `rekey` ketika lifecycle state bukan `OPEN`.

### 3. Expiry
`expires_at` yang sudah lewat membuat channel efektif `EXPIRED` dan key aktif harus dipensiunkan ketika expiry diproses.

### 4. Revocation
Revocation bersifat monotonic melalui `revocation_epoch`. Revoked channel tidak boleh direaktivasi.

### 5. Key Retirement
Key aktif yang terkait channel terminal harus tidak lagi tersedia sebagai live private-key file.

Reference filesystem provider menggunakan `unlink`/file retirement sebagai best-effort deletion. UAAF tidak mengklaim forensic secure erasure dari filesystem biasa.

### 6. Recovery
Jika private state lokal hilang pada channel yang sebelumnya aktif:

```text
ACTIVE CHANNEL
→ RECOVERY_REQUIRED
→ NEW AUTHENTICATED HANDSHAKE
```

UAAF tidak menghidupkan kembali channel lama tanpa private state.

Jika channel sudah `REVOKED`, `EXPIRED`, atau `CLOSED`, recovery hanya menghasilkan rekomendasi `requires_new_handshake=true` dan mempertahankan terminal status.

### 7. Secret Export
Key storage policy harus menggunakan:

```yaml
secret_export: DISABLED
```

### 8. Provider Abstraction
Provider yang dikenali:

```text
filesystem
os-keychain
kms
hsm
```

Reference implementation v2.7 mengimplementasikan `filesystem`. Provider lain merupakan integration surface dan tidak boleh diwakili seolah-olah sudah terintegrasi.

## Canonical Artifacts

```text
.ai/federation/secure/LIFECYCLE.yaml
.ai/federation/secure/KEY-REVOCATIONS.yaml
.ai/federation/secure/KEY-STORAGE.yaml
.ai/federation/secure/AUDIT.jsonl
```

## CLI

```bash
uaf key-lifecycle check <project>
uaf key-lifecycle inventory <project>
uaf key-lifecycle close <project> --channel-id SC-...
uaf key-lifecycle expire <project> --channel-id SC-...
uaf key-lifecycle revoke <project> --channel-id SC-...
uaf key-lifecycle retire <project> --channel-id SC-...
uaf key-lifecycle recover <project> --channel-id SC-...
```

## Security Boundary

v2.7 mengelola lifecycle. Ia tidak mengubah:
- authority model;
- trust-root model;
- protocol negotiation;
- cipher suite v2.6;
- policy enforcement v2.3.

## Verification
Release wajib membuktikan:
- terminal state fail-closed;
- expired key retirement;
- monotonic revocation;
- recovery without resurrection;
- secret export disabled;
- downgrade ke v2.6 menghapus artefak v2.7 tanpa menghapus namespace v2.6.
