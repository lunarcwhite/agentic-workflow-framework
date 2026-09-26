from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/'tools/uaf.py')]

def init(root:Path, ext='v2.3'):
    p=subprocess.run([*CLI,'init',str(root),'--profile','full','--extension',ext,'--name',root.name,'--type','fullstack'],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stdout+p.stderr

def run(*args,timeout=20):
    p=subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=timeout)
    return p

def write_effective(root:Path, *, actions, risk, evidence, domains, signed_handoff=True, signed_state=True, approval=False):
    d={'schema_version':'2.2','status':'PASS','effective':{'allowed_actions':actions,'denied_actions':[],'max_risk':risk,'min_evidence':evidence,'domains':domains,'require_signed_handoff':signed_handoff,'require_signed_state':signed_state,'require_approval':approval}}
    p=root/'.ai/federation/policy/EFFECTIVE.yaml';p.write_text(yaml.safe_dump(d,sort_keys=False),encoding='utf-8')

def test_v23_initializer_and_manifest(tmp_path):
    root=tmp_path/'p';init(root)
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert m['framework']['version']=='2.3.0'
    assert m['protocols']['federation_policy']=='UAAF-FED-2.3'
    assert m['extensions']['version']=='2.3'
    assert (root/'.ai/federation/negotiation/CAPABILITY-CONTRACT.yaml').exists()
    assert (root/'.ai/federation/negotiation/ENFORCEMENT-POLICY.yaml').exists()

def test_restrictive_intersection(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff','state-pull'],risk='MEDIUM',evidence='E2',domains=['backend','frontend'])
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-1','peer_id':'peer-b','policy':{'allowed_actions':['handoff','state-pull','policy-sync'],'denied_actions':['policy-sync'],'max_risk':'HIGH','min_evidence':'E3','domains':['backend'],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    p=run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote));assert p.returncode==0,p.stdout+p.stderr
    d=json.loads(p.stdout)
    assert d['status']=='NEGOTIATED'
    c=d['negotiated_policy']
    assert c['allowed_actions']==['handoff','state-pull']
    assert c['max_risk']=='MEDIUM';assert c['min_evidence']=='E3';assert c['domains']==['backend']

def test_deny_first_remote_denial(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff','state-pull'],risk='HIGH',evidence='E1',domains=[])
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-2','peer_id':'peer-b','policy':{'allowed_actions':['handoff'],'denied_actions':['handoff'],'max_risk':'HIGH','min_evidence':'E1','domains':[],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    p=run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote));assert p.returncode!=0
    assert 'DENIED' in p.stdout or 'allowed' in p.stdout.lower()

def test_approval_is_monotonic(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff'],risk='MEDIUM',evidence='E2',domains=['backend'],approval=True)
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-3','peer_id':'peer-b','policy':{'allowed_actions':['handoff'],'denied_actions':[],'max_risk':'MEDIUM','min_evidence':'E2','domains':['backend'],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    p=run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote));assert p.returncode==0
    assert json.loads(p.stdout)['status']=='REVIEW_REQUIRED'

def test_enforcement_authorized_after_negotiation(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff'],risk='MEDIUM',evidence='E3',domains=['backend'],approval=False)
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-4','peer_id':'peer-b','policy':{'allowed_actions':['handoff'],'denied_actions':[],'max_risk':'HIGH','min_evidence':'E2','domains':['backend'],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    assert run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote)).returncode==0
    p=run('federation-enforce','enforce',str(root),'--action','handoff','--risk','MEDIUM','--domain','backend','--evidence','E3','--signed')
    assert p.returncode==0;assert json.loads(p.stdout)['status']=='AUTHORIZED'

def test_enforcement_denies_risk_escalation(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff'],risk='MEDIUM',evidence='E2',domains=['backend'])
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-5','peer_id':'peer-b','policy':{'allowed_actions':['handoff'],'denied_actions':[],'max_risk':'HIGH','min_evidence':'E2','domains':['backend'],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    assert run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote)).returncode==0
    p=run('federation-enforce','enforce',str(root),'--action','handoff','--risk','HIGH','--domain','backend','--evidence','E3','--signed')
    assert p.returncode!=0;assert 'RISK_EXCEEDS' in p.stdout

def test_enforcement_requires_signature_and_evidence(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff'],risk='HIGH',evidence='E3',domains=['backend'])
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-6','peer_id':'peer-b','policy':{'allowed_actions':['handoff'],'denied_actions':[],'max_risk':'HIGH','min_evidence':'E3','domains':['backend'],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    assert run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote)).returncode==0
    p=run('federation-enforce','enforce',str(root),'--action','handoff','--risk','HIGH','--domain','backend','--evidence','E2')
    assert p.returncode!=0;assert 'EVIDENCE_BELOW' in p.stdout
    p=run('federation-enforce','enforce',str(root),'--action','handoff','--risk','HIGH','--domain','backend','--evidence','E3')
    assert p.returncode!=0;assert 'SIGNED_HANDOFF' in p.stdout

def test_domains_never_expand(tmp_path):
    root=tmp_path/'p';init(root)
    write_effective(root,actions=['handoff'],risk='MEDIUM',evidence='E1',domains=['backend'])
    remote=tmp_path/'remote.yaml';remote.write_text(yaml.safe_dump({'schema_version':'2.3','offer_id':'OFF-7','peer_id':'peer-b','policy':{'allowed_actions':['handoff'],'denied_actions':[],'max_risk':'MEDIUM','min_evidence':'E1','domains':['frontend'],'require_signed_handoff':True,'require_signed_state':True,'require_approval':False}}),encoding='utf-8')
    p=run('federation-negotiation','negotiate',str(root),'--remote-file',str(remote));assert p.returncode!=0
    assert json.loads(p.stdout)['status']=='DENIED'

def test_v23_conformance_and_doctor(tmp_path):
    root=tmp_path/'p';init(root)
    p=run('check',str(root),'--level','full');assert p.returncode==0,p.stdout+p.stderr
    assert 'extensions=2.3' in p.stdout
    p=run('doctor',str(root),'--json');assert p.returncode==0,p.stdout+p.stderr
    d=json.loads(p.stdout);assert d['status']=='PASS'
    assert d['checks']['federation_negotiation']['returncode']==0
    assert d['checks']['federation_enforcement']['returncode']==0

def test_v22_downgrade_removes_v23_namespace(tmp_path):
    root=tmp_path/'p';init(root,'v2.3')
    p=run('init',str(root),'--profile','full','--extension','v2.2','--force','--docs','auto');assert p.returncode==0,p.stdout+p.stderr
    assert not (root/'.ai/federation/negotiation').exists()
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text());assert str(m['extensions']['version'])=='2.2'
