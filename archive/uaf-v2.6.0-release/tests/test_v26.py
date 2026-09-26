from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / 'tools' / 'uaf.py')]

sys.path.insert(0, str(ROOT / 'tools'))
import uaf_federation_confidential as secure  # noqa: E402
import uaf_federation_protocol as proto  # noqa: E402


def run(*args, timeout=20):
    return subprocess.run([*CLI, *map(str, args)], capture_output=True, text=True, timeout=timeout)


def make_project(base: Path, name: str, project_id: str, peer_id: str):
    root = base / name
    p = run('init', str(root), '--profile', 'full', '--extension', 'v2.6', '--name', project_id, '--type', 'fullstack')
    assert p.returncode == 0, p.stdout + p.stderr
    cap = root / '.ai/federation/protocol/CAPABILITIES.yaml'
    data = yaml.safe_load(cap.read_text(encoding='utf-8'))
    data['project_id'] = project_id
    data['peer_id'] = peer_id
    cap.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    key = Ed25519PrivateKey.generate()
    return root, key


def write_key(base: Path, peer_id: str, key: Ed25519PrivateKey) -> Path:
    path = base / f'{peer_id}.pem'
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return path


def pin(root: Path, peer_id: str, key: Ed25519PrivateKey):
    d = root / '.ai/federation/peers' / peer_id
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath('ROOT.pub.pem').write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))


def establish_pair(tmp_path: Path):
    a, ka = make_project(tmp_path, 'a', 'PROJ-A', 'PEER-A')
    b, kb = make_project(tmp_path, 'b', 'PROJ-B', 'PEER-B')
    pin(a, 'PEER-B', kb)
    pin(b, 'PEER-A', ka)
    ka_path = write_key(tmp_path, 'PEER-A', ka)
    kb_path = write_key(tmp_path, 'PEER-B', kb)

    oa = tmp_path / 'PEER-A.offer.yaml'
    ob = tmp_path / 'PEER-B.offer.yaml'
    assert proto.offer(a, 'PEER-A', str(oa), str(ka_path), 'PEER-A')['status'] == 'PASS'
    assert proto.offer(b, 'PEER-B', str(ob), str(kb_path), 'PEER-B')['status'] == 'PASS'
    assert proto.negotiate(a, str(ob), 'PEER-B', True)['status'] == 'NEGOTIATED'
    assert proto.negotiate(b, str(oa), 'PEER-A', True)['status'] == 'NEGOTIATED'
    return a, b, ka_path, kb_path


def establish_secure(tmp_path):
    a, b, ka_path, kb_path = establish_pair(tmp_path)
    hello = tmp_path / 'hello.json'
    opened = secure.open_channel(a, 'PEER-B', 'PROJ-B', ka_path, 'PEER-A', hello)
    ack = secure.accept_channel(b, hello, 'PEER-B', 'PEER-A', kb_path, 'PEER-B')
    confirmed = secure.confirm_channel(a, hello, Path(ack['ack_file']), opened['channel_id'], 'PEER-B')
    return a, b, ka_path, kb_path, opened['channel_id'], hello, Path(ack['ack_file'])


def test_initializer_v26(tmp_path):
    root, _ = make_project(tmp_path, 'p', 'PROJ', 'PEER')
    manifest = yaml.safe_load((root / '.ai/manifest.yaml').read_text())
    assert manifest['framework']['version'] == '2.6.0'
    assert manifest['extensions']['version'] == '2.6'
    assert manifest['protocols']['federation_transport_confidential'] == 'UAAF-FED-2.6'
    for rel in [
        '.ai/federation/secure/CHANNELS', '.ai/federation/secure/INBOX',
        '.ai/federation/secure/OUTBOX', '.ai/federation/secure/keys',
        '.ai/federation/secure/AUDIT.jsonl', '.ai/federation/secure/CONFIG.yaml',
        '.gitignore',
    ]:
        assert (root / rel).exists(), rel


def test_v26_capability_negotiation_enables_feature(tmp_path):
    a, b, _, _ = establish_pair(tmp_path)
    ca = yaml.safe_load((a / '.ai/federation/protocol/PROTOCOL-CONTRACT.yaml').read_text())
    cb = yaml.safe_load((b / '.ai/federation/protocol/PROTOCOL-CONTRACT.yaml').read_text())
    assert 'confidential-transport' in (ca['contract'].get('enabled_features') or [])
    assert 'confidential-transport' in (cb['contract'].get('enabled_features') or [])


def test_secure_channel_and_bidirectional_encryption(tmp_path):
    a, b, ka, kb, cid, _, _ = establish_secure(tmp_path)
    m1 = tmp_path / 'm1.json'
    m2 = tmp_path / 'm2.json'
    s1 = secure.send(a, cid, {'secret': 'alpha', 'n': 1}, m1)
    assert s1['status'] == 'PASS'
    raw = m1.read_text()
    assert 'alpha' not in raw
    r1 = secure.receive(b, cid, m1)
    assert r1['status'] == 'PASS' and r1['payload']['secret'] == 'alpha'
    s2 = secure.send(b, cid, {'reply': 'beta'}, m2)
    assert s2['status'] == 'PASS'
    r2 = secure.receive(a, cid, m2)
    assert r2['status'] == 'PASS' and r2['payload']['reply'] == 'beta'


def test_tamper_and_replay_denied(tmp_path):
    a, b, _, _, cid, _, _ = establish_secure(tmp_path)
    msg = tmp_path / 'msg.json'
    assert secure.send(a, cid, {'x': 7}, msg)['status'] == 'PASS'
    original = json.loads(msg.read_text())
    tampered = dict(original)
    ct = base64.b64decode(tampered['ciphertext_b64'])
    tampered['ciphertext_b64'] = base64.b64encode(bytes([ct[0] ^ 1]) + ct[1:]).decode()
    msg.write_text(json.dumps(tampered), encoding='utf-8')
    denied = secure.receive(b, cid, msg)
    assert denied['status'] == 'DENIED'
    assert denied['reason'] in {'CIPHERTEXT_INVALID', 'KEY_FINGERPRINT_MISMATCH'}
    # The original sequence remains outstanding because the tampered message was rejected.
    msg.write_text(json.dumps(original), encoding='utf-8')
    assert secure.receive(b, cid, msg)['status'] == 'PASS'
    replay = secure.receive(b, cid, msg)
    assert replay['status'] == 'DENIED'
    assert replay['reason'] == 'SEQUENCE_VIOLATION'


def test_rekey_rotates_epoch_and_erases_old_ephemeral_keys(tmp_path):
    a, b, ka, kb, cid, _, _ = establish_secure(tmp_path)
    request = tmp_path / 'rekey.json'
    prepared = secure.rekey_prepare(a, cid, ka, 'PEER-A', request)
    assert prepared['status'] == 'PASS'
    ack = tmp_path / 'rekey-ack.json'
    accepted = secure.rekey_accept(b, request, kb, 'PEER-B', ack)
    assert accepted['status'] == 'PASS'
    assert secure.rekey_confirm(a, cid, ack, 'PEER-B')['status'] == 'PASS'
    akeydir = a / '.ai/federation/secure/keys'
    bkeydir = b / '.ai/federation/secure/keys'
    assert not (akeydir / f'{cid}.e1.initiator.x25519.pem').exists()
    assert not (bkeydir / f'{cid}.e1.responder.x25519.pem').exists()
    msg = tmp_path / 'after-rekey.json'
    assert secure.send(a, cid, {'epoch': 2}, msg)['status'] == 'PASS'
    assert secure.receive(b, cid, msg)['payload']['epoch'] == 2


def test_contract_change_blocks_old_channel(tmp_path):
    a, b, _, _, cid, _, _ = establish_secure(tmp_path)
    manifest_path = a / '.ai/federation/protocol/PROTOCOL-CONTRACT.yaml'
    contract_doc = yaml.safe_load(manifest_path.read_text())
    contract_doc['contract']['enabled_features'].append('synthetic-change')
    # Deliberately make the persisted hash stale.
    manifest_path.write_text(yaml.safe_dump(contract_doc, sort_keys=False), encoding='utf-8')
    msg = tmp_path / 'blocked.json'
    result = secure.send(a, cid, {'should': 'block'}, msg)
    assert result['status'] == 'DENIED'
    assert result['reason'] == 'PROTOCOL_CONTRACT_HASH_MISMATCH'


def test_peer_root_change_blocks_channel(tmp_path):
    a, b, _, _, cid, _, _ = establish_secure(tmp_path)
    pin_path = a / '.ai/federation/peers/PEER-B/ROOT.pub.pem'
    other = Ed25519PrivateKey.generate()
    pin_path.write_bytes(other.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    msg = tmp_path / 'root-change.json'
    result = secure.send(a, cid, {'x': 1}, msg)
    assert result['status'] == 'DENIED'
    assert result['reason'] == 'PEER_ROOT_CHANGED'


def test_v26_check_and_doctor(tmp_path):
    root, _ = make_project(tmp_path, 'p', 'PROJ', 'PEER')
    cp = run('federation-confidential', 'check', root)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert json.loads(cp.stdout)['status'] == 'NOT_CONFIGURED'
    dp = run('doctor', root, '--json')
    assert dp.returncode == 0, dp.stdout + dp.stderr
    assert json.loads(dp.stdout)['mode'] == 'compact-v2.6'


def test_v25_downgrade_removes_confidential_namespace(tmp_path):
    root, _ = make_project(tmp_path, 'p', 'PROJ', 'PEER')
    p = run('init', root, '--profile', 'full', '--extension', 'v2.5', '--force')
    assert p.returncode == 0, p.stdout + p.stderr
    assert not (root / '.ai/federation/secure').exists()
    manifest = yaml.safe_load((root / '.ai/manifest.yaml').read_text())
    assert str(manifest['extensions']['version']) == '2.5'
