from __future__ import annotations
import base64, json, subprocess, sys, yaml
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT/'tools/uaf.py')]

def run(*args, timeout=20):
    return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=timeout)

def init(root: Path, name: str):
    p=run('init',str(root),'--profile','full','--extension','v2.5','--name',name,'--type','fullstack')
    assert p.returncode==0,p.stdout+p.stderr

def keypair(path: Path):
    priv=Ed25519PrivateKey.generate(); path.write_bytes(priv.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    return priv.public_key()

def pin(root: Path, peer_id: str, pub):
    d=root/'.ai/federation/peers'/peer_id; d.mkdir(parents=True,exist_ok=True)
    (d/'ROOT.pub.pem').write_bytes(pub.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))

def activate_contract(root: Path):
    contract={'protocols':{'federation_protocol':'2.4'},'enabled_features':['protocol-negotiation'],'disabled_features':[],'fallbacks':{},'authority_change':'NONE','security_floor':3}
    import hashlib
    raw=json.dumps(contract,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    h=hashlib.sha256(raw).hexdigest()
    p=root/'.ai/federation/protocol/PROTOCOL-CONTRACT.yaml'
    p.write_text(yaml.safe_dump({'schema_version':'2.4','status':'NEGOTIATED','peer_id':'','contract_hash':h,'contract':contract},sort_keys=False),encoding='utf-8')

def set_peer(root: Path, peer_id: str):
    p=root/'.ai/federation/protocol/CAPABILITIES.yaml'; d=yaml.safe_load(p.read_text())
    d['peer_id']=peer_id; d['project_id']=root.name; p.write_text(yaml.safe_dump(d,sort_keys=False),encoding='utf-8')

def test_initializer_and_doctor(tmp_path):
    root=tmp_path/'a'; init(root,'PROJ-A')
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert m['framework']['version']=='2.5.0'; assert m['extensions']['version']=='2.5'
    assert m['protocols']['federation_transport']=='UAAF-FED-2.5'
    for rel in ['.ai/federation/protocol/PROTOCOL-CONTRACT.yaml','.ai/federation/transport/CHANNELS','.ai/federation/transport/INBOX','.ai/federation/transport/OUTBOX','.ai/federation/transport/AUDIT.jsonl']:
        assert (root/rel).exists(), rel
    p=run('doctor',str(root),'--json'); assert p.returncode==0,p.stdout+p.stderr
    assert json.loads(p.stdout)['status']=='PASS'

def test_requires_active_v24_contract(tmp_path):
    root=tmp_path/'a'; init(root,'PROJ-A'); keydir=tmp_path/'keys';keydir.mkdir(); privp=keydir/'a.pem';keypair(privp); pin(root,'PEER-B',keypair(keydir/'b.pub.pem'))
    p=run('federation-transport','open',str(root),'--peer-id','PEER-B','--peer-project-id','PROJ-B','--private-key',str(privp),'--key-id','A')
    assert p.returncode!=0; assert 'PROTOCOL_CONTRACT_NOT_ACTIVE' in p.stdout

def test_channel_open_accept_confirm_send_receive_and_replay(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; init(a,'PROJ-A'); init(b,'PROJ-B'); set_peer(a,'PEER-A'); set_peer(b,'PEER-B'); activate_contract(a); activate_contract(b)
    ka=tmp_path/'a.pem'; kb=tmp_path/'b.pem'; pa=keypair(ka); pb=keypair(kb); pin(a,'PEER-B',pb); pin(b,'PEER-A',pa)
    hello=tmp_path/'hello.json'; p=run('federation-transport','open',str(a),'--peer-id','PEER-B','--peer-project-id','PROJ-B','--private-key',str(ka),'--key-id','PEER-A','--out',str(hello)); assert p.returncode==0,p.stdout+p.stderr
    cid=json.loads(p.stdout)['channel_id']
    ack=tmp_path/'ack.json'; p=run('federation-transport','accept',str(b),'--hello-file',str(hello),'--local-peer-id','PEER-B','--sender-peer-id','PEER-A','--private-key',str(kb),'--key-id','PEER-B'); assert p.returncode==0,p.stdout+p.stderr
    ack.write_text(json.dumps(json.loads(p.stdout)['ack'],indent=2))
    p=run('federation-transport','confirm',str(a),'--hello-file',str(hello),'--ack-file',str(ack),'--channel-id',cid,'--peer-id','PEER-B'); assert p.returncode==0,p.stdout+p.stderr
    msg=tmp_path/'msg.json'; p=run('federation-transport','send',str(a),'--channel-id',cid,'--payload-json','{"event":"ping"}','--private-key',str(ka),'--key-id','PEER-A','--out',str(msg)); assert p.returncode==0,p.stdout+p.stderr
    p=run('federation-transport','receive',str(b),'--channel-id',cid,'--message-file',str(msg)); assert p.returncode==0,p.stdout+p.stderr
    assert json.loads(p.stdout)['payload']=={'event':'ping'}
    p=run('federation-transport','receive',str(b),'--channel-id',cid,'--message-file',str(msg)); assert p.returncode!=0; assert 'SEQUENCE_VIOLATION' in p.stdout

def test_tamper_and_audience_rejected(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; init(a,'PROJ-A'); init(b,'PROJ-B'); set_peer(a,'PEER-A'); set_peer(b,'PEER-B'); activate_contract(a); activate_contract(b)
    ka=tmp_path/'a.pem'; kb=tmp_path/'b.pem'; pa=keypair(ka); pb=keypair(kb); pin(a,'PEER-B',pb); pin(b,'PEER-A',pa)
    hello=tmp_path/'hello.json'; assert run('federation-transport','open',str(a),'--peer-id','PEER-B','--peer-project-id','PROJ-B','--private-key',str(ka),'--key-id','PEER-A','--out',str(hello)).returncode==0
    p=run('federation-transport','accept',str(b),'--hello-file',str(hello),'--local-peer-id','PEER-B','--sender-peer-id','PEER-A','--private-key',str(kb),'--key-id','PEER-B'); assert p.returncode==0
    ack=tmp_path/'ack.json'; ack.write_text(json.dumps(json.loads(p.stdout)['ack']))
    cid=json.loads(hello.read_text())['channel_id']; assert run('federation-transport','confirm',str(a),'--hello-file',str(hello),'--ack-file',str(ack),'--channel-id',cid,'--peer-id','PEER-B').returncode==0
    msg=tmp_path/'msg.json'; assert run('federation-transport','send',str(a),'--channel-id',cid,'--payload-json','{"x":1}','--private-key',str(ka),'--key-id','PEER-A','--out',str(msg)).returncode==0
    d=json.loads(msg.read_text()); d['payload']['x']=2; msg.write_text(json.dumps(d))
    p=run('federation-transport','receive',str(b),'--channel-id',cid,'--message-file',str(msg)); assert p.returncode!=0; assert 'PAYLOAD_HASH_MISMATCH' in p.stdout

def test_resume_replay_protection(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; init(a,'PROJ-A'); init(b,'PROJ-B'); set_peer(a,'PEER-A'); set_peer(b,'PEER-B'); activate_contract(a); activate_contract(b)
    ka=tmp_path/'a.pem'; kb=tmp_path/'b.pem'; pa=keypair(ka); pb=keypair(kb); pin(a,'PEER-B',pb); pin(b,'PEER-A',pa)
    hello=tmp_path/'hello.json'; run('federation-transport','open',str(a),'--peer-id','PEER-B','--peer-project-id','PROJ-B','--private-key',str(ka),'--key-id','PEER-A','--out',str(hello))
    p=run('federation-transport','accept',str(b),'--hello-file',str(hello),'--local-peer-id','PEER-B','--sender-peer-id','PEER-A','--private-key',str(kb),'--key-id','PEER-B'); ack=tmp_path/'ack.json'; ack.write_text(json.dumps(json.loads(p.stdout)['ack']))
    cid=json.loads(hello.read_text())['channel_id']; assert run('federation-transport','confirm',str(a),'--hello-file',str(hello),'--ack-file',str(ack),'--channel-id',cid,'--peer-id','PEER-B').returncode==0
    token=tmp_path/'resume.json'; p=run('federation-transport','resume',str(a),'--channel-id',cid,'--private-key',str(ka),'--key-id','PEER-A','--out',str(token)); assert p.returncode==0
    p=run('federation-transport','resume-accept',str(b),'--token-file',str(token),'--local-peer-id','PEER-B','--sender-peer-id','PEER-A'); assert p.returncode==0,p.stdout+p.stderr
    p=run('federation-transport','resume-accept',str(b),'--token-file',str(token),'--local-peer-id','PEER-B','--sender-peer-id','PEER-A'); assert p.returncode!=0; assert 'RESUME_REPLAY' in p.stdout

def test_downgrade_to_v24_removes_transport(tmp_path):
    root=tmp_path/'p'; init(root,'PROJ-A')
    p=run('init',str(root),'--profile','full','--extension','v2.4','--force','--docs','auto'); assert p.returncode==0,p.stdout+p.stderr
    assert not (root/'.ai/federation/transport').exists()
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text()); assert str(m['extensions']['version'])=='2.4'
