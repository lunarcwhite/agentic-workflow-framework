from __future__ import annotations
import os, subprocess, sys, tempfile, json, yaml
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
ROOT=Path(__file__).resolve().parents[1]; CLI=[sys.executable,str(ROOT/'tools/uaf.py')]

def run(*args, timeout=15): return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=timeout)

def init(base,name='p',pid='PROJ',peer='PEER'):
    r=base/name; p=run('init',r,'--profile','full','--extension','v2.9','--name',pid,'--type','fullstack'); assert p.returncode==0,p.stdout+p.stderr; c=r/'.ai/federation/protocol/CAPABILITIES.yaml'; d=yaml.safe_load(c.read_text()); d['project_id']=pid; d['peer_id']=peer; c.write_text(yaml.safe_dump(d,sort_keys=False)); return r

def pem(path,key,public=False):
    if public: path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    else: path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())); path.chmod(0o600)

def test_v29_e2e():
    with tempfile.TemporaryDirectory(prefix='uaf29-') as td:
        b=Path(td); kd=b/'keydir'; kd.mkdir(); os.environ['UAAF_KEY_DIR']=str(kd)
        root=init(b)
        k=Ed25519PrivateKey.generate(); priv=kd/'K1.ed25519.pem'; pub=b/'K1.pub.pem'; pem(priv,k); pem(pub,k,True)
        assert run('key-ops','bind',root,'--key-id','K1','--purpose','federation-signing','--public-key-file',pub).returncode==0
        payload=b/'payload.txt'; payload.write_text('hello provider'); sig=b/'payload.sig.json'
        s=run('key-ops','sign',root,'--key-id','K1','--purpose','federation-signing','--payload-file',payload,'--out',sig,'--json'); assert s.returncode==0,s.stdout+s.stderr
        v=run('key-ops','verify',root,'--key-id','K1','--purpose','federation-signing','--payload-file',payload,'--signature-file',sig,'--json'); assert v.returncode==0,v.stdout+v.stderr
        assert 'PRIVATE KEY' not in s.stdout and 'BEGIN ED25519' not in s.stdout
        refs=yaml.safe_load((root/'.ai/federation/secure/KEY-REFERENCES.yaml').read_text()); assert refs['references'][0]['allowed_purposes']==['federation-signing']

def test_v29_purpose_and_rotation():
    with tempfile.TemporaryDirectory(prefix='uaf29-') as td:
        b=Path(td); kd=b/'keydir'; kd.mkdir(); os.environ['UAAF_KEY_DIR']=str(kd); root=init(b)
        old=Ed25519PrivateKey.generate(); oldp=kd/'OLD.ed25519.pem'; oldpub=b/'OLD.pub.pem'; pem(oldp,old); pem(oldpub,old,True)
        assert run('key-ops','bind',root,'--key-id','OLD','--purpose','federation-signing','--public-key-file',oldpub).returncode==0
        bad=run('key-ops','sign-payload',root,'--key-id','OLD','--purpose','other-purpose','--payload-json','{"x":1}'); assert bad.returncode==1
        rot=run('key-ops','rotate',root,'--old-key-id','OLD','--new-key-id','NEW','--purpose','federation-signing'); assert rot.returncode==0,rot.stdout+rot.stderr
        oldsign=run('key-ops','sign-payload',root,'--key-id','OLD','--purpose','federation-signing','--payload-json','{"x":1}'); assert oldsign.returncode==1
        refs=yaml.safe_load((root/'.ai/federation/secure/KEY-REFERENCES.yaml').read_text()); rows={r['key_id']:r for r in refs['references']}; assert rows['OLD']['status']=='RETIRED' and rows['NEW']['status']=='ACTIVE'; assert not oldp.exists()

def test_v29_init_doctor_conformance():
    with tempfile.TemporaryDirectory(prefix='uaf29-') as td:
        root=init(Path(td))
        c=run('check',root,'--level','full','--json'); assert c.returncode==0,json.loads(c.stdout)
        d=run('doctor',root,'--json'); assert d.returncode==0,d.stdout+d.stderr; out=json.loads(d.stdout); assert out['mode']=='compact-v2.9'

print('v2.9 PASS')
for fn in [test_v29_e2e,test_v29_purpose_and_rotation,test_v29_init_doctor_conformance]:
    fn()
print('ALL 3/3 PASSED')
