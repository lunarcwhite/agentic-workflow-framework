# Transport Security Model

Authentication: Ed25519 signatures.
Integrity: payload hashes + signatures.
Replay protection: channel sequence numbers.
Session binding: negotiated protocol contract hash + channel nonce.
Reconnect: signed resume token.
Confidentiality: NOT PROVIDED by this layer.
