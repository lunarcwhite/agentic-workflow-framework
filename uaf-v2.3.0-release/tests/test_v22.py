from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
CLI=[sys.executable,str(TOOLS/'uaf.py')]

def run(*args, check=True):
    p=subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=15)
    if check and p.returncode!=0:
        raise AssertionError(f'cmd failed: {args}\nstdout={p.stdout}\nstderr={p.stderr}')
    return p

def init(path, ext='v2.2'):
    run('init',path,'--profile','full','--auto-detect','--extension',ext,'--docs','auto')

def test_policy_inheritance_monotonic(tmp_path):
    parent=tmp_path/'parent'; child=tmp_path/'child'; init(parent); init(child)
    pp=parent/'.ai/federation/policy/INHERITANCE.yaml'
    cp=child/'.ai/federation/policy/INHERITANCE.yaml'
    pp.write_text("""schema_version: '2.2'\nproject_id: PARENT\ninherit: false\nparents: []\nlocal:\n  allowed_actions: [handoff, state-push]\n  denied_actions: [state-push]\n  max_risk: MEDIUM\n  min_evidence: E3\n  domains: [backend]\n  require_signed_handoff: true\n  require_signed_state: true\n  require_approval: true\n""")
    cp.write_text("""schema_version: '2.2'\nproject_id: CHILD\ninherit: true\nparents:\n  - path: ../parent\nlocal:\n  allowed_actions: [handoff, state-push, policy-sync]\n  denied_actions: []\n  max_risk: CRITICAL\n  min_evidence: E1\n  domains: [backend, frontend]\n  require_signed_handoff: false\n  require_signed_state: true\n  require_approval: false\n""")
    p=subprocess.run([*CLI,'federation-policy','resolve',child],capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stdout+p.stderr
    d=json.loads(p.stdout)['effective']
    assert d['allowed_actions']==['handoff']
    assert d['max_risk']=='MEDIUM'
    assert d['min_evidence']=='E3'
    assert d['domains']==['backend']
    assert d['require_signed_handoff'] is True and d['require_approval'] is True

def test_policy_cycle_fails_closed(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; init(a); init(b)
    for root, other, pid in [(a,b,'A'),(b,a,'B')]:
        (root/'.ai/federation/policy/INHERITANCE.yaml').write_text(f"schema_version: '2.2'\nproject_id: {pid}\ninherit: true\nparents:\n  - path: ../{other.name}\nlocal: {{allowed_actions: [handoff], max_risk: LOW, min_evidence: E0, domains: []}}\n")
    p=subprocess.run([*CLI,'federation-policy','resolve',a],capture_output=True,text=True,timeout=15)
    assert p.returncode!=0
    assert 'POLICY_INHERITANCE_CYCLE' in p.stdout

def test_conflict_intelligence_is_advisory(tmp_path):
    root=tmp_path/'p'; init(root)
    conf=root/'.ai/federation/ops/CONFLICTS.yaml'
    conf.write_text("""schema_version: '2.1'\nconflicts:\n  - conflict_id: C1\n    key: delegation.policy\n    local_value: A\n    remote_value: B\n    status: UNRESOLVED\n  - conflict_id: C2\n    key: label\n    local_value: same\n    remote_value: same\n    status: UNRESOLVED\n""")
    run('federation-intel','conflicts','analyze',root)
    d=yaml.safe_load((root/'.ai/federation/intelligence/CONFLICT-ANALYSIS.yaml').read_text())
    x={c['conflict_id']:c for c in d['conflicts']}
    assert x['C1']['classification']['action']=='HUMAN_REVIEW_REQUIRED'
    assert x['C2']['classification']['action']=='AUTO_CONVERGE'
    assert all(c['classification']['action']!='AUTO_RESOLVE' for c in d['conflicts'])

def test_sync_plan_concurrent(tmp_path):
    root=tmp_path/'p'; init(root)
    vec=root/'.ai/federation/state/VECTOR.yaml'
    vec.write_text("schema_version: '2.0'\nclock:\n  A: 2\n")
    curs=root/'.ai/federation/ops/CURSORS.yaml'; curs.write_text("schema_version: '2.1'\npeers:\n  PEER: {cursor: 1}\n")
    remote=tmp_path/'remote.yaml'; remote.write_text("cursor: 5\nvector_clock:\n  A: 1\n  B: 1\n")
    p=subprocess.run([*CLI,'federation-intel','sync','plan',root,'--peer-id','PEER','--remote-file',remote],capture_output=True,text=True,timeout=15)
    assert p.returncode==0
    d=json.loads(p.stdout)
    assert d['causality']=='CONCURRENT'
    assert d['recommended_action']=='RECONCILE_CAUSALITY'
    assert d['advisory_only'] is True

def test_checkpoint_selection_and_recovery_advice(tmp_path):
    root=tmp_path/'p'; init(root)
    (root/'.ai/federation/ops/REVOCATIONS.yaml').write_text("schema_version: '2.1'\nrevocation_epoch: 3\nentries: []\n")
    (root/'.ai/federation/ops/CHECKPOINTS.yaml').write_text("""schema_version: '2.1'\ncheckpoints:\n  - checkpoint_id: OLD\n    created_at: '2026-09-20T00:00:00Z'\n    revocation_epoch: 2\n  - checkpoint_id: NEW\n    created_at: '2026-09-21T00:00:00Z'\n    revocation_epoch: 3\n""")
    run('federation-intel','checkpoint','select',root)
    d=yaml.safe_load((root/'.ai/federation/intelligence/CHECKPOINT-SELECTION.yaml').read_text())
    assert d['selected']['checkpoint_id']=='NEW'
    run('federation-intel','recovery','recommend',root)
    r=yaml.safe_load((root/'.ai/federation/intelligence/RECOVERY-RECOMMENDATION.yaml').read_text())
    assert r['status']=='REVIEW_REQUIRED'
    assert r['recommendation']=='DO_NOT_APPLY_AUTOMATICALLY'

def test_v22_conformance_non_strict(tmp_path):
    root=tmp_path/'p'; init(root)
    p=subprocess.run([*CLI,'check',root,'--level','full'],capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stdout+p.stderr
    assert 'extensions=2.2' in p.stdout

def test_v21_downgrade_does_not_leave_v22_namespace(tmp_path):
    root=tmp_path/'p'; init(root)
    assert (root/'.ai/federation/policy').exists()
    # Explicit reinitialization to v2.1 must not leave v2.2 policy/intelligence.
    p=subprocess.run([*CLI,'init',root,'--profile','full','--auto-detect','--extension','v2.1','--docs','auto','--force'],capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stdout+p.stderr
    assert not (root/'.ai/federation/policy').exists()
    assert not (root/'.ai/federation/intelligence').exists()
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert str((m.get('extensions') or {}).get('version'))=='2.1'
