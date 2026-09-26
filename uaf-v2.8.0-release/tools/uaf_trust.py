#!/usr/bin/env python3
"""UAAF v1.8 Agent Trust & Delegation.

Project-level authorization metadata for multi-agent workflows. This tool does
not authenticate OS identities or replace enterprise IAM. Decisions are bounded
by capability, authority, domain, risk, evidence floor, evidence history, and
explicit delegation chains.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

SCHEMA_VERSION = "1.8"
TRUST = ".ai/agents/TRUST.yaml"
DELEGATIONS = ".ai/agents/DELEGATIONS.yaml"
AUDIT = ".ai/agents/TRUST-AUDIT.jsonl"
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
ACTIONS = {"read", "write", "delete", "migrate", "approve", "apply", "verify"}
STATUSES = {"ACTIVE", "REVOKED", "EXPIRED", "SUSPENDED"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso() -> str:
    return now().astimezone().isoformat(timespec="seconds")


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default.copy()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else default.copy()
    except Exception:
        return default.copy()


def trust_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / TRUST, {"schema_version": SCHEMA_VERSION, "policy": {}, "agents": []})


def delegation_doc(root: Path) -> dict[str, Any]:
    return load_yaml(root / DELEGATIONS, {"schema_version": SCHEMA_VERSION, "delegations": []})


def audit(root: Path, event: dict[str, Any]) -> None:
    """Append trust audit; v1.9 uses a tamper-evident hash chain."""
    try:
        manifest = load_yaml(root / ".ai/manifest.yaml", {})
        ext = manifest.get("extensions") or {}
        if float(str(ext.get("version", "0"))) >= 1.9:
            from uaf_crypto import append_audit
            append_audit(root, event)
            return
    except Exception:
        pass
    p = root / AUDIT
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema_version": SCHEMA_VERSION, "timestamp": iso(), **event}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def index_agents(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["id"]): item
        for item in (doc.get("agents", []) or [])
        if isinstance(item, dict) and item.get("id")
    }


def index_delegations(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    current = now()
    for item in doc.get("delegations", []) or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "ACTIVE")) != "ACTIVE":
            continue
        until = parse_ts(item.get("expires_at"))
        if until and until <= current:
            continue
        out.append(item)
    return out


def token_set(values: Any) -> set[str]:
    if isinstance(values, str):
        return {values.lower()}
    if isinstance(values, list):
        return {str(v).lower() for v in values}
    return set()


def min_risk(a: str, b: str) -> str:
    return a if RISK_ORDER.get(a, 0) <= RISK_ORDER.get(b, 0) else b


def max_evidence(a: str, b: str) -> str:
    try:
        return a if int(a[1:]) >= int(b[1:]) else b
    except Exception:
        return "E0"


def intersect_domains(a: set[str], b: set[str]) -> set[str]:
    if not a:
        return set(b)
    if not b:
        return set(a)
    if "*" in a:
        return set(b)
    if "*" in b:
        return set(a)
    return a & b


def intersect_capabilities(a: set[str], b: set[str]) -> set[str]:
    if not a or not b:
        return set()
    if "*" in a:
        return set(b)
    if "*" in b:
        return set(a)
    return a & b


def edge_bounded(parent: dict[str, Any], delegation: dict[str, Any]) -> tuple[bool, str]:
    pcaps = token_set(parent.get("capabilities"))
    dcaps = token_set(delegation.get("capabilities"))
    if not dcaps or ("*" not in pcaps and not dcaps.issubset(pcaps)):
        return False, "DELEGATION_ESCALATION_CAPABILITY"
    pdomains = token_set(parent.get("domains"))
    ddomains = token_set(delegation.get("domains"))
    if pdomains and "*" not in pdomains and not ddomains.issubset(pdomains):
        return False, "DELEGATION_ESCALATION_DOMAIN"
    if RISK_ORDER.get(str(delegation.get("max_risk", "LOW")).upper(), 99) > RISK_ORDER.get(str(parent.get("max_risk", "LOW")).upper(), 0):
        return False, "DELEGATION_ESCALATION_RISK"
    expires = parse_ts(delegation.get("expires_at"))
    if not expires or expires <= now():
        return False, "DELEGATION_EXPIRED"
    return True, "OK"


def effective_profiles(root: Path, agent_id: str, *, max_depth: int = 16) -> Iterator[tuple[dict[str, Any], list[str]]]:
    trust = trust_doc(root)
    agents = index_agents(trust)
    delegations = index_delegations(delegation_doc(root))

    def dfs(current_id: str, visited: tuple[str, ...]) -> list[tuple[dict[str, Any], list[str]]]:
        if current_id in visited or len(visited) >= max_depth or current_id not in agents:
            return []
        base = agents[current_id]
        if bool(base.get("direct_authority", False)):
            return [(dict(base), [current_id])]

        results: list[tuple[dict[str, Any], list[str]]] = []
        for delegation in delegations:
            if str(delegation.get("to_agent")) != current_id:
                continue
            parent_id = str(delegation.get("from_agent", ""))
            parent = agents.get(parent_id)
            if not parent:
                continue
            ok, _ = edge_bounded(parent, delegation)
            if not ok:
                continue
            for parent_eff, parent_chain in dfs(parent_id, visited + (current_id,)):
                grant_caps = token_set(delegation.get("capabilities"))
                parent_caps = token_set(parent_eff.get("capabilities"))
                eff_caps = intersect_capabilities(parent_caps, grant_caps)
                grant_domains = token_set(delegation.get("domains"))
                parent_domains = token_set(parent_eff.get("domains"))
                eff_domains = intersect_domains(parent_domains, grant_domains)
                eff = dict(base)
                eff.update({
                    "authority": "DELEGATED",
                    "direct_authority": False,
                    "capabilities": sorted(eff_caps),
                    "domains": sorted(eff_domains),
                    "max_risk": min_risk(str(parent_eff.get("max_risk", "LOW")).upper(), str(delegation.get("max_risk", "LOW")).upper()),
                    "min_evidence": max_evidence(str(parent_eff.get("min_evidence", "E0")).upper(), str(delegation.get("min_evidence", "E0")).upper()),
                    "min_recent_verified_evidence": max(int(parent_eff.get("min_recent_verified_evidence", 0) or 0), int(base.get("min_recent_verified_evidence", 0) or 0)),
                    "evidence_window_days": max(int(parent_eff.get("evidence_window_days", 30) or 30), int(base.get("evidence_window_days", 30) or 30)),
                    "can_delegate": bool(parent_eff.get("can_delegate", False)) and bool(delegation.get("can_delegate", False)) and bool(base.get("can_delegate", False)),
                })
                results.append((eff, parent_chain + [current_id]))
        return results

    yield from dfs(agent_id, tuple())


def recent_verified_count(root: Path, agent_id: str, window_days: int) -> int:
    base = root / ".ai/evidence"
    if not base.exists():
        return 0
    cutoff = now() - timedelta(days=max(0, window_days))
    count = 0
    for path in base.glob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("verified_by", "")) != agent_id:
            continue
        if str(data.get("status", "")).upper() not in {"VERIFIED", "PASS"}:
            continue
        timestamp = parse_ts(data.get("verified_at"))
        if timestamp is None or timestamp < cutoff:
            continue
        count += 1
    return count


def has_capability(agent: dict[str, Any], action: str) -> bool:
    caps = token_set(agent.get("capabilities"))
    return "*" in caps or action.lower() in caps


def allows_domain(agent: dict[str, Any], domain: str) -> bool:
    domains = token_set(agent.get("domains"))
    return not domains or "*" in domains or domain.lower() in domains


def allowed_risk(agent: dict[str, Any], risk: str) -> bool:
    return RISK_ORDER.get(risk.upper(), 99) <= RISK_ORDER.get(str(agent.get("max_risk", "LOW")).upper(), 0)


def evidence_ok(agent: dict[str, Any], evidence: str | None) -> bool:
    required = str(agent.get("min_evidence", "E0")).upper()
    supplied = str(evidence or "E0").upper()
    try:
        return int(supplied[1:]) >= int(required[1:])
    except Exception:
        return False


def evaluate(root: Path, agent_id: str, action: str, domain: str, risk: str, evidence: str | None = None) -> dict[str, Any]:
    action = action.lower(); risk = risk.upper()
    if action not in ACTIONS:
        return {"decision": "DENIED", "reason": "UNKNOWN_ACTION"}
    if risk not in RISK_ORDER:
        return {"decision": "DENIED", "reason": "UNKNOWN_RISK"}
    trust = trust_doc(root)
    agents = index_agents(trust)
    base = agents.get(agent_id)
    if not base:
        return {"decision": "DENIED", "reason": "AGENT_NOT_REGISTERED", "agent": agent_id}
    if str(base.get("status", "ACTIVE")) != "ACTIVE":
        return {"decision": "DENIED", "reason": f"AGENT_{str(base.get('status', 'UNKNOWN')).upper()}", "agent": agent_id}

    policy = trust.get("policy") or {}
    try:
        manifest = load_yaml(root / ".ai/manifest.yaml", {})
        ext = manifest.get("extensions") or {}
        if float(str(ext.get("version", "0"))) >= 1.9:
            crypto_cfg = ext.get("cryptographic_integrity") or {}
            root_cfg = load_yaml(root / ".ai/trust/ROOT.yaml", {})
            crypto_policy = root_cfg.get("policy") or {}
            required_crypto = bool(crypto_cfg.get("cryptographic_required", False)) or bool(crypto_policy.get("cryptographic_required", False))
            if required_crypto:
                from uaf_crypto import verify_project_bundle
                verification = verify_project_bundle(root)
                if verification.get("status") != "PASS":
                    audit(root, {"action": "CRYPTO_CHECK", "agent": agent_id, "decision": "DENIED", "reason": "CRYPTOGRAPHIC_BUNDLE_INVALID"})
                    return {"decision": "DENIED", "reason": "CRYPTOGRAPHIC_BUNDLE_INVALID", "agent": agent_id, "crypto": verification}
    except Exception as exc:
        return {"decision": "DENIED", "reason": "CRYPTOGRAPHIC_CHECK_ERROR", "agent": agent_id, "error": str(exc)}
    if action in token_set(policy.get("deny_actions")):
        return {"decision": "DENIED", "reason": "POLICY_DENY_ACTION", "agent": agent_id}

    candidates = []
    for effective, chain in effective_profiles(root, agent_id):
        if not has_capability(effective, action):
            continue
        if not allows_domain(effective, domain):
            continue
        if not allowed_risk(effective, risk):
            continue
        if not evidence_ok(effective, evidence):
            continue
        required_recent = int(effective.get("min_recent_verified_evidence", 0) or 0)
        window = int(effective.get("evidence_window_days", 30) or 30)
        recent = recent_verified_count(root, agent_id, window)
        if recent < required_recent:
            continue
        candidates.append((effective, chain, recent))

    if candidates:
        effective, chain, recent = candidates[0]
        return {
            "decision": "AUTHORIZED",
            "reason": "POLICY_MATCH",
            "agent": agent_id,
            "chain": chain,
            "recent_verified_evidence": recent,
            "effective": {k: effective.get(k) for k in ["authority", "capabilities", "domains", "max_risk", "min_evidence", "min_recent_verified_evidence"]},
        }

    # Distinguish common review conditions from hard denial.
    for effective, chain in effective_profiles(root, agent_id):
        if has_capability(effective, action) and allows_domain(effective, domain):
            if not allowed_risk(effective, risk):
                return {"decision": "REVIEW_REQUIRED", "reason": "RISK_EXCEEDS_AUTHORITY", "agent": agent_id, "chain": chain}
            if not evidence_ok(effective, evidence):
                return {"decision": "REVIEW_REQUIRED", "reason": "EVIDENCE_BELOW_REQUIRED_FLOOR", "agent": agent_id, "chain": chain, "required": effective.get("min_evidence", "E0"), "supplied": evidence or "E0"}
            required_recent = int(effective.get("min_recent_verified_evidence", 0) or 0)
            if recent_verified_count(root, agent_id, int(effective.get("evidence_window_days", 30) or 30)) < required_recent:
                return {"decision": "REVIEW_REQUIRED", "reason": "EVIDENCE_HISTORY_INSUFFICIENT", "agent": agent_id, "chain": chain, "required": required_recent}
    return {"decision": "DENIED", "reason": "AUTHORIZATION_NOT_GRANTED", "agent": agent_id}


def main() -> None:
    p = argparse.ArgumentParser(description="UAAF v1.8 agent trust and delegation")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("action", choices=["check", "evaluate", "status", "delegate", "revoke"])
    p.add_argument("--agent")
    p.add_argument("--from-agent")
    p.add_argument("--to-agent")
    p.add_argument("--delegation-id")
    p.add_argument("--capability", action="append", default=[])
    p.add_argument("--domain", default="*")
    p.add_argument("--risk", default="LOW")
    p.add_argument("--min-evidence", default="E0")
    p.add_argument("--expires-at")
    p.add_argument("--reason", default="")
    p.add_argument("--can-delegate", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    root = Path(args.path).resolve()

    if args.action in {"status", "check"}:
        trust = trust_doc(root)
        delegations = delegation_doc(root)
        rows = []
        for d in delegations.get("delegations", []) or []:
            row = dict(d)
            until = parse_ts(row.get("expires_at"))
            if row.get("status") == "ACTIVE" and until and until <= now():
                row["status"] = "EXPIRED"
            rows.append(row)
        payload = {"schema_version": SCHEMA_VERSION, "agents": trust.get("agents", []), "delegations": rows}
        if args.action == "check":
            errs: list[str] = []
            for a in payload["agents"]:
                for key in ["id", "status", "capabilities", "max_risk", "min_evidence"]:
                    if key not in a:
                        errs.append(f"AGENT_MISSING_FIELDS:{a.get('id')}:{key}")
                if str(a.get("status", "")) not in {"ACTIVE", "REVOKED", "SUSPENDED"}:
                    errs.append(f"AGENT_INVALID_STATUS:{a.get('id')}")
                if str(a.get("max_risk", "")).upper() not in RISK_ORDER:
                    errs.append(f"AGENT_INVALID_RISK:{a.get('id')}")
            seen: set[str] = set()
            graph: dict[str, list[str]] = {}
            for d in rows:
                did = str(d.get("delegation_id", ""))
                if did in seen:
                    errs.append(f"DUPLICATE_DELEGATION:{did}")
                seen.add(did)
                for key in ["delegation_id", "from_agent", "to_agent", "status", "expires_at"]:
                    if not d.get(key):
                        errs.append(f"DELEGATION_MISSING_FIELDS:{did}:{key}")
                frm = str(d.get("from_agent", "")); to = str(d.get("to_agent", ""))
                if frm == to and frm:
                    errs.append(f"SELF_DELEGATION:{did}")
                if frm and frm not in index_agents(trust):
                    errs.append(f"UNKNOWN_DELEGATOR:{did}:{frm}")
                if to and to not in index_agents(trust):
                    errs.append(f"UNKNOWN_DELEGATEE:{did}:{to}")
                graph.setdefault(frm, []).append(to)
                if parse_ts(d.get("expires_at")) is None:
                    errs.append(f"INVALID_EXPIRY:{did}")
                parent = index_agents(trust).get(frm)
                if parent:
                    ok, why = edge_bounded(parent, d)
                    if str(d.get("status")) == "ACTIVE" and not ok:
                        errs.append(f"DELEGATION_INVALID:{did}:{why}")
            def visit(node: str, trail: tuple[str, ...]) -> None:
                if node in trail:
                    errs.append(f"DELEGATION_CYCLE:{'->'.join(trail + (node,))}")
                    return
                for nxt in graph.get(node, []):
                    visit(nxt, trail + (node,))
            for node in list(graph):
                visit(node, tuple())
            payload["status"] = "PASS" if not errs else "FAIL"
            payload["errors"] = sorted(set(errs))
            rc = 0 if not errs else 1
        else:
            rc = 0
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else yaml.safe_dump(payload, sort_keys=False))
        raise SystemExit(rc)

    if args.action == "evaluate":
        if not args.agent:
            raise SystemExit("--agent is required")
        capability = args.capability[0] if args.capability else "read"
        payload = evaluate(root, args.agent, capability, args.domain, args.risk, args.min_evidence)
        audit(root, {"action": "EVALUATE", "agent": args.agent, "capability": capability, "domain": args.domain, "risk": args.risk, "decision": payload.get("decision")})
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else f"{payload.get('decision')} {payload.get('reason')}")
        raise SystemExit(0 if payload.get("decision") == "AUTHORIZED" else 1)

    if args.action == "delegate":
        required = [args.from_agent, args.to_agent, args.delegation_id, args.expires_at]
        if not all(required) or not args.capability:
            raise SystemExit("--from-agent, --to-agent, --delegation-id, --expires-at, and --capability are required")
        trust = trust_doc(root)
        agents = index_agents(trust)
        if args.from_agent not in agents or args.to_agent not in agents:
            raise SystemExit("DELEGATOR_AND_DELEGATEE_MUST_BE_REGISTERED")
        source = agents[args.from_agent]; target = agents[args.to_agent]
        if str(source.get("status", "ACTIVE")) != "ACTIVE":
            raise SystemExit("DELEGATOR_NOT_ACTIVE")
        if not bool(source.get("can_delegate", False)):
            raise SystemExit("DELEGATOR_NOT_AUTHORIZED_TO_DELEGATE")
        if str(target.get("status", "ACTIVE")) != "ACTIVE":
            raise SystemExit("DELEGATEE_NOT_ACTIVE")
        expires = parse_ts(args.expires_at)
        if not expires or expires <= now():
            raise SystemExit("expires_at must be a future timestamp")
        for cap in args.capability:
            decision = evaluate(root, args.from_agent, cap, args.domain, args.risk, args.min_evidence)
            if decision.get("decision") != "AUTHORIZED":
                raise SystemExit(f"Delegation denied: {decision.get('reason')}")
        doc = delegation_doc(root)
        if any(str(d.get("delegation_id")) == args.delegation_id for d in doc.get("delegations", []) or []):
            raise SystemExit("DELEGATION_ID_EXISTS")
        row = {
            "delegation_id": args.delegation_id,
            "from_agent": args.from_agent,
            "to_agent": args.to_agent,
            "capabilities": args.capability,
            "domains": [args.domain],
            "max_risk": args.risk.upper(),
            "min_evidence": args.min_evidence.upper(),
            "can_delegate": bool(args.can_delegate),
            "expires_at": args.expires_at,
            "status": "ACTIVE",
            "reason": args.reason,
            "created_at": iso(),
        }
        doc.setdefault("delegations", []).append(row)
        (root / DELEGATIONS).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        audit(root, {"action": "DELEGATE", "delegation_id": args.delegation_id, "from_agent": args.from_agent, "to_agent": args.to_agent})
        print(yaml.safe_dump(row, sort_keys=False))
        return

    if args.action == "revoke":
        if not args.delegation_id:
            raise SystemExit("--delegation-id is required")
        doc = delegation_doc(root)
        found = False
        for d in doc.get("delegations", []) or []:
            if str(d.get("delegation_id")) == args.delegation_id:
                d["status"] = "REVOKED"
                d["revoked_at"] = iso()
                found = True
        if not found:
            raise SystemExit("DELEGATION_NOT_FOUND")
        (root / DELEGATIONS).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        audit(root, {"action": "REVOKE", "delegation_id": args.delegation_id})
        print(f"REVOKED {args.delegation_id}")
        return


if __name__ == "__main__":
    main()
