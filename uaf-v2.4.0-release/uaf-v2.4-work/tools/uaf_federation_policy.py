#!/usr/bin/env python3
"""UAAF v2.2 federation policy inheritance and effective-policy engine."""
from __future__ import annotations
import argparse, base64, hashlib, json
from pathlib import Path
from typing import Any
import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SCHEMA = "2.2"
FED = Path('.ai/federation')
POLICY_DIR = FED / 'policy'
INHERIT = POLICY_DIR / 'INHERITANCE.yaml'
EFFECTIVE = POLICY_DIR / 'EFFECTIVE.yaml'
AUDIT = FED / 'AUDIT.jsonl'
RISK = {'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}
ALL_ACTIONS = {'handoff','state-pull','state-push','capability-sync','policy-sync'}

def load_yaml(path: Path, default=None):
    if not path.exists(): return dict(default or {})
    try:
        v = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return v if isinstance(v, dict) else dict(default or {})
    except Exception:
        return dict(default or {})

def dump_yaml(path: Path, data: dict[str,Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')

def canon(v: Any)->bytes:
    return json.dumps(v, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode()

def fp(v: Any)->str: return hashlib.sha256(canon(v)).hexdigest()

def now()->str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def public_raw(path: Path)->bytes:
    k=serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(k,Ed25519PublicKey): raise ValueError('not Ed25519')
    return k.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

def private(path: Path)->Ed25519PrivateKey:
    k=serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(k,Ed25519PrivateKey): raise ValueError('not Ed25519')
    return k

def sign(payload, private_path, key_id, purpose):
    raw=canon(payload); sig=private(private_path).sign(raw)
    return {'schema_version':SCHEMA,'algorithm':'Ed25519','key_id':key_id,'purpose':purpose,'payload_sha256':fp(payload),'signature_b64':base64.b64encode(sig).decode()}

def verify(payload,sig,public_path,purpose):
    if sig.get('schema_version')!=SCHEMA or sig.get('algorithm')!='Ed25519': return False,'SCHEMA_MISMATCH'
    if sig.get('purpose')!=purpose: return False,'PURPOSE_MISMATCH'
    if sig.get('payload_sha256')!=fp(payload): return False,'PAYLOAD_HASH_MISMATCH'
    try:
        public_raw(public_path) # validate key format
        Ed25519PublicKey.from_public_bytes(public_raw(public_path)).verify(base64.b64decode(sig.get('signature_b64',''), validate=True), canon(payload))
    except (ValueError,InvalidSignature,TypeError): return False,'SIGNATURE_INVALID'
    return True,'OK'

def ensure(root: Path):
    POLICY_DIR_ABS=root/POLICY_DIR; POLICY_DIR_ABS.mkdir(parents=True,exist_ok=True)
    if not (root/INHERIT).exists(): dump_yaml(root/INHERIT, {'schema_version':SCHEMA,'inherit':False,'parents':[],'local':{}})
    if not (root/EFFECTIVE).exists(): dump_yaml(root/EFFECTIVE, {'schema_version':SCHEMA,'status':'UNRESOLVED','effective':{}})

def normalize(doc: dict[str,Any])->dict[str,Any]:
    local=doc.get('local') or {}
    actions=local.get('allowed_actions')
    if actions is None: actions=sorted(ALL_ACTIONS)
    return {
      'allowed_actions': sorted(set(actions)&ALL_ACTIONS),
      'denied_actions': sorted(set(local.get('denied_actions',[]) or [] )&ALL_ACTIONS),
      'max_risk': str(local.get('max_risk','CRITICAL')).upper(),
      'min_evidence': str(local.get('min_evidence','E0')).upper(),
      'domains': sorted(set(local.get('domains',[]) or [])),
      'require_signed_handoff': bool(local.get('require_signed_handoff',True)),
      'require_signed_state': bool(local.get('require_signed_state',True)),
      'require_approval': bool(local.get('require_approval',False)),
    }

def intersect(parent, child):
    actions=sorted(set(parent['allowed_actions']) & set(child['allowed_actions']))
    denies=sorted(set(parent['denied_actions']) | set(child['denied_actions']))
    # A deny always wins over an allow.
    actions=[a for a in actions if a not in denies]
    risk=min(RISK[parent['max_risk']], RISK[child['max_risk']])
    risk_name=next(k for k,v in RISK.items() if v==risk)
    evidence=max(int(parent['min_evidence'].lstrip('E') or 0), int(child['min_evidence'].lstrip('E') or 0))
    domains=sorted(set(parent['domains']) & set(child['domains'])) if parent['domains'] and child['domains'] else sorted(set(parent['domains'])|set(child['domains']))
    return {'allowed_actions':actions,'denied_actions':denies,'max_risk':risk_name,'min_evidence':f'E{evidence}','domains':domains,
            'require_signed_handoff':parent['require_signed_handoff'] or child['require_signed_handoff'],
            'require_signed_state':parent['require_signed_state'] or child['require_signed_state'],
            'require_approval':parent['require_approval'] or child['require_approval']}

def resolve(root: Path, stack=None, write: bool = True):
    ensure(root); stack=stack or []
    doc=load_yaml(root/INHERIT,{})
    if str(doc.get('schema_version'))!=SCHEMA: return {'status':'FAIL','reason':'SCHEMA_MISMATCH'}
    current_id=str(doc.get('project_id') or root.name)
    if current_id in stack: return {'status':'FAIL','reason':'POLICY_INHERITANCE_CYCLE','cycle':stack+[current_id]}
    eff=normalize(doc)
    provenance=[]
    if bool(doc.get('inherit',False)):
        for parent in doc.get('parents',[]) or []:
            if not isinstance(parent,dict): return {'status':'FAIL','reason':'INVALID_PARENT'}
            path=Path(parent.get('path',''))
            if not path.is_absolute(): path=(root/path).resolve()
            parent_root=path if path.is_dir() else path.parent
            if not (parent_root/INHERIT).exists(): return {'status':'FAIL','reason':'PARENT_POLICY_NOT_FOUND','parent':str(path)}
            r=resolve(parent_root, stack+[current_id], write=write)
            if r.get('status')!='PASS': return r
            eff=intersect(r['effective'], eff)
            provenance.extend(r.get('provenance',[])); provenance.append(str(path))
    deny=set(eff['denied_actions']); eff['allowed_actions']=[a for a in eff['allowed_actions'] if a not in deny]
    result={'status':'PASS','schema_version':SCHEMA,'effective':eff,'provenance':provenance,'resolved_at':now(),'effective_hash':fp(eff)}
    if write:
        dump_yaml(root/EFFECTIVE,result)
    return result

def check(root: Path):
    r=resolve(root, write=False)
    if r.get('status')!='PASS': return r
    eff=r['effective']
    if eff['max_risk'] not in RISK: return {'status':'FAIL','reason':'INVALID_MAX_RISK'}
    if any(a not in ALL_ACTIONS for a in eff['allowed_actions']): return {'status':'FAIL','reason':'INVALID_ACTION'}
    return {'status':'PASS','reason':'POLICY_EFFECTIVE','effective_hash':r['effective_hash'],'provenance':r['provenance'],'effective':eff}

def sign_effective(root, private_path, key_id, out):
    result=check(root)
    if result.get('status')!='PASS': return result
    env=sign({'schema_version':SCHEMA,'effective':result['effective'],'effective_hash':result['effective_hash']},private_path,key_id,'federation-policy-effective')
    Path(out).write_text(json.dumps(env,indent=2)+'\n',encoding='utf-8')
    return {'status':'PASS','file':str(out),'effective_hash':result['effective_hash']}

def main():
    p=argparse.ArgumentParser(description='UAAF v2.2 federation policy')
    s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('resolve');q.add_argument('path',nargs='?',default='.')
    q=s.add_parser('check');q.add_argument('path',nargs='?',default='.')
    q=s.add_parser('sign');q.add_argument('path',nargs='?',default='.');q.add_argument('--private-key',required=True);q.add_argument('--key-id',required=True);q.add_argument('--out',required=True)
    a=p.parse_args(); root=Path(getattr(a,'path','.')).resolve()
    if a.cmd=='resolve': r=resolve(root)
    elif a.cmd=='check': r=check(root)
    else: r=sign_effective(root,Path(a.private_key),a.key_id,Path(a.out).resolve())
    print(json.dumps(r,indent=2,ensure_ascii=False)); raise SystemExit(0 if r.get('status')=='PASS' else 1)
if __name__=='__main__': main()
