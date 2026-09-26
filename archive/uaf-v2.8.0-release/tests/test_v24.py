from __future__ import annotations
import base64, hashlib, json, shutil, subprocess, sys
from pathlib import Path
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT/'tools/uaf.py')]

FEATURES = {
    'capability-exchange': {'required': True, 'optional': False, 'fallback_safe': True, 'min_protocol': {'federation_protocol':'2.4'}},
    'protocol-negotiation': {'required': True, 'optional': False, 'fallback_safe': True, 'min_protocol': {'federation_protocol':'2.4'}},
    'safe-fallback': {'required': False, 'optional': True, 'fallback_safe': True, 'min_protocol': {'federation_protocol':'2.4'}},
}


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def fp(v):
    return hashlib.sha256(canon(v)).hexdigest()


def init(root: Path, ext='v2.4'):
    p = subprocess.run([*CLI,'init',str(root),'--profile','full','--extension',ext,'--name',root.name,'--type','fullstack'], capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stdout + p.stderr


def run(*args, timeout=20):
    return subprocess.run([*CLI,*map(str,args)], capture_output=True, text=True, timeout=timeout)


def remote_offer(path: Path, protocols=None, features=None, fallbacks=None, peer='PEER-B'):
    protocols = protocols or {'federation':['2.0'],'federation_ops':['2.1'],'federation_intelligence':['2.2'],'federation_policy':['2.3'],'federation_protocol':['2.4']}
    features = FEATURES if features is None else features
    doc = {'schema_version':'2.4','offer_id':'OFF-TEST','peer_id':peer,'capabilities':{
        'project_id':'REMOTE','peer_id':peer,'protocols':protocols,'features':features,
        'security':{'min_evidence':'E3','require_signed_offer':True,'require_signed_contract':True},
        'compatibility':{'fallbacks': ({'federation_protocol':['2.3']} if fallbacks is None else fallbacks)},
    }}
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')
    return doc


def sign_offer(root: Path, offer_path: Path, peer='PEER-SIGNED'):
    peer_dir = root/'.ai/federation/peers'/peer
    peer_dir.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_pem = pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    (peer_dir/'ROOT.pub.pem').write_bytes(pub_pem)
    doc = yaml.safe_load(offer_path.read_text())
    payload = {k:v for k,v in doc.items() if k!='signature'}
    sig = priv.sign(canon(payload))
    doc['signature'] = {'schema_version':'2.4','purpose':'federation-capability-offer','payload_sha256':fp(payload),'signature_b64':base64.b64encode(sig).decode(),'key_id':peer}
    offer_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')
    return doc


def test_initializer_and_doctor(tmp_path):
    root=tmp_path/'p'; init(root)
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert m['framework']['version']=='2.4.0'
    assert m['extensions']['version']=='2.4'
    assert m['protocols']['federation_protocol']=='UAAF-FED-2.4'
    for rel in ['.ai/federation/protocol/CAPABILITIES.yaml','.ai/federation/protocol/COMPATIBILITY.yaml','.ai/federation/protocol/NEGOTIATION.yaml','.ai/federation/protocol/PROTOCOL-CONTRACT.yaml','.ai/federation/protocol/AUDIT.jsonl']:
        assert (root/rel).exists()
    p=run('doctor',root,'--json'); assert p.returncode==0,p.stdout+p.stderr
    assert json.loads(p.stdout)['status']=='PASS'


def test_exact_match_and_authorize(tmp_path):
    root=tmp_path/'p'; init(root)
    offer=tmp_path/'remote.yaml'; remote_offer(offer)
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-B'); assert p.returncode==0,p.stdout+p.stderr
    d=json.loads(p.stdout); assert d['status']=='NEGOTIATED'; assert d['selected_protocols']['federation_protocol']=='2.4'
    p=run('federation-protocol','authorize',root,'--protocol-family','federation_protocol','--version','2.4','--feature','protocol-negotiation'); assert p.returncode==0
    p=run('federation-protocol','authorize',root,'--protocol-family','federation_protocol','--version','2.3','--feature','protocol-negotiation'); assert p.returncode!=0


def test_signed_offer(tmp_path):
    root=tmp_path/'p'; init(root)
    offer=tmp_path/'remote.yaml'; remote_offer(offer, peer='PEER-SIGNED'); sign_offer(root,offer,'PEER-SIGNED')
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-SIGNED','--require-remote-signature'); assert p.returncode==0,p.stdout+p.stderr
    assert json.loads(p.stdout)['status']=='NEGOTIATED'


def test_bad_signature_denied(tmp_path):
    root=tmp_path/'p'; init(root)
    offer=tmp_path/'remote.yaml'; remote_offer(offer, peer='PEER-SIGNED'); sign_offer(root,offer,'PEER-SIGNED')
    d=yaml.safe_load(offer.read_text()); d['capabilities']['peer_id']='TAMPERED'; offer.write_text(yaml.safe_dump(d,sort_keys=False))
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-SIGNED','--require-remote-signature'); assert p.returncode!=0
    assert 'PAYLOAD_HASH_MISMATCH' in p.stdout or 'SIGNATURE_INVALID' in p.stdout


def test_incompatible_protocol_denied(tmp_path):
    root=tmp_path/'p'; init(root)
    offer=tmp_path/'remote.yaml'; remote_offer(offer, protocols={'federation':['2.0'],'federation_ops':['2.1'],'federation_intelligence':['2.2'],'federation_policy':['2.3'],'federation_protocol':['9.0']}, fallbacks={})
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-B'); assert p.returncode!=0
    assert json.loads(p.stdout)['reason']=='NO_COMPATIBLE_PROTOCOL'


def test_fallback_requires_both_peer_declarations(tmp_path):
    root=tmp_path/'p'; init(root)
    offer=tmp_path/'remote.yaml'; remote_offer(offer, protocols={'federation':['2.0'],'federation_ops':['2.1'],'federation_intelligence':['2.2'],'federation_policy':['2.3'],'federation_protocol':['2.3']}, fallbacks={})
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-B'); assert p.returncode!=0
    assert 'NO_COMPATIBLE_PROTOCOL' in p.stdout


def test_safe_fallback_is_explicit_and_reviewable(tmp_path):
    root=tmp_path/'p'; init(root)
    cap=root/'.ai/federation/protocol/CAPABILITIES.yaml'; d=yaml.safe_load(cap.read_text())
    for f in ('capability-exchange','protocol-negotiation'):
        d['features'][f]['required']=False; d['features'][f]['optional']=True
        d['features'][f]['min_protocol']['federation_protocol']='2.3'
    d['protocols']['federation_protocol']=['2.4']; d['compatibility']['fallbacks']['federation_protocol']=['2.3']; cap.write_text(yaml.safe_dump(d,sort_keys=False))
    offer=tmp_path/'remote.yaml'; remote_offer(offer, protocols={'federation':['2.0'],'federation_ops':['2.1'],'federation_intelligence':['2.2'],'federation_policy':['2.3'],'federation_protocol':['2.3']}, features=d['features'], fallbacks={'federation_protocol':['2.3']})
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-B'); assert p.returncode==0
    assert json.loads(p.stdout)['status']=='FALLBACK_NEGOTIATED'


def test_required_feature_mismatch_denied(tmp_path):
    root=tmp_path/'p'; init(root)
    remote_features=dict(FEATURES); remote_features['remote-only']={'required':True,'optional':False,'fallback_safe':False,'min_protocol':{'federation_protocol':'2.4'}}
    offer=tmp_path/'remote.yaml'; remote_offer(offer,features=remote_features)
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-B'); assert p.returncode!=0
    assert 'REQUIRED_FEATURE_UNAVAILABLE:remote-only' in p.stdout


def test_protocol_contract_deny_first(tmp_path):
    root=tmp_path/'p'; init(root)
    p=run('federation-protocol','authorize',root,'--protocol-family','federation_protocol','--version','2.4'); assert p.returncode!=0
    assert 'PROTOCOL_CONTRACT_NOT_ACTIVE' in p.stdout
    p=run('federation-protocol','check',root); assert p.returncode==0


def test_v23_downgrade_removes_v24_namespace(tmp_path):
    root=tmp_path/'p'; init(root)
    p=run('init',root,'--profile','full','--extension','v2.3','--force','--docs','auto'); assert p.returncode==0,p.stdout+p.stderr
    assert not (root/'.ai/federation/protocol').exists()
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text()); assert str(m['extensions']['version'])=='2.3'


def test_cli_signed_capability_offer(tmp_path):
    root=tmp_path/'p'; init(root)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    keydir=tmp_path/'keys'; keydir.mkdir()
    priv=Ed25519PrivateKey.generate()
    priv_path=keydir/'root.pem'; priv_path.write_bytes(priv.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    out=tmp_path/'offer.yaml'
    p=run('federation-protocol','offer',root,'--peer-id','PEER-CLI','--out',out,'--private-key',priv_path,'--key-id','PEER-CLI')
    assert p.returncode==0,p.stdout+p.stderr
    d=yaml.safe_load(out.read_text()); assert d.get('signature',{}).get('purpose')=='federation-capability-offer'


def test_conformance_after_active_contract(tmp_path):
    root=tmp_path/'p'; init(root)
    offer=tmp_path/'remote.yaml'; remote_offer(offer)
    p=run('federation-protocol','negotiate',root,'--remote-file',offer,'--peer-id','PEER-B'); assert p.returncode==0
    p=run('check',root,'--level','full'); assert p.returncode==0,p.stdout+p.stderr
    p=run('federation-protocol','check',root); assert p.returncode==0
