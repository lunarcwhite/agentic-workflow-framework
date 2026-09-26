#!/usr/bin/env python3
"""UAAF v2.7 secure key and channel lifecycle reference layer.

Lifecycle guarantees:
- explicit close / expire / revoke / retire states;
- fail-closed transport integration through lifecycle state;
- revocation is append-only and monotonic by epoch;
- recovery never resurrects missing private keys;
- secure key storage is provider-abstracted; the reference filesystem provider
  performs best-effort file retirement only and does not claim forensic erasure.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

SCHEMA='2.7'
FED=Path('.ai/federation')
SECURE=FED/'secure'
CHANNELS=SECURE/'CHANNELS'
KEYS=SECURE/'keys'
LIFECYCLE=SECURE/'LIFECYCLE.yaml'
REVOCATIONS=SECURE/'KEY-REVOCATIONS.yaml'
STORAGE=SECURE/'KEY-STORAGE.yaml'
AUDIT=SECURE/'AUDIT.jsonl'
REVISION_REASONS={'ADMIN','EXPIRED','REVOKED','RECOVERY','POLICY'}
TERMINAL={'CLOSED','EXPIRED','REVOKED','RECOVERY_REQUIRED'}


def now(): return datetime.now(timezone.utc)
def iso(dt=None): return (dt or now()).isoformat(timespec='seconds').replace('+00:00','Z')
def parse_ts(v):
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception: return None

def load_yaml(p, default=None):
    if not p.exists(): return dict(default or {})
    try:
        v=yaml.safe_load(p.read_text(encoding='utf-8')) or {}
        return v if isinstance(v,dict) else dict(default or {})
    except Exception: return dict(default or {})

def dump_yaml(p,d):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(yaml.safe_dump(d,sort_keys=False),encoding='utf-8')

def canon(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def fp(v): return hashlib.sha256(canon(v)).hexdigest()

def manifest(root): return load_yaml(root/'.ai/manifest.yaml',{})
def project_id(root): return str((manifest(root).get('project') or {}).get('name') or root.name)
def local_peer_id(root):
    cap=load_yaml(root/' .ai/federation/protocol/CAPABILITIES.yaml'.strip(),{})
    return str(cap.get('peer_id') or project_id(root))

def ensure(root):
    for p in (CHANNELS,KEYS): (root/p).mkdir(parents=True,exist_ok=True)
    for p,default in [(STORAGE,{'schema_version':SCHEMA,'provider':'filesystem','mode':'best_effort_delete','secret_export':'DISABLED'}),(LIFECYCLE,{'schema_version':SCHEMA,'status':'READY','updated_at':iso(),'channels':{}}),(REVOCATIONS,{'schema_version':SCHEMA,'revocation_epoch':0,'entries':[]}),(AUDIT, None)]:
        q=root/p
        if not q.exists():
            if p==AUDIT: q.parent.mkdir(parents=True,exist_ok=True); q.write_text('',encoding='utf-8')
            else: dump_yaml(q,default)
    try: (root/KEYS).chmod(0o700)
    except OSError: pass

def audit(root,event):
    ensure(root); p=root/AUDIT
    prior='GENESIS'
    lines=[x for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
    if lines:
        try: prior=json.loads(lines[-1]).get('entry_hash','GENESIS')
        except Exception: prior='BROKEN'
    row={'schema_version':SCHEMA,'timestamp':iso(),'prev_hash':prior,**event}
    row['entry_hash']=hashlib.sha256(canon(row)).hexdigest()
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n')

def channel_path(root,cid): return root/CHANNELS/f'{cid}.yaml'
def load_channel(root,cid): return load_yaml(channel_path(root,cid),{})

def lifecycle_state(root,cid):
    ch=load_channel(root,cid)
    if not ch: return 'NOT_FOUND'
    lc=load_yaml(root/LIFECYCLE,{})
    state=((lc.get('channels') or {}).get(cid) or {}).get('status')
    if state: return str(state)
    st=str(ch.get('status','UNKNOWN'))
    exp=parse_ts(ch.get('expires_at'))
    if st=='OPEN' and exp and exp<=now(): return 'EXPIRED'
    return st

def update_channel_status(root,cid,status,reason,actor='local'):
    ch=load_channel(root,cid)
    if not ch: return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    lc=load_yaml(root/LIFECYCLE,{})
    lc.setdefault('channels',{})[cid]={'status':status,'updated_at':iso(),'reason':reason,'actor':actor,'key_epoch':int(ch.get('key_epoch',0) or 0)}
    lc['updated_at']=iso(); dump_yaml(root/LIFECYCLE,lc)
    ch['status']=status; ch['lifecycle_reason']=reason; ch['lifecycle_updated_at']=iso(); dump_yaml(channel_path(root,cid),ch)
    audit(root,{'event':'CHANNEL_LIFECYCLE_CHANGED','channel_id':cid,'new_status':status,'reason':reason,'actor':actor})
    return {'status':'PASS','channel_id':cid,'new_status':status}

def retire_keys(root,cid,reason):
    ensure(root); retired=[]
    for p in sorted((root/KEYS).glob(f'{cid}.*')):
        if not p.is_file(): continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        meta=p.with_suffix(p.suffix+'.retired.json')
        meta.write_text(json.dumps({'schema_version':SCHEMA,'path':str(p.relative_to(root)),'sha256':digest,'reason':reason,'retired_at':iso(),'provider':'filesystem','destruction_semantics':'best_effort_unlink'},indent=2)+'\n',encoding='utf-8')
        try: p.unlink(); retired.append(str(p.relative_to(root)))
        except OSError: pass
    if retired: audit(root,{'event':'KEYS_RETIRED','channel_id':cid,'reason':reason,'paths':retired})
    return retired

def close(root,cid,reason='ADMIN'):
    if reason not in REVISION_REASONS: return {'status':'DENIED','reason':'INVALID_CLOSE_REASON'}
    st=lifecycle_state(root,cid)
    if st=='NOT_FOUND': return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    if st in TERMINAL: return {'status':'PASS','channel_id':cid,'new_status':st,'idempotent':True}
    r=update_channel_status(root,cid,'CLOSED',reason); retire_keys(root,cid,reason); return r

def expire(root,cid=None):
    if cid:
        ch=load_channel(root,cid)
        if not ch:
            return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
        raw_status=str(ch.get('status','UNKNOWN'))
        exp=parse_ts(ch.get('expires_at'))
        if raw_status=='OPEN' and exp and exp<=now():
            r=update_channel_status(root,cid,'EXPIRED','EXPIRED'); r['retired_keys']=retire_keys(root,cid,'EXPIRED'); return r
        return {'status':'PASS','channel_id':cid,'new_status':lifecycle_state(root,cid)}
    out=[]
    for p in (root/CHANNELS).glob('SC-*.yaml') if (root/CHANNELS).exists() else []:
        r=expire(root,p.stem); out.append(r)
    return {'status':'PASS','channels':out}

def revoke(root,cid,reason,epoch=None):
    if reason not in REVISION_REASONS: return {'status':'DENIED','reason':'INVALID_REVOCATION_REASON'}
    ch=load_channel(root,cid)
    if not ch: return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    e=int(epoch or ch.get('key_epoch',0) or 0)
    rev=load_yaml(root/REVOCATIONS,{})
    current=int(rev.get('revocation_epoch',0) or 0)+1
    entry={'channel_id':cid,'key_epoch':e,'revocation_epoch':current,'reason':reason,'revoked_at':iso(),'project_id':project_id(root)}
    rev['revocation_epoch']=current; rev.setdefault('entries',[]).append(entry); dump_yaml(root/REVOCATIONS,rev)
    r=update_channel_status(root,cid,'REVOKED',reason); retired=retire_keys(root,cid,'REVOKED')
    r.update({'revocation_epoch':current,'retired_keys':retired}); return r

def check(root):
    ensure(root); issues=[]
    storage=load_yaml(root/STORAGE,{})
    if storage.get('provider') not in {'filesystem','os-keychain','kms','hsm'}: issues.append('KEY_STORAGE_PROVIDER_UNKNOWN')
    channels=list((root/CHANNELS).glob('SC-*.yaml')) if (root/CHANNELS).exists() else []
    rev=load_yaml(root/REVOCATIONS,{})
    rev_epoch=int(rev.get('revocation_epoch',0) or 0)
    for p in channels:
        ch=load_yaml(p,{})
        cid=p.stem; st=lifecycle_state(root,cid)
        if str(ch.get('schema_version'))!='2.6': issues.append(f'CHANNEL_SCHEMA_MISMATCH:{cid}')
        if st in TERMINAL:
            for kp in (root/KEYS).glob(f'{cid}.*'):
                if kp.is_file() and not kp.name.endswith('.retired.json'): issues.append(f'RETIREMENT_INCOMPLETE:{cid}:{kp.name}')
        if st=='REVOKED':
            ents=[x for x in rev.get('entries',[]) if x.get('channel_id')==cid]
            if not ents: issues.append(f'REVOCATION_MISSING:{cid}')
        if st=='EXPIRED':
            exp=parse_ts(ch.get('expires_at'))
            if not exp or exp>now(): issues.append(f'EXPIRE_STATE_INVALID:{cid}')
    return {'status':'PASS' if not issues else 'FAIL','issues':issues,'configured':True,'revocation_epoch':rev_epoch,'channel_count':len(channels)}

def recover(root,cid):
    ch=load_channel(root,cid)
    if not ch: return {'status':'DENIED','reason':'CHANNEL_NOT_FOUND'}
    st=lifecycle_state(root,cid)
    existing=[str(p.relative_to(root)) for p in (root/KEYS).glob(f'{cid}.*') if p.is_file() and not p.name.endswith('.retired.json')]
    if st in {'REVOKED','EXPIRED','CLOSED'}:
        audit(root,{'event':'CHANNEL_RECOVERY_BLOCKED','channel_id':cid,'status':st,'reason':'TERMINAL_STATE_REQUIRES_NEW_HANDSHAKE'})
        return {'status':'PASS','channel_id':cid,'requires_new_handshake':True,'private_keys_present':bool(existing),'terminal_status':st}
    if not existing:
        r=update_channel_status(root,cid,'RECOVERY_REQUIRED','LOCAL_KEY_STATE_MISSING')
        r['requires_new_handshake']=True; r['private_keys_present']=False
        audit(root,{'event':'CHANNEL_RECOVERY_REQUIRED','channel_id':cid,'reason':'LOCAL_KEY_STATE_MISSING'})
        return r
    return {'status':'PASS','channel_id':cid,'recovery':'NOT_NEEDED','private_keys_present':True}


def main():
    ap=argparse.ArgumentParser(description='UAAF v2.7 secure key lifecycle')
    sp=ap.add_subparsers(dest='cmd',required=True)
    for c in ['check','expire']:
        q=sp.add_parser(c); q.add_argument('path',nargs='?',default='.'); q.add_argument('--channel-id')
    q=sp.add_parser('close'); q.add_argument('path'); q.add_argument('--channel-id',required=True); q.add_argument('--reason',default='ADMIN')
    q=sp.add_parser('revoke'); q.add_argument('path'); q.add_argument('--channel-id',required=True); q.add_argument('--reason',default='REVOKED'); q.add_argument('--epoch',type=int)
    q=sp.add_parser('recover'); q.add_argument('path'); q.add_argument('--channel-id',required=True)
    q=sp.add_parser('retire'); q.add_argument('path'); q.add_argument('--channel-id',required=True); q.add_argument('--reason',default='ADMIN')
    q=sp.add_parser('inventory'); q.add_argument('path',nargs='?',default='.')
    a=ap.parse_args(); root=Path(a.path).resolve()
    try:
        if a.cmd=='check': r=check(root)
        elif a.cmd=='expire': r=expire(root,a.channel_id)
        elif a.cmd=='close': r=close(root,a.channel_id,a.reason)
        elif a.cmd=='revoke': r=revoke(root,a.channel_id,a.reason,a.epoch)
        elif a.cmd=='recover': r=recover(root,a.channel_id)
        elif a.cmd=='retire':
            ensure(root); r={'status':'PASS','retired_keys':retire_keys(root,a.channel_id,a.reason)}
        else:
            ensure(root); rows=[]
            for p in (root/KEYS).glob('*') if (root/KEYS).exists() else []:
                if p.is_file() and not p.name.endswith('.retired.json'):
                    rows.append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
            r={'status':'PASS','provider':load_yaml(root/STORAGE,{}).get('provider'),'keys':rows}
    except (OSError,ValueError,yaml.YAMLError) as exc:
        r={'status':'DENIED','reason':str(exc)}
    print(json.dumps(r,indent=2,ensure_ascii=False))
    raise SystemExit(0 if r.get('status') in {'PASS','NOT_CONFIGURED'} else 1)
if __name__=='__main__': main()
