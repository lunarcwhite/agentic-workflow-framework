# Confidential Transport Security Model

Identity authentication: Ed25519.
Key agreement: ephemeral X25519.
Confidentiality + integrity: ChaCha20-Poly1305.
Key derivation: HKDF-SHA256.
Rekey: authenticated fresh ephemeral exchange per epoch.
Old ephemeral private keys are erased after successful rekey.
This layer does not claim traffic analysis resistance or availability.
