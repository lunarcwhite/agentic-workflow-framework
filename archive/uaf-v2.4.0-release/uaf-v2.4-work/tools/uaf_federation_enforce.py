#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import yaml
SCHEMA='2.3'; ROOT=Path('.ai/federation/negotiation'); RISK={'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}; EVIDENCE={f'E{i}':i for i in range(6)}
def load(p,d=None):
    try:v=yaml.safe_load(p.read_text(encoding='utf-8')) or {};return v if isinstance(v,dict) else (d or {})
    except Exception:return d or {}
def contract(root):
    c=load(root/ROOT/'CAPABILITY-CONTRACT.yaml',{});
    if str(c.get('schema_version'))!=SCHEMA:return None,'CONTRACT_SCHEMA_MISMATCH'
    st=str(c.get('status','')).upper()
    if st=='REVIEW_REQUIRED':return None,'CONTRACT_APPROVAL_REQUIRED'
    if st!='NEGOTIATED':return None,'CONTRACT_NOT_ACTIVE'
    return c.get('contract') or {},None
def enforce(root,action,risk,domain,evidence,approved,signed):
    c,e=contract(root)
    if e:return {'status':'DENIED','reason':e}
    if action not in set(c.get('allowed_actions',[])):return {'status':'DENIED','reason':'ACTION_NOT_NEGOTIATED'}
    if action in set(c.get('denied_actions',[])):return {'status':'DENIED','reason':'ACTION_DENIED'}
    if RISK.get(risk.upper(),99)>RISK.get(str(c.get('max_risk','LOW')).upper(),0):return {'status':'DENIED','reason':'RISK_EXCEEDS_CONTRACT_CEILING'}
    if EVIDENCE.get(evidence.upper(),99)<EVIDENCE.get(str(c.get('min_evidence','E0')).upper(),99):return {'status':'DENIED','reason':'EVIDENCE_BELOW_CONTRACT_FLOOR'}
    scope=str(c.get('domain_scope','SET' if c.get('domains') else 'ALL')).upper(); domains=set(c.get('domains',[]))
    if scope=='NONE':return {'status':'DENIED','reason':'NO_DOMAIN_COMMON_DENOMINATOR'}
    if scope=='SET' and domain not in domains:return {'status':'DENIED','reason':'DOMAIN_NOT_NEGOTIATED'}
    if action=='handoff' and c.get('require_signed_handoff',True) and not signed:return {'status':'DENIED','reason':'SIGNED_HANDOFF_REQUIRED'}
    if action in {'state-pull','state-push'} and c.get('require_signed_state',True) and not signed:return {'status':'DENIED','reason':'SIGNED_STATE_REQUIRED'}
    if c.get('require_approval',False) and not approved:return {'status':'REVIEW_REQUIRED','reason':'APPROVAL_REQUIRED'}
    return {'status':'AUTHORIZED','reason':'NEGOTIATED_CONTRACT_SATISFIED','contract_hash':c.get('contract_hash')}
def check(root):
    p=load(root/ROOT/'ENFORCEMENT-POLICY.yaml',{});return {'status':'PASS' if p.get('default_deny') is True and p.get('fail_closed') is True else 'FAIL','default_deny':True,'fail_closed':True}
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('enforce');q.add_argument('path');q.add_argument('--action',required=True);q.add_argument('--risk',required=True);q.add_argument('--domain',default='*');q.add_argument('--evidence',default='E0');q.add_argument('--approved',action='store_true');q.add_argument('--signed',action='store_true')
    q=s.add_parser('check');q.add_argument('path',nargs='?',default='.')
    a=p.parse_args();root=Path(a.path).resolve();r=enforce(root,a.action,a.risk,a.domain,a.evidence,a.approved,a.signed) if a.cmd=='enforce' else check(root)
    print(json.dumps(r,indent=2,ensure_ascii=False));raise SystemExit(0 if r.get('status') in {'PASS','AUTHORIZED','REVIEW_REQUIRED'} else 1)
if __name__=='__main__':main()
