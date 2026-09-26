#!/usr/bin/env python3
"""UAAF v2.9 provider-backed cryptographic operations.

Private keys are addressed by key reference and resolved inside the configured
custody provider. The caller never receives private-key bytes.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SECURE = Path('.ai/federation/secure')
REFS = SECURE / 'KEY-REFERENCES.yaml'
PROVIDERS = SECURE / 'KEY-PROVIDERS.yaml'
TRUST_KEYS = Path('.ai/trust/KEYS.yaml')
AUDIT = SECURE / 'KEY-OPERATIONS-AUDIT.jsonl'
SCHEMA='2.9'
SUPPORTED={'filesystem','os-keychain','kms','hsm'}

def load_yaml(path: Path, default: dict[str,Any]|None=None):
    if not path.exists(): return dict(default or {})
    try:
        v=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return v if isinstance(v,dict) else dict(default or {})
    except Exception: return dict(default or {})

def canon(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def fp_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def iso(): return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def refs(root:Path): return load_yaml(root/REFS,{'schema_version':'2.8','references':[]}).get('references') or []

def provider_cfg(root:Path): return load_yaml(root/PROVIDERS,{})

def find_ref(root:Path,key_id:str):
    for r in refs(root):
        if isinstance(r,dict) and str(r.get('key_id'))==key_id: return r
    return None

def material_path(root:Path,key_id:str,ref:dict[str,Any])->Path:
    locator=str(ref.get('material_locator') or '').strip()
    cfg=provider_cfg(root); active=str(cfg.get('active_provider') or 'filesystem')
    pcfg=(cfg.get('providers') or {}).get(active) or {}
    if active!='filesystem':
        raise ValueError('KEY_PROVIDER_OPERATION_UNSUPPORTED')
    if locator.startswith('env:'):
        base=os.environ.get(locator[4:])
        if not base: raise ValueError('KEY_MATERIAL_ENV_NOT_SET')
        return Path(base)/f'{key_id}.ed25519.pem'
    material_dir=str(pcfg.get('material_dir') or '').strip()
    if material_dir.startswith('env:'):
        base=os.environ.get(material_dir[4:])
        if not base: raise ValueError('KEY_MATERIAL_ENV_NOT_SET')
        return Path(base)/f'{key_id}.ed25519.pem'
    if material_dir: return Path(material_dir)/f'{key_id}.ed25519.pem'
    raise ValueError('KEY_MATERIAL_LOCATION_UNCONFIGURED')

def resolve_private(root:Path,key_id:str,purpose:str|None=None):
    ref=find_ref(root,key_id)
    if not ref: raise ValueError('KEY_REFERENCE_NOT_FOUND')
    cfg=provider_cfg(root); active=str(cfg.get('active_provider') or '')
    if str(ref.get('provider'))!=active: raise ValueError('KEY_PROVIDER_REFERENCE_MISMATCH')
    if str(ref.get('status','ACTIVE')).upper()!='ACTIVE': raise ValueError('KEY_REFERENCE_INACTIVE')
    allowed=ref.get('allowed_purposes') or ([ref.get('purpose')] if ref.get('purpose') else [])
    if purpose and purpose not in [str(x) for x in allowed]: raise ValueError('KEY_PURPOSE_MISMATCH')
    if ref.get('secret_export')!='DISABLED': raise ValueError('SECRET_EXPORT_POLICY_VIOLATION')
    path=material_path(root,key_id,ref)
    if not path.exists(): raise ValueError('KEY_MATERIAL_UNAVAILABLE')
    key=serialization.load_pem_private_key(path.read_bytes(),password=None)
    if not isinstance(key,Ed25519PrivateKey): raise ValueError('PRIVATE_KEY_NOT_ED25519')
    raw=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    actual=fp_bytes(raw)
    expected=str(ref.get('public_fingerprint') or '')
    if expected and actual!=expected: raise ValueError('KEY_REFERENCE_FINGERPRINT_MISMATCH')
    return key, actual

def sign_payload(root:Path,payload:dict[str,Any],key_id:str,purpose:str,schema: str='2.9'):
    key,_=resolve_private(root,key_id,purpose)
    body=canon(payload); sig=key.sign(body)
    return {'schema_version':schema,'algorithm':'Ed25519','purpose':purpose,'key_id':key_id,'payload_sha256':hashlib.sha256(body).hexdigest(),'signature_b64':base64.b64encode(sig).decode(),'created_at':iso(),'provider':'provider-backed'}

def public_key_for_reference(root:Path,key_id:str)->Ed25519PublicKey:
    ref=find_ref(root,key_id)
    if not ref: raise ValueError('KEY_REFERENCE_NOT_FOUND')
    value=str(ref.get('public_key_b64') or '')
    if not value: raise ValueError('PUBLIC_KEY_NOT_BOUND')
    raw=base64.b64decode(value,validate=True)
    if len(raw)!=32: raise ValueError('PUBLIC_KEY_INVALID')
    return Ed25519PublicKey.from_public_bytes(raw)

def bind(root:Path,key_id:str,purpose:str,public_key_file:Path,provider:str='filesystem')->dict[str,Any]:
    cfg=provider_cfg(root); active=str(cfg.get('active_provider') or '')
    if provider!=active: raise ValueError('KEY_PROVIDER_REFERENCE_MISMATCH')
    pub=serialization.load_pem_public_key(public_key_file.read_bytes())
    if not isinstance(pub,Ed25519PublicKey): raise ValueError('PUBLIC_KEY_NOT_ED25519')
    raw=pub.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    expected=fp_bytes(raw)
    rs=load_yaml(root/REFS,{'schema_version':'2.9','references':[]})
    arr=rs.setdefault('references',[])
    found=None
    for row in arr:
        if isinstance(row,dict) and str(row.get('key_id'))==key_id: found=row; break
    purpose_list=[x.strip() for x in purpose.split(',') if x.strip()]
    if not purpose_list: raise ValueError('KEY_PURPOSE_REQUIRED')
    if found is None:
        found={'key_id':key_id,'provider':provider,'purpose':purpose_list[0],'allowed_purposes':purpose_list,'public_fingerprint':expected,'public_key_b64':base64.b64encode(raw).decode(),'secret_export':'DISABLED'}
        arr.append(found)
    else:
        if str(found.get('provider'))!=provider: raise ValueError('KEY_REFERENCE_BINDING_MISMATCH')
        existing=[str(x) for x in (found.get('allowed_purposes') or ([found.get('purpose')] if found.get('purpose') else []))]
        merged=list(dict.fromkeys(existing+purpose_list))
        found.update({'purpose':merged[0],'allowed_purposes':merged,'public_fingerprint':expected,'public_key_b64':base64.b64encode(raw).decode(),'secret_export':'DISABLED'})
    rs['schema_version']='2.9'; (root/REFS).parent.mkdir(parents=True,exist_ok=True); (root/REFS).write_text(yaml.safe_dump(rs,sort_keys=False),encoding='utf-8')
    audit(root,{'event':'KEY_REFERENCE_BOUND','key_id':key_id,'provider':provider,'purpose':purpose,'public_fingerprint':expected})
    return {'status':'PASS','key_id':key_id,'provider':provider,'purpose':purpose,'public_fingerprint':expected,'private_key_return':'DISABLED'}

def verify_file(root:Path,path:Path,key_id:str,purpose:str,sig_path:Path)->dict[str,Any]:
    ref=find_ref(root,key_id)
    if not ref: return {'status':'DENIED','reason':'KEY_REFERENCE_NOT_FOUND'}
    allowed=ref.get('allowed_purposes') or ([ref.get('purpose')] if ref.get('purpose') else [])
    if purpose not in [str(x) for x in allowed]: return {'status':'DENIED','reason':'KEY_PURPOSE_MISMATCH'}
    try: env=json.loads(sig_path.read_text(encoding='utf-8'))
    except Exception: return {'status':'DENIED','reason':'SIGNATURE_INVALID_JSON'}
    body=canon({'file_sha256':fp_bytes(path.read_bytes()),'file':path.name})
    if env.get('schema_version')!='2.9' or env.get('algorithm')!='Ed25519' or env.get('provider')!='provider-backed': return {'status':'DENIED','reason':'SIGNATURE_SCHEMA_MISMATCH'}
    if env.get('key_id')!=key_id or env.get('purpose')!=purpose: return {'status':'DENIED','reason':'SIGNATURE_BINDING_MISMATCH'}
    if env.get('payload_sha256')!=hashlib.sha256(body).hexdigest(): return {'status':'DENIED','reason':'PAYLOAD_HASH_MISMATCH'}
    try: public_key_for_reference(root,key_id).verify(base64.b64decode(str(env.get('signature_b64','')),validate=True),body)
    except Exception: return {'status':'DENIED','reason':'SIGNATURE_INVALID'}
    return {'status':'PASS','key_id':key_id,'purpose':purpose,'verified':True}

def rotate_reference(root:Path,old_key_id:str,new_key_id:str,purpose:str)->dict[str,Any]:
    cfg=provider_cfg(root); active=str(cfg.get('active_provider') or '')
    if active!='filesystem': raise ValueError('KEY_PROVIDER_ROTATION_UNSUPPORTED')
    old=find_ref(root,old_key_id)
    if not old: raise ValueError('OLD_KEY_REFERENCE_NOT_FOUND')
    base=material_path(root,new_key_id,{'key_id':new_key_id})
    base.parent.mkdir(parents=True,exist_ok=True)
    new=Ed25519PrivateKey.generate()
    base.write_bytes(new.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    try: base.chmod(0o600)
    except OSError: pass
    pub=new.public_key(); raw=pub.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); f=fp_bytes(raw)
    rs=load_yaml(root/REFS,{'schema_version':'2.9','references':[]}); rs['schema_version']='2.9'; arr=rs.setdefault('references',[])
    updated=[]
    for r in arr:
        if isinstance(r,dict) and str(r.get('key_id'))==old_key_id:
            r=dict(r); r['status']='RETIRED'; r['retired_at']=iso(); updated.append(r)
        elif isinstance(r,dict) and str(r.get('key_id'))==new_key_id:
            continue
        else:
            updated.append(r)
    plist=[x.strip() for x in purpose.split(',') if x.strip()]
    if not plist: raise ValueError('KEY_PURPOSE_REQUIRED')
    updated.append({'key_id':new_key_id,'provider':active,'purpose':plist[0],'allowed_purposes':plist,'public_fingerprint':f,'public_key_b64':base64.b64encode(raw).decode(),'secret_export':'DISABLED','status':'ACTIVE'})
    rs['references']=updated; (root/REFS).write_text(yaml.safe_dump(rs,sort_keys=False),encoding='utf-8')
    try:
        old_path=material_path(root,old_key_id,old)
        if old_path.exists(): old_path.unlink()
    except Exception:
        pass
    audit(root,{'event':'KEY_REFERENCE_ROTATED','from_key_id':old_key_id,'to_key_id':new_key_id,'purpose':purpose,'public_fingerprint':f,'old_status':'RETIRED'})
    return {'status':'PASS','from_key_id':old_key_id,'to_key_id':new_key_id,'public_fingerprint':f,'private_key_return':'DISABLED'}

def sign_file(root:Path,path:Path,key_id:str,purpose:str,out:Path|None=None):
    env=sign_payload(root,{'file_sha256':fp_bytes(path.read_bytes()),'file':path.name},key_id,purpose)
    dest=out or path.with_name(path.name+'.sig'); dest.write_text(json.dumps(env,indent=2)+'\n',encoding='utf-8')
    try: audit_path=str(path.relative_to(root))
    except ValueError: audit_path='external:'+path.name
    audit(root,{'event':'PROVIDER_SIGN','key_id':key_id,'purpose':purpose,'path':audit_path})
    return {'status':'PASS','signature':str(dest),'key_id':key_id,'provider':'provider-backed'}

def audit(root:Path,event:dict[str,Any]):
    p=root/AUDIT; p.parent.mkdir(parents=True,exist_ok=True); prev='GENESIS'
    lines=[x for x in p.read_text(encoding='utf-8').splitlines() if x.strip()] if p.exists() else []
    if lines:
        try: prev=str(json.loads(lines[-1]).get('entry_hash','GENESIS'))
        except Exception: prev='BROKEN'
    row={'schema_version':SCHEMA,'timestamp':iso(),'prev_hash':prev,**event}; row['entry_hash']=hashlib.sha256(canon(row)).hexdigest()
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n')

def status(root:Path):
    cfg=provider_cfg(root); active=str(cfg.get('active_provider') or '')
    rows=[]
    for r in refs(root):
        if isinstance(r,dict): rows.append({'key_id':r.get('key_id'),'provider':r.get('provider'),'purpose':r.get('purpose'),'secret_export':r.get('secret_export'),'material_locator':r.get('material_locator','provider://filesystem')})
    return {'status':'PASS','schema_version':SCHEMA,'active_provider':active,'references':rows,'private_key_export':'DISABLED'}

def main():
    ap=argparse.ArgumentParser(description='UAAF v2.9 provider-backed key operations')
    sp=ap.add_subparsers(dest='cmd',required=True)
    q=sp.add_parser('status'); q.add_argument('path',nargs='?',default='.'); q.add_argument('--json',action='store_true')
    q=sp.add_parser('sign'); q.add_argument('path'); q.add_argument('--key-id',required=True); q.add_argument('--purpose',required=True); q.add_argument('--payload-file',required=True); q.add_argument('--out'); q.add_argument('--json',action='store_true')
    q=sp.add_parser('bind'); q.add_argument('path'); q.add_argument('--key-id',required=True); q.add_argument('--purpose',required=True); q.add_argument('--public-key-file',required=True); q.add_argument('--provider',default='filesystem'); q.add_argument('--json',action='store_true')
    q=sp.add_parser('verify'); q.add_argument('path'); q.add_argument('--key-id',required=True); q.add_argument('--purpose',required=True); q.add_argument('--payload-file',required=True); q.add_argument('--signature-file',required=True); q.add_argument('--json',action='store_true')
    q=sp.add_parser('rotate'); q.add_argument('path'); q.add_argument('--old-key-id',required=True); q.add_argument('--new-key-id',required=True); q.add_argument('--purpose',required=True); q.add_argument('--json',action='store_true')
    q=sp.add_parser('sign-payload'); q.add_argument('path'); q.add_argument('--key-id',required=True); q.add_argument('--purpose',required=True); q.add_argument('--payload-json',required=True); q.add_argument('--json',action='store_true')
    a=ap.parse_args(); root=Path(a.path).resolve()
    try:
        if a.cmd=='status': r=status(root)
        elif a.cmd=='sign': r=sign_file(root,Path(a.payload_file).resolve(),a.key_id,a.purpose,Path(a.out).resolve() if a.out else None)
        elif a.cmd=='bind': r=bind(root,a.key_id,a.purpose,Path(a.public_key_file).resolve(),a.provider)
        elif a.cmd=='verify': r=verify_file(root,Path(a.payload_file).resolve(),a.key_id,a.purpose,Path(a.signature_file).resolve())
        elif a.cmd=='rotate': r=rotate_reference(root,a.old_key_id,a.new_key_id,a.purpose)
        else:
            payload=json.loads(a.payload_json); r={'status':'PASS','envelope':sign_payload(root,payload,a.key_id,a.purpose)}; audit(root,{'event':'PROVIDER_SIGN_PAYLOAD','key_id':a.key_id,'purpose':a.purpose})
    except Exception as exc: r={'status':'DENIED','reason':str(exc)}
    print(json.dumps(r,indent=2,ensure_ascii=False) if getattr(a,'json',False) else r.get('status'))
    raise SystemExit(0 if r.get('status')=='PASS' else 1)
if __name__=='__main__': main()
