#!/usr/bin/env python3
"""UAAF v2.5 secure federation transport reference layer.

This reference transport is deliberately transport-agnostic and uses the
filesystem as a loopback/reference carrier. It provides authentication,
message integrity, session binding, sequencing, reconnect/resume, and
replay protection. It does not provide confidentiality.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SCHEMA = "2.5"
FED = Path('.ai/federation')
TRANSPORT = FED / 'transport'
CHANNELS = TRANSPORT / 'CHANNELS'
INBOX = TRANSPORT / 'INBOX'
OUTBOX = TRANSPORT / 'OUTBOX'
AUDIT = TRANSPORT / 'AUDIT.jsonl'
MAX_CLOCK_SKEW = 300


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now().isoformat(timespec='seconds').replace('+00:00','Z')


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except ValueError:
        return None


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return data if isinstance(data, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def fp(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('private key is not Ed25519')
    return key


def public_key(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError('public key is not Ed25519')
    return key


def project_id(root: Path) -> str:
    m = load_yaml(root / '.ai/manifest.yaml', {})
    return str((m.get('project') or {}).get('name') or root.name)

def local_peer_id(root: Path) -> str:
    cap = load_yaml(root / '.ai/federation/protocol/CAPABILITIES.yaml', {})
    return str(cap.get('peer_id') or project_id(root))


def active_contract(root: Path) -> tuple[str, dict[str, Any]]:
    path = root / '.ai/federation/protocol/PROTOCOL-CONTRACT.yaml'
    doc = load_yaml(path, {})
    if str(doc.get('status')) not in {'NEGOTIATED','FALLBACK_NEGOTIATED'}:
        raise ValueError('PROTOCOL_CONTRACT_NOT_ACTIVE')
    contract = doc.get('contract') or {}
    h = str(doc.get('contract_hash') or '')
    if not h:
        raise ValueError('PROTOCOL_CONTRACT_HASH_MISSING')
    if fp(contract) != h:
        raise ValueError('PROTOCOL_CONTRACT_HASH_MISMATCH')
    return h, doc


def peer_root_key(root: Path, peer_id: str) -> tuple[Ed25519PublicKey, str]:
    peer_dir = root / FED / 'peers' / peer_id
    pem = peer_dir / 'ROOT.pub.pem'
    if not pem.exists():
        raise ValueError('REMOTE_ROOT_NOT_PINNED')
    key = public_key(pem)
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, hashlib.sha256(raw).hexdigest()


def sign(payload: dict[str, Any], private: Path, key_id: str, purpose: str) -> dict[str, Any]:
    body = canon(payload)
    sig = private_key(private).sign(body)
    return {
        'schema_version': SCHEMA,
        'algorithm': 'Ed25519',
        'purpose': purpose,
        'key_id': key_id,
        'payload_sha256': hashlib.sha256(body).hexdigest(),
        'signature_b64': base64.b64encode(sig).decode('ascii'),
    }


def verify(payload: dict[str, Any], env: dict[str, Any], key: Ed25519PublicKey, purpose: str) -> tuple[bool, str]:
    if env.get('schema_version') != SCHEMA or env.get('algorithm') != 'Ed25519':
        return False, 'SIGNATURE_SCHEMA_MISMATCH'
    if env.get('purpose') != purpose:
        return False, 'PURPOSE_MISMATCH'
    body = canon(payload)
    if env.get('payload_sha256') != hashlib.sha256(body).hexdigest():
        return False, 'PAYLOAD_HASH_MISMATCH'
    try:
        key.verify(base64.b64decode(str(env.get('signature_b64','')), validate=True), body)
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
            try: prior = str(json.loads(lines[-1]).get('entry_hash', prior))
            except Exception: prior = 'BROKEN'
    row = {'schema_version': SCHEMA, 'timestamp': iso_now(), 'prev_hash': prior, **event}
    row['entry_hash'] = hashlib.sha256(canon(row)).hexdigest()
    with p.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')


def ensure(root: Path) -> None:
    for p in [CHANNELS, INBOX, OUTBOX]:
        (root / p).mkdir(parents=True, exist_ok=True)
    (root / AUDIT).touch(exist_ok=True)


def channel_path(root: Path, channel_id: str) -> Path:
    return root / CHANNELS / f'{channel_id}.yaml'


def load_channel(root: Path, channel_id: str) -> dict[str, Any]:
    return load_yaml(channel_path(root, channel_id), {})


def validate_time(value: Any) -> bool:
    ts = parse_ts(value)
    return bool(ts and abs((now() - ts).total_seconds()) <= MAX_CLOCK_SKEW)


def open_channel(root: Path, peer_id: str, peer_project_id: str, private: Path, key_id: str, protocol_family: str = 'federation_protocol', protocol_version: str = '2.4', ttl: int = 900, out: Path | None = None) -> dict[str, Any]:
    ensure(root)
    contract_hash, contract_doc = active_contract(root)
    if contract_doc.get('contract', {}).get('protocols', {}).get(protocol_family) != protocol_version:
        raise ValueError('PROTOCOL_NOT_NEGOTIATED')
    _, peer_fp = peer_root_key(root, peer_id)
    channel_id = f'CH-{secrets.token_hex(6)}'
    nonce = secrets.token_hex(24)
    local_id = project_id(root)
    local_peer = local_peer_id(root)
    binding = fp({'channel_id': channel_id, 'local_project_id': local_id, 'local_peer_id': local_peer, 'peer_id': peer_id, 'peer_project_id': peer_project_id, 'contract_hash': contract_hash, 'protocol_family': protocol_family, 'protocol_version': protocol_version, 'nonce': nonce})
    payload = {
        'schema_version': SCHEMA,
        'message_type': 'CHANNEL_HELLO',
        'channel_id': channel_id,
        'sender_project_id': local_id,
        'sender_peer_id': local_peer,
        'audience_peer_id': peer_id,
        'audience_project_id': peer_project_id,
        'protocol_family': protocol_family,
        'protocol_version': protocol_version,
        'contract_hash': contract_hash,
        'binding': binding,
        'nonce': nonce,
        'created_at': iso_now(),
        'expires_at': (now() + timedelta(seconds=ttl)).isoformat(timespec='seconds').replace('+00:00','Z'),
        'transport_security': {'authentication': 'Ed25519', 'integrity': True, 'replay_protection': True, 'confidentiality': False},
    }
    payload['signature'] = sign({k:v for k,v in payload.items() if k != 'signature'}, private, key_id, 'federation-transport-channel-open')
    channel = {
        'schema_version': SCHEMA,
        'status': 'OPENING',
        'channel_id': channel_id,
        'local_project_id': local_id,
        'peer_identity_id': peer_id,
        'peer_project_id': peer_project_id,
        'peer_root_fingerprint': peer_fp,
        'protocol_family': protocol_family,
        'protocol_version': protocol_version,
        'contract_hash': contract_hash,
        'binding': binding,
        'nonce_hash': fp(nonce),
        'created_at': payload['created_at'],
        'expires_at': payload['expires_at'],
        'send_seq': 0,
        'recv_seq': 0,
        'last_received_message': None,
        'resume_epoch': 0,
    }
    dump_yaml(channel_path(root, channel_id), channel)
    hello_path = out or (root / OUTBOX / f'{channel_id}.hello.json')
    hello_path.parent.mkdir(parents=True, exist_ok=True)
    hello_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    audit(root, {'event':'CHANNEL_OPEN_REQUESTED','channel_id':channel_id,'peer_id':peer_id,'contract_hash':contract_hash})
    return {'status':'PASS','channel_id':channel_id,'hello_file':str(hello_path),'contract_hash':contract_hash,'binding':binding}


def accept_channel(root: Path, hello_file: Path, local_peer_id_arg: str, sender_peer_id: str, private: Path, key_id: str) -> dict[str, Any]:
    ensure(root)
    doc = json.loads(hello_file.read_text(encoding='utf-8'))
    signature = doc.get('signature') or {}
    payload = {k:v for k,v in doc.items() if k != 'signature'}
    if str(payload.get('audience_peer_id')) != local_peer_id_arg:
        return {'status':'DENIED','reason':'CHANNEL_AUDIENCE_PEER_MISMATCH'}
    if str(payload.get('audience_project_id')) != project_id(root):
        return {'status':'DENIED','reason':'CHANNEL_AUDIENCE_PROJECT_MISMATCH'}
    if not validate_time(payload.get('created_at')):
        return {'status':'DENIED','reason':'CHANNEL_TIME_INVALID'}
    if parse_ts(payload.get('expires_at')) and parse_ts(payload.get('expires_at')) <= now():
        return {'status':'DENIED','reason':'CHANNEL_EXPIRED'}
    key, peer_fp = peer_root_key(root, sender_peer_id)
    ok, reason = verify(payload, signature, key, 'federation-transport-channel-open')
    if not ok:
        return {'status':'DENIED','reason':reason}
    contract_hash, contract_doc = active_contract(root)
    if str(payload.get('contract_hash')) != contract_hash:
        return {'status':'DENIED','reason':'CONTRACT_HASH_MISMATCH'}
    local_id = project_id(root)
    channel_id = str(payload.get('channel_id'))
    binding = fp({'channel_id': channel_id, 'local_project_id': str(payload.get('sender_project_id')), 'local_peer_id': str(payload.get('sender_peer_id')), 'peer_id': str(payload.get('audience_peer_id')), 'peer_project_id': str(payload.get('audience_project_id')), 'contract_hash': contract_hash, 'protocol_family': payload.get('protocol_family'), 'protocol_version': payload.get('protocol_version'), 'nonce': payload.get('nonce')})
    if binding != str(payload.get('binding')):
        return {'status':'DENIED','reason':'SESSION_BINDING_MISMATCH'}
    channel = {
        'schema_version': SCHEMA,
        'status': 'OPEN',
        'channel_id': channel_id,
        'local_project_id': local_id,
        'peer_identity_id': sender_peer_id,
        'peer_project_id': str(payload.get('sender_project_id')),
        'peer_root_fingerprint': peer_fp,
        'protocol_family': str(payload.get('protocol_family')),
        'protocol_version': str(payload.get('protocol_version')),
        'contract_hash': contract_hash,
        'binding': str(payload.get('binding')),
        'nonce_hash': fp(str(payload.get('nonce'))),
        'created_at': payload.get('created_at'),
        'expires_at': payload.get('expires_at'),
        'send_seq': 0,
        'recv_seq': 0,
        'last_received_message': None,
        'resume_epoch': 0,
    }
    dump_yaml(channel_path(root, channel_id), channel)
    ack = {'schema_version':SCHEMA,'message_type':'CHANNEL_ACCEPT','channel_id':channel_id,'sender_project_id':local_id,'sender_peer_id':local_peer_id_arg,'audience_project_id':str(payload.get('sender_project_id')),'audience_peer_id':str(payload.get('sender_peer_id')),'binding':binding,'accepted_at':iso_now(),'contract_hash':contract_hash}
    ack['signature'] = sign({k:v for k,v in ack.items() if k != 'signature'}, private, key_id, 'federation-transport-channel-accept')
    audit(root, {'event':'CHANNEL_ACCEPTED','channel_id':channel_id,'peer_project_id':payload.get('sender_project_id'),'contract_hash':contract_hash})
    return {'status':'PASS','channel_id':channel_id,'ack':ack}



def confirm(root: Path, hello_file: Path, ack_file: Path, channel_id: str, peer_id: str) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if not ch:
        return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    ack = json.loads(ack_file.read_text(encoding='utf-8'))
    sig = ack.get('signature') or {}
    payload = {k:v for k,v in ack.items() if k != 'signature'}
    if payload.get('channel_id') != channel_id:
        return {'status':'DENIED','reason':'CHANNEL_ID_MISMATCH'}
    if str(payload.get('audience_project_id')) != str(ch.get('local_project_id')):
        return {'status':'DENIED','reason':'CHANNEL_AUDIENCE_PROJECT_MISMATCH'}
    if str(payload.get('audience_peer_id')) != str(local_peer_id(root)):
        return {'status':'DENIED','reason':'CHANNEL_AUDIENCE_PEER_MISMATCH'}
    if str(payload.get('binding')) != str(ch.get('binding')):
        return {'status':'DENIED','reason':'SESSION_BINDING_MISMATCH'}
    key, peer_fp = peer_root_key(root, peer_id)
    if str(ch.get('peer_root_fingerprint')) != peer_fp:
        return {'status':'DENIED','reason':'PEER_ROOT_CHANGED'}
    ok, reason = verify(payload, sig, key, 'federation-transport-channel-accept')
    if not ok:
        return {'status':'DENIED','reason':reason}
    ch['status'] = 'OPEN'
    ch['peer_identity_id'] = peer_id
    ch['peer_project_id'] = str(payload.get('sender_project_id'))
    dump_yaml(channel_path(root, channel_id), ch)
    audit(root, {'event':'CHANNEL_CONFIRMED','channel_id':channel_id,'peer_id':peer_id})
    return {'status':'PASS','channel_id':channel_id,'status_detail':'OPEN'}


def send(root: Path, channel_id: str, payload: dict[str, Any], private: Path, key_id: str, out: Path | None = None) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if ch.get('status') != 'OPEN':
        return {'status':'DENIED','reason':'CHANNEL_NOT_OPEN'}
    if parse_ts(ch.get('expires_at')) and parse_ts(ch.get('expires_at')) <= now():
        return {'status':'DENIED','reason':'CHANNEL_EXPIRED'}
    seq = int(ch.get('send_seq',0)) + 1
    message_id = f'MSG-{secrets.token_hex(8)}'
    body = {
        'schema_version': SCHEMA,
        'message_type': 'DATA',
        'message_id': message_id,
        'channel_id': channel_id,
        'sender_project_id': str(ch.get('local_project_id')),
        'sender_peer_id': str(local_peer_id(root)),
        'audience_project_id': str(ch.get('peer_project_id')),
        'audience_peer_id': str(ch.get('peer_identity_id')),
        'binding': str(ch.get('binding')),
        'seq': seq,
        'created_at': iso_now(),
        'payload': payload,
        'payload_sha256': fp(payload),
    }
    body['signature'] = sign(body, private, key_id, 'federation-transport-message')
    p = out or (root / OUTBOX / f'{channel_id}.{seq}.json')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    ch['send_seq'] = seq
    dump_yaml(channel_path(root, channel_id), ch)
    audit(root, {'event':'TRANSPORT_MESSAGE_SENT','channel_id':channel_id,'message_id':message_id,'seq':seq})
    return {'status':'PASS','message_id':message_id,'seq':seq,'file':str(p)}


def receive(root: Path, channel_id: str, message_file: Path) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if ch.get('status') != 'OPEN':
        return {'status':'DENIED','reason':'CHANNEL_NOT_OPEN'}
    doc = json.loads(message_file.read_text(encoding='utf-8'))
    sig = doc.get('signature') or {}
    payload = {k:v for k,v in doc.items() if k != 'signature'}
    if str(payload.get('channel_id')) != channel_id:
        return {'status':'DENIED','reason':'CHANNEL_ID_MISMATCH'}
    if str(payload.get('binding')) != str(ch.get('binding')):
        return {'status':'DENIED','reason':'SESSION_BINDING_MISMATCH'}
    if str(payload.get('audience_project_id')) != str(ch.get('local_project_id')):
        return {'status':'DENIED','reason':'MESSAGE_AUDIENCE_MISMATCH'}
    if str(payload.get('sender_project_id')) != str(ch.get('peer_project_id')):
        return {'status':'DENIED','reason':'MESSAGE_SENDER_PROJECT_MISMATCH'}
    expected = int(ch.get('recv_seq',0)) + 1
    seq = int(payload.get('seq',0) or 0)
    if seq != expected:
        return {'status':'DENIED','reason':'SEQUENCE_VIOLATION','expected_seq':expected,'received_seq':seq}
    if not validate_time(payload.get('created_at')):
        return {'status':'DENIED','reason':'MESSAGE_TIME_INVALID'}
    if fp(payload.get('payload') or {}) != str(payload.get('payload_sha256')):
        return {'status':'DENIED','reason':'PAYLOAD_HASH_MISMATCH'}
    peer_id = str(ch.get('peer_identity_id'))
    key, peer_fp = peer_root_key(root, peer_id)
    if str(ch.get('peer_root_fingerprint')) != peer_fp:
        return {'status':'DENIED','reason':'PEER_ROOT_CHANGED'}
    ok, reason = verify(payload, sig, key, 'federation-transport-message')
    if not ok:
        return {'status':'DENIED','reason':reason}
    inbox = root / INBOX / f'{channel_id}.{seq}.json'
    inbox.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    ch['recv_seq'] = seq
    ch['last_received_message'] = str(payload.get('message_id'))
    dump_yaml(channel_path(root, channel_id), ch)
    audit(root, {'event':'TRANSPORT_MESSAGE_ACCEPTED','channel_id':channel_id,'message_id':payload.get('message_id'),'seq':seq})
    return {'status':'PASS','message_id':payload.get('message_id'),'seq':seq,'payload':payload.get('payload')}


def resume(root: Path, channel_id: str, private: Path, key_id: str, out: Path | None = None) -> dict[str, Any]:
    ch = load_channel(root, channel_id)
    if not ch:
        return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    epoch = int(ch.get('resume_epoch',0)) + 1
    token = {
        'schema_version': SCHEMA,
        'message_type': 'CHANNEL_RESUME',
        'channel_id': channel_id,
        'sender_project_id': str(ch.get('local_project_id')),
        'sender_peer_id': str(local_peer_id(root)),
        'audience_project_id': str(ch.get('peer_project_id')),
        'audience_peer_id': str(ch.get('peer_identity_id')),
        'binding': str(ch.get('binding')),
        'resume_epoch': epoch,
        'last_sent_seq': int(ch.get('send_seq',0)),
        'last_received_seq': int(ch.get('recv_seq',0)),
        'created_at': iso_now(),
        'expires_at': (now()+timedelta(seconds=900)).isoformat(timespec='seconds').replace('+00:00','Z'),
    }
    token['signature'] = sign(token, private, key_id, 'federation-transport-channel-resume')
    p = out or (root / OUTBOX / f'{channel_id}.resume.{epoch}.json')
    p.write_text(json.dumps(token, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    ch['resume_epoch'] = epoch
    ch['status'] = 'OPEN'
    dump_yaml(channel_path(root, channel_id), ch)
    audit(root, {'event':'CHANNEL_RESUME_CREATED','channel_id':channel_id,'resume_epoch':epoch})
    return {'status':'PASS','channel_id':channel_id,'resume_epoch':epoch,'file':str(p)}



def resume_accept(root: Path, token_file: Path, local_peer_id_arg: str, sender_peer_id: str) -> dict[str, Any]:
    doc = json.loads(token_file.read_text(encoding='utf-8'))
    sig = doc.get('signature') or {}
    payload = {k:v for k,v in doc.items() if k != 'signature'}
    if str(payload.get('audience_peer_id')) != local_peer_id_arg:
        return {'status':'DENIED','reason':'RESUME_AUDIENCE_PEER_MISMATCH'}
    if str(payload.get('audience_project_id')) != project_id(root):
        return {'status':'DENIED','reason':'RESUME_AUDIENCE_PROJECT_MISMATCH'}
    if not validate_time(payload.get('created_at')):
        return {'status':'DENIED','reason':'RESUME_TIME_INVALID'}
    exp = parse_ts(payload.get('expires_at'))
    if exp and exp <= now():
        return {'status':'DENIED','reason':'RESUME_EXPIRED'}
    key, peer_fp = peer_root_key(root, sender_peer_id)
    ok, reason = verify(payload, sig, key, 'federation-transport-channel-resume')
    if not ok:
        return {'status':'DENIED','reason':reason}
    ch = load_channel(root, str(payload.get('channel_id')))
    if not ch:
        return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    if str(ch.get('binding')) != str(payload.get('binding')):
        return {'status':'DENIED','reason':'SESSION_BINDING_MISMATCH'}
    if str(ch.get('peer_identity_id')) != sender_peer_id or str(ch.get('peer_project_id')) != str(payload.get('sender_project_id')):
        return {'status':'DENIED','reason':'RESUME_SENDER_MISMATCH'}
    if str(ch.get('peer_root_fingerprint')) != peer_fp:
        return {'status':'DENIED','reason':'PEER_ROOT_CHANGED'}
    incoming_epoch = int(payload.get('resume_epoch',0) or 0)
    current_epoch = int(ch.get('resume_epoch',0) or 0)
    if incoming_epoch <= current_epoch:
        return {'status':'DENIED','reason':'RESUME_REPLAY','current_epoch':current_epoch,'received_epoch':incoming_epoch}
    ch['resume_epoch'] = incoming_epoch
    ch['status'] = 'OPEN'
    ch['send_seq'] = max(int(ch.get('send_seq',0)), int(payload.get('last_sent_seq',0) or 0))
    ch['recv_seq'] = max(int(ch.get('recv_seq',0)), int(payload.get('last_received_seq',0) or 0))
    dump_yaml(channel_path(root, str(payload.get('channel_id'))), ch)
    audit(root, {'event':'CHANNEL_RESUME_ACCEPTED','channel_id':payload.get('channel_id'),'resume_epoch':incoming_epoch})
    return {'status':'PASS','channel_id':payload.get('channel_id'),'resume_epoch':incoming_epoch}


def check(root: Path) -> dict[str, Any]:
    ensure(root)
    issues=[]
    try:
        contract_hash,_=active_contract(root)
    except ValueError as exc:
        if str(exc) != 'PROTOCOL_CONTRACT_NOT_ACTIVE':
            issues.append(str(exc))
        contract_hash=''
    channels=list((root/CHANNELS).glob('CH-*.yaml')) if (root/CHANNELS).exists() else []
    open_count=0
    for p in channels:
        c=load_yaml(p,{})
        if str(c.get('schema_version')) != SCHEMA: issues.append(f'SCHEMA_MISMATCH:{p.name}')
        if str(c.get('status'))=='OPEN':
            open_count += 1
            if str(c.get('contract_hash')) != contract_hash: issues.append(f'CHANNEL_CONTRACT_MISMATCH:{p.name}')
            if int(c.get('recv_seq',0)) < 0 or int(c.get('send_seq',0)) < 0: issues.append(f'NEGATIVE_SEQUENCE:{p.name}')
    if not issues and not contract_hash:
        return {'status':'NOT_CONFIGURED','issues':[],'open_channels':open_count,'configured':False}
    return {'status':'PASS' if not issues else 'FAIL','issues':issues,'open_channels':open_count,'configured':bool(contract_hash)}


def main() -> None:
    ap=argparse.ArgumentParser(description='UAAF v2.5 secure federation transport')
    sp=ap.add_subparsers(dest='cmd', required=True)
    q=sp.add_parser('open'); q.add_argument('path'); q.add_argument('--peer-id',required=True); q.add_argument('--peer-project-id',required=True); q.add_argument('--private-key',required=True); q.add_argument('--key-id',required=True); q.add_argument('--out')
    q=sp.add_parser('accept'); q.add_argument('path'); q.add_argument('--hello-file',required=True); q.add_argument('--local-peer-id',required=True); q.add_argument('--sender-peer-id',required=True); q.add_argument('--private-key',required=True); q.add_argument('--key-id',required=True)
    q=sp.add_parser('confirm'); q.add_argument('path'); q.add_argument('--hello-file',required=True); q.add_argument('--ack-file',required=True); q.add_argument('--channel-id',required=True); q.add_argument('--peer-id',required=True)
    q=sp.add_parser('send'); q.add_argument('path'); q.add_argument('--channel-id',required=True); q.add_argument('--payload-json',required=True); q.add_argument('--private-key',required=True); q.add_argument('--key-id',required=True); q.add_argument('--out')
    q=sp.add_parser('receive'); q.add_argument('path'); q.add_argument('--channel-id',required=True); q.add_argument('--message-file',required=True)
    q=sp.add_parser('resume'); q.add_argument('path'); q.add_argument('--channel-id',required=True); q.add_argument('--private-key',required=True); q.add_argument('--key-id',required=True); q.add_argument('--out')
    q=sp.add_parser('resume-accept'); q.add_argument('path'); q.add_argument('--token-file',required=True); q.add_argument('--local-peer-id',required=True); q.add_argument('--sender-peer-id',required=True)
    q=sp.add_parser('check'); q.add_argument('path',nargs='?',default='.'); q.add_argument('--json',action='store_true')
    a=ap.parse_args(); root=Path(a.path).resolve()
    try:
        if a.cmd=='open': r=open_channel(root,a.peer_id,a.peer_project_id,Path(a.private_key),a.key_id,out=Path(a.out) if a.out else None)
        elif a.cmd=='accept': r=accept_channel(root,Path(a.hello_file),a.local_peer_id,a.sender_peer_id,Path(a.private_key),a.key_id)
        elif a.cmd=='confirm': r=confirm(root,Path(a.hello_file),Path(a.ack_file),a.channel_id,a.peer_id)
        elif a.cmd=='send': r=send(root,a.channel_id,json.loads(a.payload_json),Path(a.private_key),a.key_id,Path(a.out) if a.out else None)
        elif a.cmd=='receive': r=receive(root,a.channel_id,Path(a.message_file))
        elif a.cmd=='resume': r=resume(root,a.channel_id,Path(a.private_key),a.key_id,Path(a.out) if a.out else None)
        elif a.cmd=='resume-accept': r=resume_accept(root,Path(a.token_file),a.local_peer_id,a.sender_peer_id)
        else: r=check(root)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        r={'status':'DENIED','reason':str(exc)}
    print(json.dumps(r,indent=2,ensure_ascii=False))
    raise SystemExit(0 if r.get('status') in {'PASS','OPEN','ACCEPTED','NOT_CONFIGURED'} else 1)

if __name__=='__main__': main()
