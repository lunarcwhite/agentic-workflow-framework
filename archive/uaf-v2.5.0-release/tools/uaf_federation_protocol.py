#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, json
from pathlib import Path
from typing import Any
import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey

SCHEMA='2.4'
FED=Path('.ai/federation')
PROTO=FED/'protocol'
CAP=PROTO/'CAPABILITIES.yaml'
COMPAT=PROTO/'COMPATIBILITY.yaml'
NEG=PROTO/'NEGOTIATION.yaml'
CONTRACT=PROTO/'PROTOCOL-CONTRACT.yaml'
AUDIT=PROTO/'AUDIT.jsonl'

PROTOCOL_FAMILIES = {
    'federation': ['2.0'],
    'federation_ops': ['2.1'],
    'federation_intelligence': ['2.2'],
    'federation_policy': ['2.3'],
    'federation_protocol': ['2.4'],
}

FEATURES = {
    'capability-exchange',
    'protocol-negotiation',
    'safe-fallback',
    'federated-policy',
    'federation-ops',
    'conflict-intelligence',
}

RISK = {'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}
EVIDENCE = {f'E{i}':i for i in range(6)}

def load(path: Path, default=None) -> dict[str, Any]:
    if not path.exists(): return dict(default or {})
    try:
        v = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        return v if isinstance(v, dict) else dict(default or {})
    except Exception:
        return dict(default or {})

def dump(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')

def canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def fp(v: Any) -> str:
    return hashlib.sha256(canon(v)).hexdigest()

def version_key(v: str) -> tuple[int, ...]:
    try: return tuple(int(x) for x in str(v).split('.'))
    except Exception: return (-1,)

def normalize_caps(doc: dict[str, Any]) -> dict[str, Any]:
    protocols = {}
    raw_protocols = doc.get('protocols') or {}
    for family in PROTOCOL_FAMILIES:
        vals = raw_protocols.get(family) or []
        if isinstance(vals, dict): vals = vals.get('supported', []) or []
        protocols[family] = sorted({str(v) for v in vals}, key=version_key)
    features = {}
    raw_features = doc.get('features') or {}
    if isinstance(raw_features, list):
        raw_features = {str(x): {'required': False, 'optional': True} for x in raw_features}
    for name, spec in raw_features.items():
        if isinstance(spec, bool): spec = {'required': bool(spec), 'optional': not bool(spec)}
        spec = dict(spec or {})
        features[str(name)] = {
            'required': bool(spec.get('required', False)),
            'optional': bool(spec.get('optional', True)),
            'fallback_safe': bool(spec.get('fallback_safe', False)),
            'min_protocol': {str(k): str(v) for k, v in (spec.get('min_protocol') or {}).items()},
        }
    sec = doc.get('security') or {}
    compat = doc.get('compatibility') or {}
    fallbacks = compat.get('fallbacks') or {}
    return {
        'project_id': str(doc.get('project_id', '')),
        'peer_id': str(doc.get('peer_id', '')),
        'protocols': protocols,
        'features': features,
        'security': {
            'min_evidence': str(sec.get('min_evidence', 'E0')).upper(),
            'require_signed_offer': bool(sec.get('require_signed_offer', True)),
            'require_signed_contract': bool(sec.get('require_signed_contract', True)),
        },
        'fallbacks': {str(k): sorted({str(x) for x in (v or [])}, key=version_key) for k, v in fallbacks.items()},
    }

def local_caps(root: Path) -> dict[str, Any]:
    return normalize_caps(load(root / CAP, {}))

def protocol_satisfies_feature(selected: dict[str, str], feature: dict[str, Any]) -> bool:
    for family, minimum in (feature.get('min_protocol') or {}).items():
        current = selected.get(family)
        if current is None or version_key(current) < version_key(minimum):
            return False
    return True

def select_protocol(local: dict[str, Any], remote: dict[str, Any], family: str) -> tuple[str|None, bool, str]:
    lp = local['protocols'].get(family, [])
    rp = remote['protocols'].get(family, [])
    common = sorted(set(lp) & set(rp), key=version_key, reverse=True)
    if common:
        return common[0], False, 'COMMON_VERSION'
    # Safe fallback requires both peers to advertise the fallback explicitly.
    candidates = []
    for v in local.get('fallbacks', {}).get(family, []):
        if v in rp and v in remote.get('fallbacks', {}).get(family, []):
            candidates.append(v)
    for v in remote.get('fallbacks', {}).get(family, []):
        if v in lp and v in local.get('fallbacks', {}).get(family, []):
            candidates.append(v)
    if candidates:
        return sorted(set(candidates), key=version_key, reverse=True)[0], True, 'EXPLICIT_SAFE_FALLBACK'
    return None, False, 'NO_COMPATIBLE_VERSION'

def feature_decisions(local: dict[str, Any], remote: dict[str, Any], selected: dict[str, str], fallback_used: bool) -> tuple[list[str], list[dict[str, Any]], str|None, bool]:
    names = sorted(set(local['features']) | set(remote['features']))
    enabled: list[str] = []
    disabled: list[dict[str, Any]] = []
    denial = None
    review_required = False
    for name in names:
        l = local['features'].get(name, {})
        r = remote['features'].get(name, {})
        required = bool(l.get('required') or r.get('required'))
        supported = name in FEATURES and name in local['features'] and name in remote['features']
        selected_ok = supported and protocol_satisfies_feature(selected, l) and protocol_satisfies_feature(selected, r)
        if selected_ok:
            enabled.append(name)
            continue
        safe_fallback = bool(l.get('fallback_safe') and r.get('fallback_safe'))
        reason = 'UNSUPPORTED_BY_BOTH' if not supported else 'PROTOCOL_VERSION_TOO_LOW'
        disabled.append({'feature': name, 'required': required, 'reason': reason, 'fallback_safe': safe_fallback})
        if required:
            if fallback_used and safe_fallback:
                review_required = True
                continue
            denial = f'REQUIRED_FEATURE_UNAVAILABLE:{name}'
    return enabled, disabled, denial, review_required

def audit(root: Path, event: dict[str, Any]) -> None:
    root.joinpath(AUDIT).parent.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event.setdefault('schema_version', SCHEMA)
    root.joinpath(AUDIT).open('a', encoding='utf-8').write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

def verify_offer_signature(root: Path, offer: dict[str, Any], peer_id: str) -> tuple[bool,str]:
    sig = offer.get('signature') or {}
    key = root / FED / 'peers' / str(peer_id) / 'ROOT.pub.pem'
    if not sig: return False, 'REMOTE_OFFER_UNSIGNED'
    if not key.exists(): return False, 'REMOTE_ROOT_NOT_PINNED'
    payload = {k:v for k,v in offer.items() if k != 'signature'}
    try:
        public = serialization.load_pem_public_key(key.read_bytes())
        raw = public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if sig.get('schema_version') != SCHEMA: return False, 'SIGNATURE_SCHEMA_MISMATCH'
        if sig.get('purpose') != 'federation-capability-offer': return False, 'PURPOSE_MISMATCH'
        if sig.get('payload_sha256') != fp(payload): return False, 'PAYLOAD_HASH_MISMATCH'
        Ed25519PublicKey.from_public_bytes(raw).verify(base64.b64decode(sig.get('signature_b64',''), validate=True), canon(payload))
    except (OSError, ValueError, InvalidSignature, TypeError, KeyError):
        return False, 'SIGNATURE_INVALID'
    return True, 'OK'

def offer(root: Path, peer_id: str, out: str, private_key: str|None = None, key_id: str|None = None) -> dict[str, Any]:
    caps = load(root / CAP, {'schema_version': SCHEMA})
    if str(caps.get('schema_version')) != SCHEMA:
        return {'status':'FAIL','reason':'CAPABILITY_SCHEMA_MISMATCH'}
    caps = dict(caps)
    caps['peer_id'] = peer_id
    payload = {'schema_version': SCHEMA, 'offer_id': f'CAP-{fp(caps)[:12]}', 'peer_id': peer_id, 'capabilities': normalize_caps(caps)}
    if private_key:
        try:
            private = serialization.load_pem_private_key(Path(private_key).read_bytes(), password=None)
            if not isinstance(private, Ed25519PrivateKey):
                return {'status':'FAIL','reason':'PRIVATE_KEY_NOT_ED25519'}
            raw = private.sign(canon(payload))
            payload['signature'] = {'schema_version':SCHEMA,'purpose':'federation-capability-offer','payload_sha256':fp(payload),'signature_b64':base64.b64encode(raw).decode(),'key_id':key_id or peer_id}
        except Exception:
            return {'status':'FAIL','reason':'SIGNING_FAILED'}
    dump(Path(out), payload)
    audit(root, {'event':'CAPABILITY_OFFER_CREATED','peer_id':peer_id,'offer_id':payload['offer_id'],'signed':bool(private_key)})
    return {'status':'PASS','file':str(out),'offer_id':payload['offer_id'],'signed':bool(private_key)}

def negotiate(root: Path, remote_file: str, peer_id: str|None, require_remote_signature: bool) -> dict[str, Any]:
    remote_doc = load(Path(remote_file), {})
    if str(remote_doc.get('schema_version')) != SCHEMA:
        return {'status':'DENIED','reason':'REMOTE_OFFER_SCHEMA_MISMATCH'}
    remote_caps = normalize_caps(remote_doc.get('capabilities') or {})
    local = local_caps(root)
    actual_peer = str(peer_id or remote_caps.get('peer_id') or remote_doc.get('peer_id',''))
    if require_remote_signature:
        ok, reason = verify_offer_signature(root, remote_doc, actual_peer)
        if not ok:
            return {'status':'DENIED','reason':reason}
    selected: dict[str,str] = {}
    fallback: dict[str,Any] = {}
    missing: list[str] = []
    for family in PROTOCOL_FAMILIES:
        v, used, reason = select_protocol(local, remote_caps, family)
        if v is None:
            missing.append(family)
            continue
        selected[family] = v
        if used: fallback[family] = {'selected':v,'reason':reason}
    if missing:
        result = {'schema_version':SCHEMA,'status':'DENIED','peer_id':actual_peer,'reason':'NO_COMPATIBLE_PROTOCOL','missing_protocols':missing}
        dump(root/NEG, result); return result
    enabled, disabled, denial, review_required = feature_decisions(local, remote_caps, selected, bool(fallback))
    if denial:
        status='DENIED'
    elif review_required:
        status='REVIEW_REQUIRED'
    elif fallback:
        status='FALLBACK_NEGOTIATED'
    else:
        status='NEGOTIATED'
    contract_core = {
        'protocols': selected,
        'enabled_features': enabled,
        'disabled_features': disabled,
        'fallbacks': fallback,
        'authority_change': 'NONE',
        'security_floor': max(EVIDENCE.get(local['security']['min_evidence'],99), EVIDENCE.get(remote_caps['security']['min_evidence'],99)),
    }
    result = {
        'schema_version':SCHEMA,'status':status,'peer_id':actual_peer,
        'offer_id':remote_doc.get('offer_id'),'local_capabilities':local,'remote_capabilities':remote_caps,
        'selected_protocols':selected,'enabled_features':enabled,'disabled_features':disabled,
        'fallbacks':fallback,'contract_hash':fp(contract_core),'advisory_only':True,
        **({'reason': denial} if denial else {}),
    }
    dump(root/NEG,result)
    audit(root, {'event':'NEGOTIATION_RESULT','peer_id':actual_peer,'status':status,'contract_hash':fp(contract_core),'fallback':bool(fallback)})
    dump(root/CONTRACT,{'schema_version':SCHEMA,'status':status,'peer_id':actual_peer,'contract_hash':fp(contract_core),'contract':contract_core})
    return result

def contract_check(root: Path) -> dict[str, Any]:
    c = load(root/CONTRACT,{})
    issues=[]
    if not c: return {'status':'PASS','issues':[],'configured':False}
    if str(c.get('schema_version')) != SCHEMA: issues.append('CONTRACT_SCHEMA_MISMATCH')
    contract = c.get('contract') or {}
    selected = contract.get('protocols') or {}
    for family, version in selected.items():
        if family not in PROTOCOL_FAMILIES: issues.append(f'UNKNOWN_PROTOCOL_FAMILY:{family}')
        elif str(version) not in PROTOCOL_FAMILIES[family] + local_caps(root)['protocols'].get(family,[]):
            issues.append(f'UNSUPPORTED_SELECTED_VERSION:{family}:{version}')
    if c.get('status') in {'NEGOTIATED','FALLBACK_NEGOTIATED'} and contract.get('authority_change') != 'NONE': issues.append('AUTHORITY_ESCALATION_FORBIDDEN')
    if c.get('status') in {'NEGOTIATED','FALLBACK_NEGOTIATED'} and not c.get('contract_hash'):
        issues.append('MISSING_CONTRACT_HASH')
    for item in contract.get('disabled_features',[]) or []:
        if item.get('required') and not item.get('fallback_safe'):
            issues.append(f"REQUIRED_FEATURE_DISABLED:{item.get('feature')}")
    return {'status':'PASS' if not issues else 'FAIL','issues':issues,'configured':True,'deny_first':True}

def authorize(root: Path, protocol_family: str, version: str, feature: str|None) -> dict[str,Any]:
    c=load(root/CONTRACT,{})
    if str(c.get('schema_version')) != SCHEMA or c.get('status') not in {'NEGOTIATED','FALLBACK_NEGOTIATED'}:
        return {'status':'DENIED','reason':'PROTOCOL_CONTRACT_NOT_ACTIVE'}
    selected=(c.get('contract') or {}).get('protocols') or {}
    if selected.get(protocol_family) != version:
        return {'status':'DENIED','reason':'PROTOCOL_VERSION_NOT_NEGOTIATED'}
    if feature and feature not in set((c.get('contract') or {}).get('enabled_features',[]) or []):
        return {'status':'DENIED','reason':'FEATURE_NOT_NEGOTIATED'}
    return {'status':'AUTHORIZED','protocol':protocol_family,'version':version,'feature':feature}

def main():
    p=argparse.ArgumentParser(description='UAAF v2.4 federation capability exchange')
    s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('offer'); q.add_argument('path'); q.add_argument('--peer-id',required=True); q.add_argument('--out',required=True); q.add_argument('--private-key'); q.add_argument('--key-id')
    q=s.add_parser('negotiate'); q.add_argument('path'); q.add_argument('--remote-file',required=True); q.add_argument('--peer-id'); q.add_argument('--require-remote-signature',action='store_true')
    q=s.add_parser('check'); q.add_argument('path',nargs='?',default='.')
    q=s.add_parser('authorize'); q.add_argument('path'); q.add_argument('--protocol-family',required=True); q.add_argument('--version',required=True); q.add_argument('--feature')
    a=p.parse_args(); root=Path(getattr(a,'path','.')).resolve()
    if a.cmd=='offer': r=offer(root,a.peer_id,a.out,a.private_key,a.key_id)
    elif a.cmd=='negotiate': r=negotiate(root,a.remote_file,a.peer_id,a.require_remote_signature)
    elif a.cmd=='check': r=contract_check(root)
    else: r=authorize(root,a.protocol_family,a.version,a.feature)
    print(json.dumps(r,indent=2,ensure_ascii=False))
    raise SystemExit(0 if r.get('status') in {'PASS','NEGOTIATED','FALLBACK_NEGOTIATED','AUTHORIZED'} else 1)
if __name__=='__main__': main()
