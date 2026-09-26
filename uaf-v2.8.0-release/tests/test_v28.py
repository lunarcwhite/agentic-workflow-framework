from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/'tools'/'uaf.py')]

def run(*args, timeout=10):
    return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=timeout)

def make_project(tmp_path):
    root=tmp_path/'p'
    p=run('init',root,'--profile','full','--extension','v2.8','--name','NorthstarV28','--type','fullstack')
    assert p.returncode==0,p.stdout+p.stderr
    return root

def test_initializer_creates_v28_custody(tmp_path):
    root=make_project(tmp_path)
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert m['framework']['version']=='2.8.0'
    assert m['extensions']['version']=='2.8'
    assert m['protocols']['federation_key_storage']=='UAAF-FED-2.8'
    assert (root/'.ai/federation/secure/KEY-PROVIDERS.yaml').exists()
    assert (root/'.ai/federation/secure/KEY-REFERENCES.yaml').exists()
    assert (root/'.ai/federation/secure/KEY-STORAGE-HEALTH.yaml').exists()

def test_storage_check_and_inventory_never_export_secret(tmp_path):
    root=make_project(tmp_path)
    p=run('key-storage','check',root,'--json')
    assert p.returncode==0,p.stdout+p.stderr
    out=json.loads(p.stdout)
    assert out['active_provider']=='filesystem'
    assert out['providers']['filesystem']['status']=='PASS'
    assert out['providers']['filesystem']['secrets_exported'] is False
    q=run('key-storage','inventory',root,'--json')
    assert q.returncode==0,q.stdout+q.stderr
    inv=json.loads(q.stdout)
    raw=q.stdout.lower()
    assert 'private key' not in raw and 'begin ed25519 private key' not in raw
    assert inv['secret_export']=='DISABLED'

def test_register_is_metadata_only(tmp_path):
    root=make_project(tmp_path)
    p=run('key-storage','register',root,'--key-id','K-001','--provider','filesystem','--purpose','federation-signing')
    assert p.returncode==0,p.stdout+p.stderr
    refs=yaml.safe_load((root/'.ai/federation/secure/KEY-REFERENCES.yaml').read_text())
    assert refs['references'][0]['key_id']=='K-001'
    assert refs['references'][0]['secret_export']=='DISABLED'
    assert len(list((root/'.ai/federation/secure/keys').glob('K-001*')))==0

def test_unavailable_provider_is_fail_closed(tmp_path):
    root=make_project(tmp_path)
    p=run('key-storage','set-active',root,'--provider','kms','--json')
    assert p.returncode==0 or p.returncode==1
    out=json.loads(p.stdout)
    assert out['status']=='NOT_CONFIGURED'
    cfg=yaml.safe_load((root/'.ai/federation/secure/KEY-PROVIDERS.yaml').read_text())
    assert cfg['active_provider']=='filesystem'

def test_external_adapter_health_can_be_enabled_without_key_export(tmp_path):
    root=make_project(tmp_path)
    adapter=tmp_path/'kms_adapter.py'
    adapter.write_text('#!/usr/bin/env python3\nimport sys\nraise SystemExit(0 if sys.argv[1:] == ["--healthcheck"] else 1)\n')
    adapter.chmod(0o755)
    cfgp=root/'.ai/federation/secure/KEY-PROVIDERS.yaml'
    cfg=yaml.safe_load(cfgp.read_text())
    cfg['providers']['kms']['enabled']=True
    cfg['providers']['kms']['adapter_command']=str(adapter)
    cfgp.write_text(yaml.safe_dump(cfg,sort_keys=False))
    p=run('key-storage','set-active',root,'--provider','kms','--json')
    assert p.returncode==0,p.stdout+p.stderr
    out=json.loads(p.stdout); assert out['active_provider']=='kms'
    health=yaml.safe_load((root/'.ai/federation/secure/KEY-STORAGE-HEALTH.yaml').read_text())
    assert health['active_provider']=='kms' and health['providers']['kms']['status']=='PASS'
    storage=yaml.safe_load((root/'.ai/federation/secure/KEY-STORAGE.yaml').read_text())
    assert storage['provider']=='kms' and storage['secret_export']=='DISABLED'

def test_disallowed_provider_does_not_fallback(tmp_path):
    root=make_project(tmp_path)
    cfgp=root/'.ai/federation/secure/KEY-PROVIDERS.yaml'
    cfg=yaml.safe_load(cfgp.read_text())
    cfg['providers']['hsm']['enabled']=True
    cfgp.write_text(yaml.safe_dump(cfg,sort_keys=False))
    p=run('key-storage','set-active',root,'--provider','hsm','--json')
    out=json.loads(p.stdout)
    assert out['status']=='NOT_CONFIGURED'
    assert yaml.safe_load(cfgp.read_text())['active_provider']=='filesystem'

def test_doctor_v28_mode(tmp_path):
    root=make_project(tmp_path)
    p=run('doctor',root,'--json')
    assert p.returncode==0,p.stdout+p.stderr
    out=json.loads(p.stdout)
    assert out['mode']=='compact-v2.8'
    assert out['status']=='PASS'

def test_strict_conformance_reports_only_expected_fresh_warnings(tmp_path):
    root=make_project(tmp_path)
    p=run('check',root,'--level','full','--strict')
    assert p.returncode==1
    assert 'CONF-V28-' not in p.stdout
    assert 'ERROR ' not in p.stdout
    assert 'WARNING ' in p.stdout

def test_explicit_downgrade_removes_v28_only(tmp_path):
    root=make_project(tmp_path)
    p=run('init',root,'--profile','full','--extension','v2.7','--force')
    assert p.returncode==0,p.stdout+p.stderr
    assert not (root/'.ai/federation/secure/KEY-PROVIDERS.yaml').exists()
    assert not (root/'.ai/federation/secure/KEY-REFERENCES.yaml').exists()
    assert (root/'.ai/federation/secure/KEY-STORAGE.yaml').exists()
    m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
    assert str(m['extensions']['version'])=='2.7'
