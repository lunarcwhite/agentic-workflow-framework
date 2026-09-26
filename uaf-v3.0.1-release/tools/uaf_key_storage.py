#!/usr/bin/env python3
"""UAAF v2.8 key custody/provider reference layer.

This layer separates key custody from lifecycle and transport semantics.
Reference providers:
- filesystem: local reference provider; private keys remain on disk and are never exported;
- os-keychain: optional Python keyring adapter; unavailable unless keyring is installed;
- kms/hsm: external signing providers; configuration/health only in this reference build.

No command prints private key material.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from typing import Any
import yaml

SCHEMA='2.8'
SECURE=Path('.ai/federation/secure')
CONFIG=SECURE/'KEY-PROVIDERS.yaml'
REFS=SECURE/'KEY-REFERENCES.yaml'
HEALTH=SECURE/'KEY-STORAGE-HEALTH.yaml'
STORAGE=SECURE/'KEY-STORAGE.yaml'
AUDIT=SECURE/'KEY-CUSTODY-AUDIT.jsonl'
SUPPORTED={'filesystem','os-keychain','kms','hsm'}


def load_yaml(path: Path, default: dict | None=None) -> dict:
    if not path.exists(): return dict(default or {})
    try:
        v=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return v if isinstance(v,dict) else dict(default or {})
    except Exception: return dict(default or {})


def dump_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding='utf-8')


def ensure(root: Path) -> None:
    d=root/SECURE; d.mkdir(parents=True,exist_ok=True)
    if not (root/CONFIG).exists():
        dump_yaml(root/CONFIG, {
            'schema_version':SCHEMA,
            'active_provider':'filesystem',
            'providers':{
                'filesystem':{'enabled':True,'mode':'reference_local','secret_export':'DISABLED'},
                'os-keychain':{'enabled':False,'mode':'optional_keyring','secret_export':'DISABLED'},
                'kms':{'enabled':False,'mode':'external_signing_adapter','secret_export':'DISABLED'},
                'hsm':{'enabled':False,'mode':'external_signing_adapter','secret_export':'DISABLED'},
            },
            'policy':{
                'secret_export':'DISABLED',
                'private_key_return':'DISABLED',
                'fail_closed_when_unavailable':True,
                'allow_filesystem_fallback':False,
            },
        })
    if not (root/REFS).exists(): dump_yaml(root/REFS, {'schema_version':SCHEMA,'references':[]})
    if not (root/HEALTH).exists(): dump_yaml(root/HEALTH, {'schema_version':SCHEMA,'status':'NOT_RUN','providers':{}})
    (root/AUDIT).touch(exist_ok=True)
    if not (root/STORAGE).exists():
        dump_yaml(root/STORAGE, {'schema_version':SCHEMA,'provider':'filesystem','mode':'provider_abstracted','secret_export':'DISABLED'})


def provider_health(name: str, cfg: dict) -> dict:
    if name not in SUPPORTED: return {'status':'FAIL','reason':'KEY_STORAGE_PROVIDER_UNKNOWN'}
    if name=='filesystem': return {'status':'PASS','mode':'reference_local','secrets_exported':False}
    if name=='os-keychain':
        try:
            import keyring  # type: ignore
            backend=keyring.get_keyring()
            return {'status':'PASS','mode':'os_keychain','backend':backend.__class__.__name__,'secrets_exported':False}
        except Exception as exc:
            return {'status':'NOT_CONFIGURED','reason':'KEYRING_UNAVAILABLE','detail':str(exc)[:160]}
    entry=(cfg.get('providers') or {}).get(name) or {}
    if not entry.get('enabled'):
        return {'status':'NOT_CONFIGURED','reason':'PROVIDER_DISABLED'}
    adapter=str(entry.get('adapter_command') or '').strip()
    if not adapter: return {'status':'NOT_CONFIGURED','reason':'ADAPTER_NOT_CONFIGURED'}
    exe=shutil.which(adapter.split()[0])
    if not exe: return {'status':'NOT_CONFIGURED','reason':'ADAPTER_NOT_FOUND'}
    try:
        proc=subprocess.run(adapter.split()+['--healthcheck'],capture_output=True,text=True,timeout=3,shell=False)
        if proc.returncode==0: return {'status':'PASS','mode':'external_signing_adapter','secrets_exported':False}
        return {'status':'FAIL','reason':'ADAPTER_HEALTHCHECK_FAILED'}
    except (OSError,subprocess.TimeoutExpired): return {'status':'NOT_CONFIGURED','reason':'ADAPTER_UNAVAILABLE'}


def check(root: Path) -> dict:
    ensure(root); cfg=load_yaml(root/CONFIG,{})
    active=str(cfg.get('active_provider') or '')
    policies=cfg.get('policy') or {}
    issues=[]
    if active not in SUPPORTED: issues.append('ACTIVE_PROVIDER_UNKNOWN')
    if policies.get('secret_export')!='DISABLED' or policies.get('private_key_return')!='DISABLED':
        issues.append('SECRET_EXPORT_POLICY_MUST_BE_DISABLED')
    statuses={name:provider_health(name,cfg) for name in sorted(SUPPORTED)}
    ah=statuses.get(active,{'status':'FAIL'})
    storage=load_yaml(root/STORAGE,{})
    if str(storage.get('provider'))!=active: issues.append('KEY_STORAGE_ACTIVE_PROVIDER_MISMATCH')
    if issues: status='FAIL'
    elif ah['status']=='PASS': status='PASS'
    elif ah['status']=='NOT_CONFIGURED' and policies.get('fail_closed_when_unavailable',True): status='NOT_CONFIGURED'
    else: status='FAIL'
    health={'schema_version':SCHEMA,'checked_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'status':status,'active_provider':active,'providers':statuses,'issues':issues}
    dump_yaml(root/HEALTH,health)
    return health


def inventory(root: Path) -> dict:
    ensure(root); refs=load_yaml(root/REFS,{})
    return {'status':'PASS','active_provider':load_yaml(root/CONFIG,{}).get('active_provider'),'references':refs.get('references',[]),'secret_export':'DISABLED'}


def set_active(root: Path, provider: str) -> dict:
    ensure(root)
    if provider not in SUPPORTED: return {'status':'DENIED','reason':'KEY_STORAGE_PROVIDER_UNKNOWN'}
    cfg=load_yaml(root/CONFIG,{})
    health=provider_health(provider,cfg)
    if health['status']!='PASS': return {'status':'NOT_CONFIGURED','reason':health.get('reason','PROVIDER_UNAVAILABLE'),'provider':provider}
    cfg['active_provider']=provider; dump_yaml(root/CONFIG,cfg)
    storage=load_yaml(root/STORAGE,{})
    storage['provider']=provider; storage['schema_version']=SCHEMA; storage['mode']='provider_abstracted'; storage['secret_export']='DISABLED'; dump_yaml(root/STORAGE,storage)
    # Refresh health after a provider switch so health and active state cannot drift.
    health=check(root)
    return {'status':'PASS','active_provider':provider,'health_status':health.get('status')}


def register_reference(root: Path, key_id: str, provider: str, purpose: str, public_fingerprint: str='') -> dict:
    ensure(root)
    if provider not in SUPPORTED: return {'status':'DENIED','reason':'KEY_STORAGE_PROVIDER_UNKNOWN'}
    refs=load_yaml(root/REFS,{})
    items=refs.setdefault('references',[])
    if any(str(x.get('key_id'))==key_id for x in items): return {'status':'PASS','idempotent':True,'key_id':key_id}
    items.append({'key_id':key_id,'provider':provider,'purpose':purpose,'public_fingerprint':public_fingerprint,'secret_export':'DISABLED'})
    dump_yaml(root/REFS,refs)
    return {'status':'PASS','key_id':key_id,'provider':provider,'secret_export':'DISABLED'}


def main():
    ap=argparse.ArgumentParser(description='UAAF v2.8 key storage/custody')
    ap.add_argument('--json', action='store_true', help='emit machine-readable JSON')
    sp=ap.add_subparsers(dest='cmd',required=True)
    for c in ['check','inventory']:
        q=sp.add_parser(c); q.add_argument('path',nargs='?',default='.'); q.add_argument('--json',action='store_true')
    q=sp.add_parser('set-active'); q.add_argument('path'); q.add_argument('--provider',required=True); q.add_argument('--json',action='store_true')
    q=sp.add_parser('register'); q.add_argument('path'); q.add_argument('--key-id',required=True); q.add_argument('--provider',required=True); q.add_argument('--purpose',required=True); q.add_argument('--public-fingerprint',default=''); q.add_argument('--json',action='store_true')
    a=ap.parse_args(); root=Path(a.path).resolve()
    if a.cmd=='check': r=check(root)
    elif a.cmd=='inventory': r=inventory(root)
    elif a.cmd=='set-active': r=set_active(root,a.provider)
    else: r=register_reference(root,a.key_id,a.provider,a.purpose,a.public_fingerprint)
    print(json.dumps(r,indent=2,ensure_ascii=False) if a.json else (r.get('status','') if r.get('status') else json.dumps(r)))
    ok_status = r.get('status') == 'PASS' or (r.get('status') == 'NOT_CONFIGURED' and a.cmd in {'check','inventory'})
    raise SystemExit(0 if ok_status else 1)

if __name__=='__main__': main()
