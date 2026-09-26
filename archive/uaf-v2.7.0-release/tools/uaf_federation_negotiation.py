#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, json
from pathlib import Path
from typing import Any
import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA='2.3'; FED=Path('.ai/federation'); POLICY=FED/'policy'; NEG=FED/'negotiation'
CONTRACT=NEG/'CAPABILITY-CONTRACT.yaml'; NEGOTIATION=NEG/'NEGOTIATION.yaml'
RISK={'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}; EVIDENCE={f'E{i}':i for i in range(6)}
ACTIONS={'handoff','state-pull','state-push','capability-sync','policy-sync'}

def load_yaml(path:Path,default=None):
    if not path.exists(): return dict(default or {})
    try:
        v=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return v if isinstance(v,dict) else dict(default or {})
    except Exception:return dict(default or {})

def dump_yaml(path:Path,data:dict[str,Any]):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8')

def canon(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def fp(v:Any)->str:return hashlib.sha256(canon(v)).hexdigest()

def normalize_policy(doc:dict[str,Any]):
    local=doc.get('local',doc); acts=local.get('allowed_actions'); acts=sorted(ACTIONS) if acts is None else acts
    return {'allowed_actions':sorted(set(acts)&ACTIONS),'denied_actions':sorted(set(local.get('denied_actions',[]) or [])&ACTIONS),
            'max_risk':str(local.get('max_risk','CRITICAL')).upper(),'min_evidence':str(local.get('min_evidence','E0')).upper(),
            'domains':sorted(set(local.get('domains',[]) or [])),'domain_scope':str(local.get('domain_scope','SET' if local.get('domains') else 'ALL')).upper(),'require_signed_handoff':bool(local.get('require_signed_handoff',True)),
            'require_signed_state':bool(local.get('require_signed_state',True)),'require_approval':bool(local.get('require_approval',False))}

def local_effective(root:Path):
    d=load_yaml(root/POLICY/'EFFECTIVE.yaml',{})
    return normalize_policy(d.get('effective') or load_yaml(root/POLICY/'INHERITANCE.yaml',{}))

def restrict(a,b):
    denied=set(a['denied_actions'])|set(b['denied_actions']); actions=sorted((set(a['allowed_actions'])&set(b['allowed_actions']))-denied)
    risk=min((a['max_risk'],b['max_risk']),key=lambda x:RISK.get(x,99)); evidence=max(EVIDENCE.get(a['min_evidence'],99),EVIDENCE.get(b['min_evidence'],99))
    ad,bd=set(a['domains']),set(b['domains'])
    ascope=a.get('domain_scope','SET' if ad else 'ALL'); bscope=b.get('domain_scope','SET' if bd else 'ALL')
    if ascope=='NONE' or bscope=='NONE': domain_scope='NONE'; domains=[]
    elif ascope=='ALL' and bscope=='ALL': domain_scope='ALL'; domains=[]
    elif ascope=='ALL': domain_scope='SET'; domains=sorted(bd)
    elif bscope=='ALL': domain_scope='SET'; domains=sorted(ad)
    else:
        domains=sorted(ad&bd); domain_scope='SET' if domains else 'NONE'
    return {'allowed_actions':actions,'denied_actions':sorted(denied),'max_risk':risk,'min_evidence':f'E{evidence}','domains':domains,'domain_scope':domain_scope,
            'require_signed_handoff':a['require_signed_handoff'] or b['require_signed_handoff'],'require_signed_state':a['require_signed_state'] or b['require_signed_state'],'require_approval':a['require_approval'] or b['require_approval']}

def non_escalating(local,remote,n):
    if not set(n['allowed_actions']).issubset(local['allowed_actions']):return False,'ALLOWED_ACTION_ESCALATION_LOCAL'
    if not set(n['allowed_actions']).issubset(remote['allowed_actions']):return False,'ALLOWED_ACTION_ESCALATION_REMOTE'
    if RISK[n['max_risk']] > min(RISK[local['max_risk']],RISK[remote['max_risk']]):return False,'RISK_ESCALATION'
    if EVIDENCE[n['min_evidence']] < max(EVIDENCE[local['min_evidence']],EVIDENCE[remote['min_evidence']]):return False,'EVIDENCE_ESCALATION'
    for side,name in ((local,'LOCAL'),(remote,'REMOTE')):
        s_scope=side.get('domain_scope','SET' if side.get('domains') else 'ALL'); n_scope=n.get('domain_scope','SET' if n.get('domains') else 'ALL')
        if s_scope=='NONE' and n_scope!='NONE': return False,f'DOMAIN_ESCALATION_{name}'
        if s_scope=='SET':
            if n_scope=='ALL' or not set(n.get('domains',[])).issubset(set(side.get('domains',[]))):return False,f'DOMAIN_ESCALATION_{name}'
    for k in ('require_signed_handoff','require_signed_state','require_approval'):
        if n[k] != (local[k] or remote[k]):return False,f'REQUIREMENT_ESCALATION:{k}'
    return True,'OK'

def verify_offer_signature(root,offer,peer_id):
    sig=offer.get('signature') or {}; peer=str(peer_id or offer.get('peer_id','')); key=root/FED/'peers'/peer/'ROOT.pub.pem'
    if not sig:return False,'REMOTE_OFFER_UNSIGNED'
    if not key.exists():return False,'REMOTE_ROOT_NOT_PINNED'
    payload={k:v for k,v in offer.items() if k!='signature'}
    try:
        public=serialization.load_pem_public_key(key.read_bytes()); raw=public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        if sig.get('schema_version')!=SCHEMA:return False,'SIGNATURE_SCHEMA_MISMATCH'
        if sig.get('purpose')!='federation-policy-offer':return False,'PURPOSE_MISMATCH'
        if sig.get('payload_sha256')!=fp(payload):return False,'PAYLOAD_HASH_MISMATCH'
        Ed25519PublicKey.from_public_bytes(raw).verify(base64.b64decode(sig.get('signature_b64',''),validate=True),canon(payload))
    except (OSError,ValueError,InvalidSignature,TypeError,KeyError):return False,'SIGNATURE_INVALID'
    return True,'OK'

def offer(root,peer_id,out):
    p=local_effective(root); d={'schema_version':SCHEMA,'offer_id':f'OFF-{fp(p)[:12]}','peer_id':peer_id,'policy':p}
    dump_yaml(Path(out),d); return {'status':'PASS','file':str(out),'offer_id':d['offer_id']}

def negotiate(root,remote_file,peer_id,require_remote_signature):
    remote=load_yaml(Path(remote_file),{}); 
    if str(remote.get('schema_version'))!=SCHEMA:return {'status':'FAIL','reason':'REMOTE_OFFER_SCHEMA_MISMATCH'}
    if require_remote_signature:
        ok,reason=verify_offer_signature(root,remote,peer_id)
        if not ok:return {'status':'FAIL','reason':reason}
    local=local_effective(root); rp=normalize_policy(remote.get('policy') or {}); np=restrict(local,rp); ok,reason=non_escalating(local,rp,np)
    if not ok:return {'status':'FAIL','reason':reason}
    status='DENIED' if (not np['allowed_actions'] or np.get('domain_scope')=='NONE') else ('REVIEW_REQUIRED' if np['require_approval'] else 'NEGOTIATED')
    result={'schema_version':SCHEMA,'status':status,'peer_id':peer_id or remote.get('peer_id'),'offer_id':remote.get('offer_id'),'local_policy':local,'remote_policy':rp,'negotiated_policy':np,'negotiated_hash':fp(np)}
    dump_yaml(root/NEGOTIATION,result); dump_yaml(root/CONTRACT,{'schema_version':SCHEMA,'status':status,'peer_id':result['peer_id'],'contract_hash':fp(np),'contract':np,'source_negotiation':str((root/NEGOTIATION).relative_to(root))})
    return result

def check(root):
    issues=[]; c=load_yaml(root/CONTRACT,{})
    if c and str(c.get('schema_version'))!=SCHEMA:issues.append('CONTRACT_SCHEMA_MISMATCH')
    if c:
        contract=c.get('contract') or {}
        if contract and contract.get('max_risk') not in RISK:issues.append('INVALID_MAX_RISK')
        if contract and contract.get('min_evidence') not in EVIDENCE:issues.append('INVALID_MIN_EVIDENCE')
        if contract and not set(contract.get('allowed_actions',[])).issubset(ACTIONS):issues.append('INVALID_ACTION')
    return {'status':'PASS' if not issues else 'FAIL','issues':issues,'deny_first':True}

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('offer');q.add_argument('path');q.add_argument('--peer-id',required=True);q.add_argument('--out',required=True)
    q=s.add_parser('negotiate');q.add_argument('path');q.add_argument('--remote-file',required=True);q.add_argument('--peer-id');q.add_argument('--require-remote-signature',action='store_true')
    q=s.add_parser('check');q.add_argument('path',nargs='?',default='.')
    a=p.parse_args();root=Path(getattr(a,'path','.')).resolve()
    r=offer(root,a.peer_id,a.out) if a.cmd=='offer' else negotiate(root,Path(a.remote_file).resolve(),a.peer_id,a.require_remote_signature) if a.cmd=='negotiate' else check(root)
    print(json.dumps(r,indent=2,ensure_ascii=False)); raise SystemExit(0 if r.get('status') in {'PASS','NEGOTIATED','REVIEW_REQUIRED'} else 1)
if __name__=='__main__':main()
