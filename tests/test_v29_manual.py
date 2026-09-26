from pathlib import Path
import os, sys, json, yaml, tempfile, shutil
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
ROOT=Path('/mnt/data/uaf-v2.9-work')
sys.path.insert(0,str(ROOT/'tools'))
import uaf_init, uaf_key_ops as ops, uaf_federation_protocol as proto, uaf_federation_confidential as secure

def init(base,name,pid,peer):
    r=base/name
    uaf_init.main
    import subprocess
    rr=subprocess.run([sys.executable,str(ROOT/'tools/uaf.py'),'init',str(r),'--profile','full','--extension','v2.9','--name',pid,'--type','fullstack'],capture_output=True,text=True)
    assert rr.returncode==0,rr.stdout+rr.stderr
    cap=r/'.ai/federation/protocol/CAPABILITIES.yaml'; d=yaml.safe_load(cap.read_text()); d['project_id']=pid; d['peer_id']=peer; cap.write_text(yaml.safe_dump(d,sort_keys=False)); return r

def write_priv(path,key): path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())); path.chmod(0o600)

def pub_file(path,key): path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))

with tempfile.TemporaryDirectory(prefix='uaf29-') as td:
    base=Path(td); keydir=base/'keys'; keydir.mkdir(); os.environ['UAAF_KEY_DIR']=str(keydir)
    a=init(base,'a','PROJ-A','PEER-A'); b=init(base,'b','PROJ-B','PEER-B')
    ka=Ed25519PrivateKey.generate(); kb=Ed25519PrivateKey.generate();
    ka_priv=keydir/'PEER-A.ed25519.pem'; kb_priv=keydir/'PEER-B.ed25519.pem'; write_priv(ka_priv,ka); write_priv(kb_priv,kb)
    ka_pub=base/'PEER-A.pub.pem'; kb_pub=base/'PEER-B.pub.pem'; pub_file(ka_pub,ka); pub_file(kb_pub,kb)
    # Bind public references in the project custody registry.
    assert ops.bind(a,'PEER-A','federation-signing,federation-confidential-channel-open,federation-confidential-channel-resume',ka_pub)['status']=='PASS'
    assert ops.bind(b,'PEER-B','federation-signing,federation-confidential-channel-accept',kb_pub)['status']=='PASS'
    payload=base/'payload.txt'; payload.write_text('provider-backed payload',encoding='utf-8'); sig=base/'payload.sig.json'
    assert ops.sign_file(a,payload,'PEER-A','federation-signing',sig)['status']=='PASS'
    assert ops.verify_file(a,payload,'PEER-A','federation-signing',sig)['status']=='PASS'
    raw=sig.read_text(); assert 'PRIVATE KEY' not in raw and 'BEGIN' not in raw
    # Establish protocol contract using normal protocol capability signing keys outside repo.
    oa=base/'a.offer.yaml'; ob=base/'b.offer.yaml'
    assert proto.offer(a,'PEER-A',str(oa),str(ka_priv),'PEER-A')['status']=='PASS'
    assert proto.offer(b,'PEER-B',str(ob),str(kb_priv),'PEER-B')['status']=='PASS'
    # Pin peer roots before federation negotiation.
    for root,peer,key in [(a,'PEER-B',kb),(b,'PEER-A',ka)]:
        d=root/'.ai/federation/peers'/peer; d.mkdir(parents=True,exist_ok=True); pub_file(d/'ROOT.pub.pem',key)
    assert proto.negotiate(a,str(ob),'PEER-B',True)['status']=='NEGOTIATED'
    assert proto.negotiate(b,str(oa),'PEER-A',True)['status']=='NEGOTIATED'
    hello=base/'hello.json'
    op=secure.open_channel(a,'PEER-B','PROJ-B',None,'PEER-A','PEER-A',hello)
    assert op['status']=='PASS',op
    ack=secure.accept_channel(b,hello,'PEER-B','PEER-A',None,'PEER-B','PEER-B')
    assert ack['status']=='PASS',ack
    cf=secure.confirm_channel(a,hello,Path(ack['ack_file']),op['channel_id'],'PEER-B')
    assert cf['status']=='PASS',cf
    msg=base/'msg.json'
    assert secure.send(a,op['channel_id'],{'hello':'provider'},msg)['status']=='PASS'
    received=secure.receive(b,op['channel_id'],msg)
    assert received['status']=='PASS' and received['payload']['hello']=='provider',received
    print('PASS provider-backed sign + federation handshake + encrypted message')
