from __future__ import annotations
import json, subprocess, sys, base64
from pathlib import Path
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/'tools'/'uaf.py')]
sys.path.insert(0,str(ROOT/'tools'))
import uaf_federation_protocol as proto
import uaf_federation_confidential as secure
import uaf_key_lifecycle as life

def run(*args, timeout=15):
    return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=timeout)

def make_project(base,name,pid,peer):
    root=base/name
    p=run('init',root,'--profile','full','--extension','v2.7','--name',pid,'--type','fullstack')
    assert p.returncode==0,p.stdout+p.stderr
    cap=root/'.ai/federation/protocol/CAPABILITIES.yaml'
    d=yaml.safe_load(cap.read_text())
    d['project_id']=pid; d['peer_id']=peer
    cap.write_text(yaml.safe_dump(d,sort_keys=False))
    key=Ed25519PrivateKey.generate()
    return root,key

def write_key(base,peer,key):
    p=base/f'{peer}.pem'
    p.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    return p

def pin(root,peer,key):
    d=root/'.ai/federation/peers'/peer; d.mkdir(parents=True,exist_ok=True)
    d.joinpath('ROOT.pub.pem').write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))

def pair(tmp):
    a,ka=make_project(tmp,'a','PROJ-A','PEER-A'); b,kb=make_project(tmp,'b','PROJ-B','PEER-B')
    pin(a,'PEER-B',kb); pin(b,'PEER-A',ka)
    ka_path=write_key(tmp,'PEER-A',ka); kb_path=write_key(tmp,'PEER-B',kb)
    oa=tmp/'oa.yaml'; ob=tmp/'ob.yaml'
    assert proto.offer(a,'PEER-A',str(oa),str(ka_path),'PEER-A')['status']=='PASS'
    assert proto.offer(b,'PEER-B',str(ob),str(kb_path),'PEER-B')['status']=='PASS'
    assert proto.negotiate(a,str(ob),'PEER-B',True)['status']=='NEGOTIATED'
    assert proto.negotiate(b,str(oa),'PEER-A',True)['status']=='NEGOTIATED'
    hello=tmp/'hello.json'; opened=secure.open_channel(a,'PEER-B','PROJ-B',ka_path,'PEER-A',hello)
    ack=secure.accept_channel(b,hello,'PEER-B','PEER-A',kb_path,'PEER-B')
    assert secure.confirm_channel(a,hello,Path(ack['ack_file']),opened['channel_id'],'PEER-B')['status']=='PASS'
    return a,b,ka_path,kb_path,opened['channel_id']

def test_initializer_and_check(tmp_path):
    root,_=make_project(tmp_path,'p','PROJ','PEER')
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert m['framework']['version']=='2.7.0'
    assert m['extensions']['version']=='2.7'
    assert m['protocols']['federation_key_lifecycle']=='UAAF-FED-2.7'
    assert (root/'.ai/federation/secure/LIFECYCLE.yaml').exists()
    assert (root/'.ai/federation/secure/KEY-REVOCATIONS.yaml').exists()
    assert (root/'.ai/federation/secure/KEY-STORAGE.yaml').exists()
    r=life.check(root); assert r['status']=='PASS'

def test_close_retire_and_deny(tmp_path):
    a,b,_,_,cid=pair(tmp_path)
    assert secure.send(a,cid,{'before':'close'},tmp_path/'msg.json')['status']=='PASS'
    r=life.close(a,cid,'ADMIN'); assert r['new_status']=='CLOSED'
    assert not list((a/'.ai/federation/secure/keys').glob(f'{cid}.*.x25519.pem'))
    denied=secure.send(a,cid,{'after':'close'},tmp_path/'msg2.json')
    assert denied['status']=='DENIED' and denied['reason']=='CHANNEL_LIFECYCLE_CLOSED'
    assert life.close(a,cid,'ADMIN')['idempotent'] is True

def test_expire_and_idempotent(tmp_path):
    a,b,_,_,cid=pair(tmp_path)
    cp=a/f'.ai/federation/secure/CHANNELS/{cid}.yaml'
    ch=yaml.safe_load(cp.read_text()); ch['expires_at']='2000-01-01T00:00:00Z'; cp.write_text(yaml.safe_dump(ch,sort_keys=False))
    r=life.expire(a,cid); assert r['new_status']=='EXPIRED'
    assert not list((a/'.ai/federation/secure/keys').glob(f'{cid}.*.x25519.pem'))
    assert secure.send(a,cid,{'x':1},tmp_path/'expired.json')['reason']=='CHANNEL_LIFECYCLE_EXPIRED'
    assert life.expire(a,cid)['new_status']=='EXPIRED'

def test_revoke_monotonic_and_recover(tmp_path):
    a,b,_,_,cid=pair(tmp_path)
    r=life.revoke(a,cid,'REVOKED'); assert r['status']=='PASS' and r['revocation_epoch']==1
    rev=yaml.safe_load((a/'.ai/federation/secure/KEY-REVOCATIONS.yaml').read_text())
    assert [e['revocation_epoch'] for e in rev['entries']]==[1]
    assert secure.send(a,cid,{'x':1},tmp_path/'revoked.json')['reason']=='CHANNEL_LIFECYCLE_REVOKED'
    # Recovering a revoked channel must never resurrect it.
    rr=life.recover(a,cid); assert rr['requires_new_handshake'] is True
    assert life.lifecycle_state(a,cid)=='REVOKED'

def test_missing_private_state_requires_new_handshake(tmp_path):
    a,b,_,_,cid=pair(tmp_path)
    for p in (a/'.ai/federation/secure/keys').glob(f'{cid}.*.x25519.pem'): p.unlink()
    r=life.recover(a,cid)
    assert r['status']=='PASS' and r['requires_new_handshake'] is True
    assert r['private_keys_present'] is False
    assert life.lifecycle_state(a,cid)=='RECOVERY_REQUIRED'
    assert secure.send(a,cid,{'x':1},tmp_path/'missing.json')['status']=='DENIED'

def test_storage_policy_and_doctor(tmp_path):
    root,_=make_project(tmp_path,'p','PROJ','PEER')
    st=yaml.safe_load((root/'.ai/federation/secure/KEY-STORAGE.yaml').read_text())
    assert st['secret_export']=='DISABLED'
    assert st['provider']=='filesystem'
    d=run('doctor',root,'--json')
    assert d.returncode==0,d.stdout+d.stderr
    assert json.loads(d.stdout)['mode']=='compact-v2.7'

def test_downgrade_removes_v27_namespace(tmp_path):
    root,_=make_project(tmp_path,'p','PROJ','PEER')
    p=run('init',root,'--profile','full','--extension','v2.6','--force')
    assert p.returncode==0,p.stdout+p.stderr
    assert not (root/'.ai/federation/secure/LIFECYCLE.yaml').exists()
    assert not (root/'.ai/federation/secure/KEY-REVOCATIONS.yaml').exists()
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert str(m['extensions']['version'])=='2.6'
