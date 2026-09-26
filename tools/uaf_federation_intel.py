#!/usr/bin/env python3
"""UAAF v2.2 federation conflict intelligence, sync planning, checkpoint selection, recovery advice."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
import yaml

SCHEMA='2.2'; FED=Path('.ai/federation'); OPS=FED/'ops'; INTEL=FED/'intelligence'
RISK={'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}

def load(path, default=None):
    if not path.exists(): return dict(default or {})
    try:
        v=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return v if isinstance(v,dict) else dict(default or {})
    except Exception:return dict(default or {})

def dump(path,data): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8')

def fp(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def vector_cmp(a,b):
    keys=set(a)|set(b); a_le=b_le=True; equal=True
    for k in keys:
        av=int(a.get(k,0) or 0); bv=int(b.get(k,0) or 0)
        if av>bv:a_le=False
        if av<bv:b_le=False
        if av!=bv:equal=False
    if equal:return 'IDENTICAL'
    if b_le:return 'DOMINATED_BY_REMOTE'
    if a_le:return 'DOMINATED_BY_LOCAL'
    return 'CONCURRENT'

def classify_conflict(c):
    key=str(c.get('key','')); local=c.get('local_value'); remote=c.get('remote_value')
    kind=str(c.get('kind','')).upper()
    path=key.lower()
    if local==remote:return {'class':'BYTE_IDENTICAL','impact':'NONE','action':'AUTO_CONVERGE'}
    if kind in {'POLICY','AUTHORITY'} or any(x in path for x in ('policy','permission','authority','delegation','trust')):
        return {'class':'POLICY_AUTHORITY','impact':'CRITICAL','action':'HUMAN_REVIEW_REQUIRED'}
    if any(x in path for x in ('security','revocation','key','secret','credential')):
        return {'class':'SECURITY','impact':'CRITICAL','action':'HUMAN_REVIEW_REQUIRED'}
    if kind=='VECTOR_DOMINANT':return {'class':'CAUSALLY_DOMINATED','impact':'LOW','action':'AUTO_CONVERGE'}
    if isinstance(local,(dict,list)) or isinstance(remote,(dict,list)):
        return {'class':'STRUCTURAL_SEMANTIC','impact':'HIGH','action':'ADVISORY_RESOLUTION'}
    return {'class':'SEMANTIC_VALUE','impact':'MEDIUM','action':'ADVISORY_RESOLUTION'}

def analyze_conflicts(root):
    conflicts=load(root/(OPS/'CONFLICTS.yaml'),{}).get('conflicts',[]) or []
    out=[]
    for c in conflicts:
        if not isinstance(c,dict):continue
        item={'conflict_id':c.get('conflict_id'),'status':c.get('status','UNRESOLVED'),'key':c.get('key'),'classification':classify_conflict(c)}
        item['fingerprint']=fp({'conflict_id':item['conflict_id'],'key':item['key'],'classification':item['classification']})
        out.append(item)
    result={'schema_version':SCHEMA,'generated_by':'uaf_federation_intel','status':'PASS','conflicts':out,'unresolved':sum(x['status'] in {'UNRESOLVED','PROPOSED','APPROVED'} for x in out)}
    dump(root/(INTEL/'CONFLICT-ANALYSIS.yaml'),result); return result

def sync_plan(root, peer_id, remote_file=None):
    curs=load(root/(OPS/'CURSORS.yaml'),{}).get('peers',{}) or {}; local=curs.get(peer_id,{})
    remote={}
    if remote_file: remote=load(Path(remote_file),{})
    remote_cursor=int(remote.get('cursor',remote.get('sequence',0)) or 0)
    local_cursor=int(local.get('cursor',0) or 0)
    source_vector=remote.get('vector_clock') or remote.get('clock') or {}
    local_vec=load(root/(FED/'state/VECTOR.yaml'),{}).get('clock',{}) or {}
    causal=vector_cmp(local_vec,source_vector) if source_vector else 'UNKNOWN'
    action='NOOP'
    if causal=='CONCURRENT': action='RECONCILE_CAUSALITY'
    elif remote_cursor>local_cursor: action='PULL_REMOTE_DELTAS'
    elif remote_cursor<local_cursor: action='REMOTE_BEHIND'
    result={'schema_version':SCHEMA,'status':'PASS','peer_id':peer_id,'local_cursor':local_cursor,'remote_cursor':remote_cursor,'causality':causal,'recommended_action':action,'advisory_only':True}
    dump(root/(INTEL/f'SYNC-PLAN-{peer_id}.yaml'),result); return result

def checkpoint_select(root):
    items=load(root/(OPS/'CHECKPOINTS.yaml'),{}).get('checkpoints',[]) or []
    current_rev=int(load(root/(OPS/'REVOCATIONS.yaml'),{}).get('revocation_epoch',0) or 0)
    local_vec=load(root/(FED/'state/VECTOR.yaml'),{}).get('clock',{}) or {}
    candidates=[]
    for c in items:
        if not isinstance(c,dict):continue
        vec=c.get('vector',c.get('clock',{})) or {}
        relation=vector_cmp(local_vec,vec) if vec else 'UNKNOWN'
        rev=int(c.get('revocation_epoch',0) or 0)
        candidates.append({'checkpoint_id':c.get('checkpoint_id'),'created_at':c.get('created_at'),'revocation_epoch':rev,'causality':relation,'eligible':rev>=current_rev})
    eligible=[x for x in candidates if x['eligible']]
    # Deterministic selection: newest timestamp, then highest epoch, without a trust-score.
    eligible.sort(key=lambda x:(str(x.get('created_at') or ''),x['revocation_epoch']),reverse=True)
    chosen=eligible[0] if eligible else None
    result={'schema_version':SCHEMA,'status':'PASS','current_revocation_epoch':current_rev,'candidates':candidates,'selected':chosen,'advisory_only':True}
    dump(root/(INTEL/'CHECKPOINT-SELECTION.yaml'),result); return result

def check(root):
    issues=[]
    required=[INTEL/'CONFLICT-ANALYSIS.yaml', INTEL/'CHECKPOINT-SELECTION.yaml', INTEL/'RECOVERY-RECOMMENDATION.yaml']
    for path in required:
        if path.exists():
            doc = load(root / path, {})
            if str(doc.get('schema_version')) != SCHEMA:
                issues.append(f'SCHEMA_MISMATCH:{path.relative_to(root)}')
    return {'status': 'PASS' if not issues else 'FAIL', 'issues': issues, 'advisory_only': True}

def recovery_recommend(root):
    status=load(root/(OPS/'MODE.yaml'),{}).get('mode','ONLINE')
    conflicts=load(root/(OPS/'CONFLICTS.yaml'),{}).get('conflicts',[]) or []
    rev=int(load(root/(OPS/'REVOCATIONS.yaml'),{}).get('revocation_epoch',0) or 0)
    unresolved=[c for c in conflicts if isinstance(c,dict) and str(c.get('status','UNRESOLVED')) in {'UNRESOLVED','PROPOSED','APPROVED'}]
    blockers=[]
    if status!='RECOVERING': blockers.append('RECOVERY_MODE_NOT_ACTIVE')
    if unresolved: blockers.append('UNRESOLVED_CONFLICTS_PRESERVED')
    result={'schema_version':SCHEMA,'status':'REVIEW_REQUIRED' if blockers else 'PASS','mode':status,'revocation_epoch':rev,'unresolved_conflicts':len(unresolved),'blockers':blockers,
            'recommendation':'VERIFY_CHECKPOINT_THEN_RECOVER' if not blockers else 'DO_NOT_APPLY_AUTOMATICALLY','advisory_only':True}
    dump(root/(INTEL/'RECOVERY-RECOMMENDATION.yaml'),result); return result

def main():
    p=argparse.ArgumentParser(description='UAAF v2.2 federation intelligence'); s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('conflicts');q.add_argument('action',choices=['analyze']);q.add_argument('path',nargs='?',default='.')
    q=s.add_parser('sync');q.add_argument('action',choices=['plan']);q.add_argument('path',nargs='?',default='.');q.add_argument('--peer-id',required=True);q.add_argument('--remote-file')
    q=s.add_parser('checkpoint');q.add_argument('action',choices=['select']);q.add_argument('path',nargs='?',default='.')
    q=s.add_parser('recovery');q.add_argument('action',choices=['recommend']);q.add_argument('path',nargs='?',default='.')
    q=s.add_parser('check');q.add_argument('path',nargs='?',default='.')
    a=p.parse_args(); root=Path(a.path).resolve()
    if a.cmd=='conflicts':r=analyze_conflicts(root)
    elif a.cmd=='sync':r=sync_plan(root,a.peer_id,a.remote_file)
    elif a.cmd=='checkpoint':r=checkpoint_select(root)
    elif a.cmd=='check':r=check(root)
    else:r=recovery_recommend(root)
    print(json.dumps(r,indent=2,ensure_ascii=False)); raise SystemExit(0 if r.get('status') in {'PASS','REVIEW_REQUIRED'} else 1)
if __name__=='__main__':main()
