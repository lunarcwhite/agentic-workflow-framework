#!/usr/bin/env python3
"""UAAF v2.6 confidential federation transport reference layer.

Adds confidentiality to the v2.5 authenticated transport using an ephemeral
X25519 key agreement, HKDF-SHA256 key derivation, ChaCha20-Poly1305 AEAD,
per-channel key epochs, authenticated rekey, and key-erasure semantics.

The layer remains transport-agnostic and uses files as a loopback/reference
carrier. Private ephemeral keys live only under .ai/federation/secure/keys and
must never be committed or bundled into releases.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SCHEMA = "2.6"
FED = Path('.ai/federation')
SECURE = FED / 'secure'
CHANNELS = SECURE / 'CHANNELS'
INBOX = SECURE / 'INBOX'
OUTBOX = SECURE / 'OUTBOX'
KEYS = SECURE / 'keys'
AUDIT = SECURE / 'AUDIT.jsonl'
MAX_CLOCK_SKEW = 300


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now().isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return value if isinstance(value, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def fp(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def project_id(root: Path) -> str:
    m = load_yaml(root / '.ai/manifest.yaml', {})
    return str((m.get('project') or {}).get('name') or root.name)


def local_peer_id(root: Path) -> str:
    cap = load_yaml(root / '.ai/federation/protocol/CAPABILITIES.yaml', {})
    return str(cap.get('peer_id') or project_id(root))


def contract(root: Path) -> tuple[str, dict[str, Any]]:
    path = root / '.ai/federation/protocol/PROTOCOL-CONTRACT.yaml'
    doc = load_yaml(path, {})
    if str(doc.get('status')) not in {'NEGOTIATED', 'FALLBACK_NEGOTIATED'}:
        raise ValueError('PROTOCOL_CONTRACT_NOT_ACTIVE')
    body = doc.get('contract') or {}
    ch = str(doc.get('contract_hash') or '')
    if not ch:
        raise ValueError('PROTOCOL_CONTRACT_HASH_MISSING')
    if fp(body) != ch:
        raise ValueError('PROTOCOL_CONTRACT_HASH_MISMATCH')
    return ch, doc


def peer_root_key(root: Path, peer_id: str) -> tuple[Ed25519PublicKey, str]:
    path = root / FED / 'peers' / peer_id / 'ROOT.pub.pem'
    if not path.exists():
        raise ValueError('REMOTE_ROOT_NOT_PINNED')
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError('REMOTE_ROOT_NOT_ED25519')
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, hashlib.sha256(raw).hexdigest()


def ed_private(path: Path) -> Ed25519PrivateKey:
    value = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(value, Ed25519PrivateKey):
        raise ValueError('PRIVATE_KEY_NOT_ED25519')
    return value


def sign(payload: dict[str, Any], private: Path, key_id: str, purpose: str) -> dict[str, Any]:
    body = canon(payload)
    signature = ed_private(private).sign(body)
    return {
        'schema_version': SCHEMA,
        'algorithm': 'Ed25519',
        'purpose': purpose,
        'key_id': key_id,
        'payload_sha256': hashlib.sha256(body).hexdigest(),
        'signature_b64': base64.b64encode(signature).decode('ascii'),
    }


def verify(payload: dict[str, Any], envelope: dict[str, Any], key: Ed25519PublicKey, purpose: str) -> tuple[bool, str]:
    if envelope.get('schema_version') != SCHEMA or envelope.get('algorithm') != 'Ed25519':
        return False, 'SIGNATURE_SCHEMA_MISMATCH'
    if envelope.get('purpose') != purpose:
        return False, 'PURPOSE_MISMATCH'
    body = canon(payload)
    if envelope.get('payload_sha256') != hashlib.sha256(body).hexdigest():
        return False, 'PAYLOAD_HASH_MISMATCH'
    try:
        key.verify(base64.b64decode(str(envelope.get('signature_b64', '')), validate=True), body)
    except (InvalidSignature, ValueError, TypeError):
        return False, 'SIGNATURE_INVALID'
    return True, 'OK'


def audit(root: Path, event: dict[str, Any]) -> None:
    p = root / AUDIT
    p.parent.mkdir(parents=True, exist_ok=True)
    prior = 'GENESIS'
    if p.exists():
        lines = [x for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
        if lines:
            try:
                prior = str(json.loads(lines[-1]).get('entry_hash', prior))
            except Exception:
                prior = 'BROKEN'
    row = {'schema_version': SCHEMA, 'timestamp': iso_now(), 'prev_hash': prior, **event}
    row['entry_hash'] = hashlib.sha256(canon(row)).hexdigest()
    with p.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')


def ensure(root: Path) -> None:
    for path in [CHANNELS, INBOX, OUTBOX, KEYS]:
        (root / path).mkdir(parents=True, exist_ok=True)
    (root / AUDIT).touch(exist_ok=True)
    # Restrict key directory as much as the local filesystem permits.
    try:
        (root / KEYS).chmod(0o700)
    except OSError:
        pass


def channel_file(root: Path, channel_id: str) -> Path:
    return root / CHANNELS / f'{channel_id}.yaml'


def load_channel(root: Path, channel_id: str) -> dict[str, Any]:
    return load_yaml(channel_file(root, channel_id), {})


def xpriv_path(root: Path, channel_id: str, epoch: int, role: str) -> Path:
    return root / KEYS / f'{channel_id}.e{epoch}.{role}.x25519.pem'


def write_xpriv(path: Path, key: X25519PrivateKey) -> None:
    ensure(path.parent.parent.parent.parent)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def read_xpriv(path: Path) -> X25519PrivateKey:
    value = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(value, X25519PrivateKey):
        raise ValueError('EPHEMERAL_KEY_NOT_X25519')
    return value


def pub_b64(key: X25519PublicKey) -> str:
    return base64.b64encode(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode('ascii')


def load_pub_b64(value: str) -> X25519PublicKey:
    raw = base64.b64decode(value, validate=True)
    if len(raw) != 32:
        raise ValueError('EPHEMERAL_PUBLIC_KEY_INVALID')
    return X25519PublicKey.from_public_bytes(raw)


def derive_session(shared: bytes, binding: str, channel_id: str, epoch: int) -> dict[str, tuple[bytes, bytes]]:
    salt = hashlib.sha256(canon({'binding': binding, 'channel_id': channel_id, 'epoch': epoch})).digest()
    material = {}
    for direction in ('i2r', 'r2i'):
        okm = HKDF(algorithm=hashes.SHA256(), length=36, salt=salt, info=(b'UAAF-v2.6-confidential-transport/' + direction.encode())).derive(shared)
        material[direction] = (okm[:32], okm[32:36])
    confirm_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b'UAAF-v2.6-confidential-transport/key-confirm').derive(shared)
    material['confirm'] = (confirm_key, b'')
    return material


def confirmation(key: bytes, binding: str, channel_id: str, epoch: int) -> str:
    msg = canon({'binding': binding, 'channel_id': channel_id, 'epoch': epoch, 'purpose': 'key-confirm'})
    return base64.b64encode(hmac.new(key, msg, hashlib.sha256).digest()).decode('ascii')


def key_for_channel(root: Path, ch: dict[str, Any], role: str, direction: str | None = None) -> tuple[bytes, str, bytes]:
    epoch = int(ch.get('key_epoch', 0) or 0)
    if epoch <= 0:
        raise ValueError('KEY_EPOCH_NOT_ESTABLISHED')
    priv_path = xpriv_path(root, str(ch['channel_id']), epoch, role)
    if not priv_path.exists():
        raise ValueError('EPHEMERAL_PRIVATE_KEY_MISSING')
    priv = read_xpriv(priv_path)
    peer_pub_value = ch.get('initiator_ephemeral_pub') if role == 'responder' else ch.get('responder_ephemeral_pub')
    if not peer_pub_value:
        raise ValueError('PEER_EPHEMERAL_PUBLIC_KEY_MISSING')
    shared = priv.exchange(load_pub_b64(str(peer_pub_value)))
    session = derive_session(shared, str(ch['binding']), str(ch['channel_id']), epoch)
    if role == 'initiator':
        chosen = direction or 'i2r'
    else:
        chosen = direction or 'r2i'
    key, prefix = session[chosen]
    return key, hashlib.sha256(key).hexdigest(), prefix


def aad(ch: dict[str, Any], seq: int, epoch: int, sender_project_id: str, sender_peer_id: str) -> bytes:
    return canon({
        'channel_id': ch['channel_id'], 'binding': ch['binding'], 'seq': seq,
        'key_epoch': epoch, 'sender_project_id': sender_project_id,
        'sender_peer_id': sender_peer_id, 'audience_project_id': ch['local_project_id'] if sender_project_id == ch['peer_project_id'] else ch['peer_project_id'],
    })


def nonce(prefix_b64: str, seq: int) -> bytes:
    prefix = base64.b64decode(prefix_b64, validate=True)
    if len(prefix) != 4 or seq < 0 or seq >= 2**64:
        raise ValueError('NONCE_COMPONENT_INVALID')
    return prefix + seq.to_bytes(8, 'big')


def require_v26_contract(root: Path) -> str:
    ch, doc = contract(root)
    protocols = (doc.get('contract') or {}).get('protocols') or {}
    version = str(protocols.get('federation_protocol', ''))
    if version != '2.4':
        raise ValueError('V26_REQUIRES_V24_PROTOCOL_CONTRACT')
    secure = (doc.get('contract') or {}).get('enabled_features') or []
    if 'confidential-transport' not in secure:
        # Secure transport may use a v2.4 contract only when the capability
        # was explicitly negotiated as an extension-level feature.
        raise ValueError('CONFIDENTIAL_TRANSPORT_NOT_NEGOTIATED')
    return ch



def assert_current_contract(root: Path, ch: dict[str, Any]) -> None:
    current_hash, _ = contract(root)
    if str(ch.get('contract_hash')) != current_hash:
        raise ValueError('PROTOCOL_CONTRACT_CHANGED')

def open_channel(root: Path, peer_id: str, peer_project_id: str, private: Path, key_id: str, out: Path | None = None) -> dict[str, Any]:
    ensure(root)
    contract_hash = require_v26_contract(root)
    _, peer_fp = peer_root_key(root, peer_id)
    channel_id = f'SC-{secrets.token_hex(6)}'
    initiator_ephemeral = X25519PrivateKey.generate()
    epoch = 1
    write_xpriv(xpriv_path(root, channel_id, epoch, 'initiator'), initiator_ephemeral)
    nonce_prefix = base64.b64encode(secrets.token_bytes(4)).decode('ascii')
    local_project = project_id(root)
    local_peer = local_peer_id(root)
    expires = (now() + timedelta(seconds=900)).isoformat(timespec='seconds').replace('+00:00', 'Z')
    binding = fp({'channel_id': channel_id, 'local_project_id': local_project, 'local_peer_id': local_peer, 'peer_id': peer_id, 'peer_project_id': peer_project_id, 'contract_hash': contract_hash, 'protocol_version': '2.6', 'key_epoch': epoch})
    payload = {
        'schema_version': SCHEMA, 'message_type': 'SECURE_CHANNEL_HELLO', 'channel_id': channel_id,
        'sender_project_id': local_project, 'sender_peer_id': local_peer,
        'audience_peer_id': peer_id, 'audience_project_id': peer_project_id,
        'protocol_family': 'federation_confidential', 'protocol_version': '2.6',
        'contract_hash': contract_hash, 'key_epoch': epoch, 'binding': binding,
        'initiator_ephemeral_pub': pub_b64(initiator_ephemeral.public_key()), 'nonce_prefix': nonce_prefix,
        'created_at': iso_now(), 'expires_at': expires,
        'cipher_suite': 'ChaCha20-Poly1305', 'key_agreement': 'X25519', 'kdf': 'HKDF-SHA256',
        'forward_secrecy_orientation': 'ephemeral_per_epoch',
    }
    payload['signature'] = sign({k: v for k, v in payload.items() if k != 'signature'}, private, key_id, 'federation-confidential-channel-open')
    channel = {
        'schema_version': SCHEMA, 'status': 'OPENING', 'channel_id': channel_id,
        'local_project_id': local_project, 'local_peer_id': local_peer,
        'peer_identity_id': peer_id, 'peer_project_id': peer_project_id,
        'peer_root_fingerprint': peer_fp, 'protocol_version': '2.6', 'contract_hash': contract_hash,
        'binding': binding, 'key_epoch': epoch, 'nonce_prefix': nonce_prefix, 'role': 'initiator',
        'initiator_ephemeral_pub': payload['initiator_ephemeral_pub'], 'responder_ephemeral_pub': None,
        'send_seq': 0, 'recv_seq': 0, 'last_received_message': None,
        'created_at': payload['created_at'], 'expires_at': expires,
    }
    dump_yaml(channel_file(root, channel_id), channel)
    hello = out or root / OUTBOX / f'{channel_id}.hello.json'
    hello.parent.mkdir(parents=True, exist_ok=True)
    hello.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    audit(root, {'event': 'SECURE_CHANNEL_OPEN_REQUESTED', 'channel_id': channel_id, 'peer_id': peer_id, 'key_epoch': epoch})
    return {'status': 'PASS', 'channel_id': channel_id, 'hello_file': str(hello), 'key_epoch': epoch, 'cipher_suite': 'ChaCha20-Poly1305'}


def accept_channel(root: Path, hello_file: Path, local_peer_id_arg: str, sender_peer_id: str, private: Path, key_id: str) -> dict[str, Any]:
    ensure(root)
    contract_hash = require_v26_contract(root)
    doc = json.loads(hello_file.read_text(encoding='utf-8'))
    sig = doc.get('signature') or {}
    payload = {k: v for k, v in doc.items() if k != 'signature'}
    if payload.get('audience_peer_id') != local_peer_id_arg or payload.get('sender_peer_id') != sender_peer_id:
        return {'status': 'DENIED', 'reason': 'CHANNEL_IDENTITY_MISMATCH'}
    if payload.get('audience_project_id') != project_id(root):
        return {'status': 'DENIED', 'reason': 'CHANNEL_AUDIENCE_PROJECT_MISMATCH'}
    if payload.get('contract_hash') != contract_hash:
        return {'status': 'DENIED', 'reason': 'CONTRACT_HASH_MISMATCH'}
    if payload.get('protocol_version') != '2.6':
        return {'status': 'DENIED', 'reason': 'V26_PROTOCOL_REQUIRED'}
    if not parse_ts(payload.get('expires_at')) or parse_ts(payload.get('expires_at')) <= now():
        return {'status': 'DENIED', 'reason': 'CHANNEL_EXPIRED'}
    key, peer_fp = peer_root_key(root, sender_peer_id)
    ok, reason = verify(payload, sig, key, 'federation-confidential-channel-open')
    if not ok:
        return {'status': 'DENIED', 'reason': reason}
    channel_id = str(payload['channel_id'])
    epoch = int(payload.get('key_epoch', 1) or 1)
    responder = X25519PrivateKey.generate()
    write_xpriv(xpriv_path(root, channel_id, epoch, 'responder'), responder)
    shared = responder.exchange(load_pub_b64(str(payload['initiator_ephemeral_pub'])))
    session = derive_session(shared, str(payload['binding']), channel_id, epoch)
    channel_key = session['confirm'][0]
    key_fp = hashlib.sha256(session['i2r'][0]).hexdigest()
    ack_payload = {
        'schema_version': SCHEMA, 'message_type': 'SECURE_CHANNEL_ACCEPT', 'channel_id': channel_id,
        'sender_project_id': project_id(root), 'sender_peer_id': local_peer_id_arg,
        'audience_project_id': payload['sender_project_id'], 'audience_peer_id': payload['sender_peer_id'],
        'contract_hash': contract_hash, 'key_epoch': epoch, 'binding': payload['binding'],
        'responder_ephemeral_pub': pub_b64(responder.public_key()),
        'key_confirmation': confirmation(channel_key, str(payload['binding']), channel_id, epoch),
        'created_at': iso_now(), 'expires_at': payload['expires_at'],
        'cipher_suite': 'ChaCha20-Poly1305', 'key_agreement': 'X25519', 'kdf': 'HKDF-SHA256',
    }
    ack_payload['signature'] = sign({k: v for k, v in ack_payload.items() if k != 'signature'}, private, key_id, 'federation-confidential-channel-accept')
    ch = {
        'schema_version': SCHEMA, 'status': 'OPEN', 'channel_id': channel_id,
        'local_project_id': project_id(root), 'local_peer_id': local_peer_id_arg,
        'peer_identity_id': sender_peer_id, 'peer_project_id': payload['sender_project_id'],
        'peer_root_fingerprint': peer_fp, 'protocol_version': '2.6', 'contract_hash': contract_hash,
        'binding': payload['binding'], 'key_epoch': epoch, 'nonce_prefix': payload['nonce_prefix'], 'role': 'responder',
        'initiator_ephemeral_pub': payload['initiator_ephemeral_pub'], 'responder_ephemeral_pub': ack_payload['responder_ephemeral_pub'],
        'send_seq': 0, 'recv_seq': 0, 'last_received_message': None,
        'created_at': payload['created_at'], 'expires_at': payload['expires_at'], 'key_fingerprint': key_fp,
    }
    dump_yaml(channel_file(root, channel_id), ch)
    out = root / OUTBOX / f'{channel_id}.accept.json'
    out.write_text(json.dumps(ack_payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    audit(root, {'event': 'SECURE_CHANNEL_ACCEPTED', 'channel_id': channel_id, 'key_epoch': epoch})
    return {'status': 'PASS', 'channel_id': channel_id, 'ack_file': str(out), 'key_epoch': epoch}


def confirm_channel(root: Path, hello_file: Path, ack_file: Path, channel_id: str, peer_id: str) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if not ch:
        return {'status': 'DENIED', 'reason': 'CHANNEL_NOT_FOUND'}
    hello = json.loads(hello_file.read_text(encoding='utf-8'))
    ack = json.loads(ack_file.read_text(encoding='utf-8'))
    payload = {k: v for k, v in ack.items() if k != 'signature'}
    if payload.get('channel_id') != channel_id or payload.get('audience_peer_id') != local_peer_id(root) or payload.get('sender_peer_id') != peer_id:
        return {'status': 'DENIED', 'reason': 'CHANNEL_CONFIRM_IDENTITY_MISMATCH'}
    key, peer_fp = peer_root_key(root, peer_id)
    ok, reason = verify(payload, ack.get('signature') or {}, key, 'federation-confidential-channel-accept')
    if not ok:
        return {'status': 'DENIED', 'reason': reason}
    if str(payload.get('binding')) != str(ch.get('binding')) or str(payload.get('contract_hash')) != str(ch.get('contract_hash')):
        return {'status': 'DENIED', 'reason': 'SESSION_BINDING_MISMATCH'}
    ch['responder_ephemeral_pub'] = payload.get('responder_ephemeral_pub')
    ch['key_epoch'] = int(payload.get('key_epoch', 0) or 0)
    ch['key_fingerprint'] = ch.get('key_fingerprint') or ''
    key_path = xpriv_path(root, channel_id, int(ch['key_epoch']), 'initiator')
    shared = read_xpriv(key_path).exchange(load_pub_b64(str(ch['responder_ephemeral_pub'])))
    session = derive_session(shared, str(ch['binding']), channel_id, int(ch['key_epoch']))
    channel_key = session['confirm'][0]
    key_fp = hashlib.sha256(session['i2r'][0]).hexdigest()
    expected = confirmation(channel_key, str(ch['binding']), channel_id, int(ch['key_epoch']))
    if not hmac.compare_digest(expected, str(payload.get('key_confirmation', ''))):
        return {'status': 'DENIED', 'reason': 'KEY_CONFIRMATION_FAILED'}
    if ch.get('peer_root_fingerprint') != peer_fp:
        return {'status': 'DENIED', 'reason': 'PEER_ROOT_CHANGED'}
    ch['key_fingerprint'] = key_fp
    ch['status'] = 'OPEN'
    dump_yaml(channel_file(root, channel_id), ch)
    audit(root, {'event': 'SECURE_CHANNEL_CONFIRMED', 'channel_id': channel_id, 'key_epoch': int(ch['key_epoch'])})
    return {'status': 'PASS', 'channel_id': channel_id, 'key_epoch': int(ch['key_epoch'])}


def send(root: Path, channel_id: str, payload: dict[str, Any], out: Path | None = None) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if str(ch.get('status')) != 'OPEN':
        return {'status': 'DENIED', 'reason': 'CHANNEL_NOT_OPEN'}
    try:
        assert_current_contract(root, ch)
    except ValueError as exc:
        return {'status': 'DENIED', 'reason': str(exc)}
    peer_id = str(ch.get('peer_identity_id'))
    _, peer_fp = peer_root_key(root, peer_id)
    if ch.get('peer_root_fingerprint') != peer_fp:
        return {'status': 'DENIED', 'reason': 'PEER_ROOT_CHANGED'}
    epoch = int(ch.get('key_epoch', 0) or 0)
    role = str(ch.get('role') or '')
    if role not in {'initiator', 'responder'}:
        return {'status': 'DENIED', 'reason': 'CHANNEL_ROLE_INVALID'}
    direction = 'i2r' if role == 'initiator' else 'r2i'
    key, key_fp, nonce_prefix = key_for_channel(root, ch, role, direction)
    seq = int(ch.get('send_seq', 0)) + 1
    sender_project = str(ch['local_project_id'])
    sender_peer = str(ch.get('local_peer_id') or local_peer_id(root))
    envelope_aad = aad(ch, seq, epoch, sender_project, sender_peer)
    ct = ChaCha20Poly1305(key).encrypt(nonce(base64.b64encode(nonce_prefix).decode('ascii'), seq), canon(payload), envelope_aad)
    doc = {
        'schema_version': SCHEMA, 'message_type': 'SECURE_DATA', 'channel_id': channel_id,
        'sender_project_id': sender_project, 'sender_peer_id': sender_peer,
        'audience_peer_id': peer_id, 'audience_project_id': ch['peer_project_id'],
        'binding': ch['binding'], 'seq': seq, 'key_epoch': epoch,
        'nonce': base64.b64encode(nonce(base64.b64encode(nonce_prefix).decode('ascii'), seq)).decode('ascii'),
        'ciphertext_b64': base64.b64encode(ct).decode('ascii'),
        'aad_sha256': hashlib.sha256(envelope_aad).hexdigest(), 'key_fingerprint': key_fp,
        'created_at': iso_now(), 'expires_at': ch['expires_at'],
    }
    path = out or root / OUTBOX / f'{channel_id}.{epoch}.{seq}.secure.json'
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    ch['send_seq'] = seq
    dump_yaml(channel_file(root, channel_id), ch)
    audit(root, {'event': 'SECURE_MESSAGE_SENT', 'channel_id': channel_id, 'seq': seq, 'key_epoch': epoch})
    return {'status': 'PASS', 'message_file': str(path), 'seq': seq, 'key_epoch': epoch, 'direction': direction}


def receive(root: Path, channel_id: str, message_file: Path) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if str(ch.get('status')) != 'OPEN':
        return {'status': 'DENIED', 'reason': 'CHANNEL_NOT_OPEN'}
    doc = json.loads(message_file.read_text(encoding='utf-8'))
    if doc.get('channel_id') != channel_id or doc.get('audience_project_id') != project_id(root) or doc.get('audience_peer_id') != local_peer_id(root):
        return {'status': 'DENIED', 'reason': 'MESSAGE_AUDIENCE_MISMATCH'}
    try:
        assert_current_contract(root, ch)
    except ValueError as exc:
        return {'status': 'DENIED', 'reason': str(exc)}
    if doc.get('binding') != ch.get('binding'):
        return {'status': 'DENIED', 'reason': 'SESSION_BINDING_MISMATCH'}
    if doc.get('sender_project_id') != ch.get('peer_project_id') or doc.get('sender_peer_id') != ch.get('peer_identity_id'):
        return {'status': 'DENIED', 'reason': 'MESSAGE_SENDER_MISMATCH'}
    seq = int(doc.get('seq', 0) or 0)
    if seq != int(ch.get('recv_seq', 0)) + 1:
        return {'status': 'DENIED', 'reason': 'SEQUENCE_VIOLATION', 'expected_seq': int(ch.get('recv_seq', 0)) + 1, 'received_seq': seq}
    epoch = int(doc.get('key_epoch', 0) or 0)
    if epoch != int(ch.get('key_epoch', 0) or 0):
        return {'status': 'DENIED', 'reason': 'KEY_EPOCH_MISMATCH'}
    if not parse_ts(doc.get('expires_at')) or parse_ts(doc.get('expires_at')) <= now():
        return {'status': 'DENIED', 'reason': 'MESSAGE_EXPIRED'}
    if not parse_ts(doc.get('created_at')) or abs((now() - parse_ts(doc['created_at'])).total_seconds()) > MAX_CLOCK_SKEW:
        return {'status': 'DENIED', 'reason': 'MESSAGE_TIME_INVALID'}
    role = str(ch.get('role') or '')
    if role not in {'initiator', 'responder'}:
        return {'status': 'DENIED', 'reason': 'CHANNEL_ROLE_INVALID'}
    direction = 'i2r' if role == 'responder' else 'r2i'
    key, key_fp, nonce_prefix = key_for_channel(root, ch, role, direction)
    if doc.get('key_fingerprint') != key_fp:
        return {'status': 'DENIED', 'reason': 'KEY_FINGERPRINT_MISMATCH'}
    aad_bytes = aad(ch, seq, epoch, str(doc.get('sender_project_id')), str(doc.get('sender_peer_id')))
    if doc.get('aad_sha256') != hashlib.sha256(aad_bytes).hexdigest():
        return {'status': 'DENIED', 'reason': 'AAD_HASH_MISMATCH'}
    try:
        ct = base64.b64decode(str(doc.get('ciphertext_b64', '')), validate=True)
        plain = ChaCha20Poly1305(key).decrypt(base64.b64decode(str(doc.get('nonce', '')), validate=True), ct, aad_bytes)
        payload = json.loads(plain.decode('utf-8'))
    except (InvalidTag, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return {'status': 'DENIED', 'reason': 'CIPHERTEXT_INVALID'}
    inbox = root / INBOX / f'{channel_id}.{epoch}.{seq}.json'
    inbox.write_text(json.dumps({'metadata': doc, 'payload': payload}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    ch['recv_seq'] = seq
    dump_yaml(channel_file(root, channel_id), ch)
    audit(root, {'event': 'SECURE_MESSAGE_RECEIVED', 'channel_id': channel_id, 'seq': seq, 'key_epoch': epoch})
    return {'status': 'PASS', 'seq': seq, 'key_epoch': epoch, 'payload': payload}


def rekey_prepare(root: Path, channel_id: str, private: Path, key_id: str, out: Path | None = None) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if str(ch.get('status')) != 'OPEN':
        return {'status': 'DENIED', 'reason': 'CHANNEL_NOT_OPEN'}
    try:
        assert_current_contract(root, ch)
    except ValueError as exc:
        return {'status': 'DENIED', 'reason': str(exc)}
    old_epoch = int(ch.get('key_epoch', 0) or 0)
    new_epoch = old_epoch + 1
    new_priv = X25519PrivateKey.generate()
    write_xpriv(xpriv_path(root, channel_id, new_epoch, 'initiator'), new_priv)
    payload = {
        'schema_version': SCHEMA, 'message_type': 'SECURE_REKEY_REQUEST', 'channel_id': channel_id,
        'sender_project_id': ch['local_project_id'], 'sender_peer_id': ch['local_peer_id'],
        'audience_project_id': ch['peer_project_id'], 'audience_peer_id': ch['peer_identity_id'],
        'contract_hash': ch['contract_hash'], 'binding': ch['binding'], 'old_key_epoch': old_epoch,
        'new_key_epoch': new_epoch, 'new_ephemeral_pub': pub_b64(new_priv.public_key()),
        'created_at': iso_now(), 'expires_at': (now()+timedelta(seconds=900)).isoformat(timespec='seconds').replace('+00:00','Z'),
    }
    payload['signature'] = sign({k:v for k,v in payload.items() if k != 'signature'}, private, key_id, 'federation-confidential-rekey')
    path = out or root / OUTBOX / f'{channel_id}.rekey.{new_epoch}.json'
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    audit(root, {'event': 'SECURE_REKEY_REQUESTED', 'channel_id': channel_id, 'old_epoch': old_epoch, 'new_epoch': new_epoch})
    return {'status': 'PASS', 'rekey_file': str(path), 'new_key_epoch': new_epoch}


def rekey_accept(root: Path, request_file: Path, private: Path, key_id: str, out: Path | None = None) -> dict[str, Any]:
    doc = json.loads(request_file.read_text(encoding='utf-8'))
    payload = {k:v for k,v in doc.items() if k != 'signature'}
    ch = load_channel(root, str(payload.get('channel_id')))
    if str(ch.get('status')) != 'OPEN':
        return {'status': 'DENIED', 'reason': 'CHANNEL_NOT_OPEN'}
    try:
        assert_current_contract(root, ch)
    except ValueError as exc:
        return {'status': 'DENIED', 'reason': str(exc)}
    sender = str(payload.get('sender_peer_id'))
    key, peer_fp = peer_root_key(root, sender)
    if peer_fp != ch.get('peer_root_fingerprint'):
        return {'status': 'DENIED', 'reason': 'PEER_ROOT_CHANGED'}
    ok, reason = verify(payload, doc.get('signature') or {}, key, 'federation-confidential-rekey')
    if not ok:
        return {'status': 'DENIED', 'reason': reason}
    if payload.get('binding') != ch.get('binding') or int(payload.get('old_key_epoch', 0)) != int(ch.get('key_epoch', 0)):
        return {'status': 'DENIED', 'reason': 'REKEY_STATE_MISMATCH'}
    new_epoch = int(payload.get('new_key_epoch', 0) or 0)
    if new_epoch <= int(ch.get('key_epoch', 0)):
        return {'status': 'DENIED', 'reason': 'REKEY_NOT_FORWARD'}
    responder = X25519PrivateKey.generate()
    write_xpriv(xpriv_path(root, str(payload['channel_id']), new_epoch, 'responder'), responder)
    shared = responder.exchange(load_pub_b64(str(payload['new_ephemeral_pub'])))
    session = derive_session(shared, str(ch['binding']), str(ch['channel_id']), new_epoch)
    new_key = session['confirm'][0]
    new_fp = hashlib.sha256(session['r2i'][0]).hexdigest()
    ack = {
        'schema_version': SCHEMA, 'message_type': 'SECURE_REKEY_ACCEPT', 'channel_id': ch['channel_id'],
        'sender_project_id': ch['local_project_id'], 'sender_peer_id': ch['local_peer_id'],
        'audience_project_id': payload['sender_project_id'], 'audience_peer_id': payload['sender_peer_id'],
        'contract_hash': ch['contract_hash'], 'binding': ch['binding'], 'new_key_epoch': new_epoch,
        'responder_ephemeral_pub': pub_b64(responder.public_key()), 'key_fingerprint': new_fp,
        'key_confirmation': confirmation(new_key, str(ch['binding']), str(ch['channel_id']), new_epoch),
        'created_at': iso_now(), 'expires_at': payload['expires_at'],
    }
    ack['signature'] = sign({k:v for k,v in ack.items() if k != 'signature'}, private, key_id, 'federation-confidential-rekey-accept')
    ch['key_epoch'] = new_epoch
    ch['initiator_ephemeral_pub'] = payload['new_ephemeral_pub']
    ch['responder_ephemeral_pub'] = ack['responder_ephemeral_pub']
    ch['key_fingerprint'] = new_fp
    ch['send_seq'] = 0
    ch['recv_seq'] = 0
    ch['status'] = 'OPEN'
    dump_yaml(channel_file(root, str(payload['channel_id'])), ch)
    # Erase prior responder private key after the new key is established.
    old_path = xpriv_path(root, str(payload['channel_id']), new_epoch - 1, 'responder')
    if old_path.exists():
        old_path.unlink()
    path = out or root / OUTBOX / f"{payload['channel_id']}.rekey-accept.{new_epoch}.json"
    path.write_text(json.dumps(ack, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    audit(root, {'event': 'SECURE_REKEY_ACCEPTED', 'channel_id': payload['channel_id'], 'new_epoch': new_epoch})
    return {'status': 'PASS', 'rekey_accept_file': str(path), 'new_key_epoch': new_epoch}


def rekey_confirm(root: Path, channel_id: str, ack_file: Path, peer_id: str) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    try:
        assert_current_contract(root, ch)
    except ValueError as exc:
        return {'status': 'DENIED', 'reason': str(exc)}
    doc = json.loads(ack_file.read_text(encoding='utf-8'))
    payload = {k:v for k,v in doc.items() if k != 'signature'}
    if payload.get('channel_id') != channel_id or payload.get('audience_peer_id') != local_peer_id(root) or payload.get('sender_peer_id') != peer_id:
        return {'status': 'DENIED', 'reason': 'REKEY_AUDIENCE_MISMATCH'}
    key, peer_fp = peer_root_key(root, peer_id)
    if peer_fp != ch.get('peer_root_fingerprint'):
        return {'status': 'DENIED', 'reason': 'PEER_ROOT_CHANGED'}
    ok, reason = verify(payload, doc.get('signature') or {}, key, 'federation-confidential-rekey-accept')
    if not ok:
        return {'status': 'DENIED', 'reason': reason}
    new_epoch = int(payload.get('new_key_epoch', 0) or 0)
    if new_epoch <= int(ch.get('key_epoch', 0)):
        return {'status': 'DENIED', 'reason': 'REKEY_NOT_FORWARD'}
    priv = read_xpriv(xpriv_path(root, channel_id, new_epoch, 'initiator'))
    shared = priv.exchange(load_pub_b64(str(payload['responder_ephemeral_pub'])))
    session = derive_session(shared, str(ch['binding']), channel_id, new_epoch)
    new_key = session['confirm'][0]
    new_fp = hashlib.sha256(session['i2r'][0]).hexdigest()
    expected = confirmation(new_key, str(ch['binding']), channel_id, new_epoch)
    if not hmac.compare_digest(expected, str(payload.get('key_confirmation', ''))):
        return {'status': 'DENIED', 'reason': 'REKEY_KEY_CONFIRMATION_FAILED'}
    ch['key_epoch'] = new_epoch
    # Move the initiator side to its freshly generated ephemeral public key.
    ch['initiator_ephemeral_pub'] = pub_b64(priv.public_key())
    ch['responder_ephemeral_pub'] = payload['responder_ephemeral_pub']
    ch['key_fingerprint'] = new_fp
    ch['send_seq'] = 0
    ch['recv_seq'] = 0
    ch['status'] = 'OPEN'
    dump_yaml(channel_file(root, channel_id), ch)
    old_path = xpriv_path(root, channel_id, new_epoch - 1, 'initiator')
    if old_path.exists():
        old_path.unlink()
    audit(root, {'event': 'SECURE_REKEY_CONFIRMED', 'channel_id': channel_id, 'new_epoch': new_epoch})
    return {'status': 'PASS', 'channel_id': channel_id, 'new_key_epoch': new_epoch}


def check(root: Path) -> dict[str, Any]:
    ensure(root)
    issues: list[str] = []
    try:
        contract_hash = require_v26_contract(root)
    except ValueError as exc:
        reason = str(exc)
        if reason in {'PROTOCOL_CONTRACT_NOT_ACTIVE', 'CONFIDENTIAL_TRANSPORT_NOT_NEGOTIATED'}:
            return {'status': 'NOT_CONFIGURED', 'issues': [], 'configured': False}
        return {'status': 'FAIL', 'issues': [reason], 'configured': True}
    channels = list((root / CHANNELS).glob('SC-*.yaml')) if (root / CHANNELS).exists() else []
    open_count = 0
    for path in channels:
        ch = load_yaml(path, {})
        if str(ch.get('schema_version')) != SCHEMA:
            issues.append(f'SCHEMA_MISMATCH:{path.name}')
        if str(ch.get('status')) == 'OPEN':
            open_count += 1
            if ch.get('contract_hash') != contract_hash:
                issues.append(f'CHANNEL_CONTRACT_MISMATCH:{path.name}')
            if str(ch.get('protocol_version')) != '2.6':
                issues.append(f'CHANNEL_PROTOCOL_MISMATCH:{path.name}')
            if int(ch.get('key_epoch', 0) or 0) < 1:
                issues.append(f'KEY_EPOCH_INVALID:{path.name}')
            if not ch.get('key_fingerprint'):
                issues.append(f'KEY_FINGERPRINT_MISSING:{path.name}')
            if not ch.get('initiator_ephemeral_pub') or not ch.get('responder_ephemeral_pub'):
                issues.append(f'EPHEMERAL_BINDING_INCOMPLETE:{path.name}')
            if ch.get('role') not in {'initiator','responder'}:
                issues.append(f'CHANNEL_ROLE_INVALID:{path.name}')
            if int(ch.get('send_seq', 0) or 0) < 0 or int(ch.get('recv_seq', 0) or 0) < 0:
                issues.append(f'NEGATIVE_SEQUENCE:{path.name}')
    return {'status': 'PASS' if not issues else 'FAIL', 'issues': issues, 'configured': True, 'open_channels': open_count}


def main() -> None:
    ap = argparse.ArgumentParser(description='UAAF v2.6 confidential federation transport')
    sp = ap.add_subparsers(dest='cmd', required=True)
    q = sp.add_parser('open'); q.add_argument('path'); q.add_argument('--peer-id', required=True); q.add_argument('--peer-project-id', required=True); q.add_argument('--private-key', required=True); q.add_argument('--key-id', required=True); q.add_argument('--out')
    q = sp.add_parser('accept'); q.add_argument('path'); q.add_argument('--hello-file', required=True); q.add_argument('--local-peer-id', required=True); q.add_argument('--sender-peer-id', required=True); q.add_argument('--private-key', required=True); q.add_argument('--key-id', required=True)
    q = sp.add_parser('confirm'); q.add_argument('path'); q.add_argument('--hello-file', required=True); q.add_argument('--ack-file', required=True); q.add_argument('--channel-id', required=True); q.add_argument('--peer-id', required=True)
    q = sp.add_parser('send'); q.add_argument('path'); q.add_argument('--channel-id', required=True); q.add_argument('--payload-json', required=True); q.add_argument('--out')
    q = sp.add_parser('receive'); q.add_argument('path'); q.add_argument('--channel-id', required=True); q.add_argument('--message-file', required=True)
    q = sp.add_parser('rekey'); q.add_argument('path'); q.add_argument('--channel-id', required=True); q.add_argument('--private-key', required=True); q.add_argument('--key-id', required=True); q.add_argument('--out')
    q = sp.add_parser('rekey-accept'); q.add_argument('path'); q.add_argument('--request-file', required=True); q.add_argument('--private-key', required=True); q.add_argument('--key-id', required=True); q.add_argument('--out')
    q = sp.add_parser('rekey-confirm'); q.add_argument('path'); q.add_argument('--channel-id', required=True); q.add_argument('--ack-file', required=True); q.add_argument('--peer-id', required=True)
    q = sp.add_parser('check'); q.add_argument('path', nargs='?', default='.')
    a = ap.parse_args(); root = Path(a.path).resolve()
    try:
        if a.cmd == 'open': r = open_channel(root, a.peer_id, a.peer_project_id, Path(a.private_key), a.key_id, Path(a.out) if a.out else None)
        elif a.cmd == 'accept': r = accept_channel(root, Path(a.hello_file), a.local_peer_id, a.sender_peer_id, Path(a.private_key), a.key_id)
        elif a.cmd == 'confirm': r = confirm_channel(root, Path(a.hello_file), Path(a.ack_file), a.channel_id, a.peer_id)
        elif a.cmd == 'send': r = send(root, a.channel_id, json.loads(a.payload_json), Path(a.out) if a.out else None)
        elif a.cmd == 'receive': r = receive(root, a.channel_id, Path(a.message_file))
        elif a.cmd == 'rekey': r = rekey_prepare(root, a.channel_id, Path(a.private_key), a.key_id, Path(a.out) if a.out else None)
        elif a.cmd == 'rekey-accept': r = rekey_accept(root, Path(a.request_file), Path(a.private_key), a.key_id, Path(a.out) if a.out else None)
        elif a.cmd == 'rekey-confirm': r = rekey_confirm(root, a.channel_id, Path(a.ack_file), a.peer_id)
        else: r = check(root)
    except (ValueError, OSError, json.JSONDecodeError, InvalidSignature) as exc:
        r = {'status': 'DENIED', 'reason': str(exc)}
    print(json.dumps(r, indent=2, ensure_ascii=False))
    raise SystemExit(0 if r.get('status') in {'PASS', 'NOT_CONFIGURED'} else 1)


if __name__ == '__main__':
    main()
