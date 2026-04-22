# Moved from src/normalize_entity_mapping.py
from typing import Dict, List, Any, Optional, Tuple
import re
_processed_cache: Dict[str, Dict[str, Dict[str, str]]] = {}

def _process_synonyms(raw_block: Dict[str, List[str]]) -> Dict[str, str]:
    vt_map: Dict[str, str] = {}
    for canonical, variants in raw_block.items():
        if not isinstance(canonical, str): continue
        variant_list = [v for v in (variants or []) if isinstance(v, str)]
        vt_map.setdefault(canonical.lower(), canonical)
        for v in variant_list: vt_map.setdefault(v.lower(), canonical)
    return vt_map

def build_variant_maps(service_synonyms: Dict[str, List[str]] | None, offering_synonyms: Dict[str, List[str]] | None, region_synonyms: Dict[str, List[str]] | None) -> Dict[str, Dict[str, str]]:
    cache_key = f"svc:{id(service_synonyms)}|off:{id(offering_synonyms)}|reg:{id(region_synonyms)}"
    if cache_key in _processed_cache: return _processed_cache[cache_key]
    result: Dict[str, Dict[str, str]] = {}
    if isinstance(service_synonyms, dict): result['servicename'] = _process_synonyms(service_synonyms)
    if isinstance(offering_synonyms, dict): result['offering'] = _process_synonyms(offering_synonyms)
    if isinstance(region_synonyms, dict): result['region'] = _process_synonyms(region_synonyms)
    _processed_cache[cache_key] = result; return result

def _coerce_list(val: Any) -> List[str]:
    if val is None: return []
    if isinstance(val, str): return [val]
    if isinstance(val, (list, tuple, set)): return [v for v in val if isinstance(v, str)]
    return []

def normalize_entity_mapping(entity_mapping: Dict[str, Any], user_ask: str, variant_maps: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Any]:
    vt_all = variant_maps or {}
    normalized: Dict[str, List[str]] = {}; replacement_spans: List[Tuple[int,int,str]] = []
    key_aliases = {"region": "Region", "regions": "Region", "regionname": "Region", "servicename": "ServiceName", "servicenames": "ServiceName", "service": "ServiceName", "services": "ServiceName", "offering": "Offering", "offerings": "Offering", "customer": "CustomerName", "customers": "CustomerName", "customername": "CustomerName", "customernames": "CustomerName"}
    offering_context = bool(re.search(r"\boffering(s)?\b", user_ask, re.IGNORECASE))
    for raw_entity_type, raw_vals in entity_mapping.items():
        if not isinstance(raw_entity_type, str): continue
        etype_lower = raw_entity_type.strip().lower();
        if not etype_lower: continue
        canonical_type_key = key_aliases.get(etype_lower, raw_entity_type)
        if not offering_context and canonical_type_key == "Offering": canonical_type_key = "ServiceName"
        service_map = vt_all.get("servicename", {}); offering_map = vt_all.get("offering", {})
        vt_map_default = vt_all.get(canonical_type_key.lower(), {}) or (service_map if canonical_type_key == "ServiceName" else {})
        values = _coerce_list(raw_vals); per_type: Dict[str, List[str]] = {}
        for v in values:
            v_clean = v.strip();
            if not v_clean: continue
            use_type = canonical_type_key; vt_map_current = vt_map_default
            if offering_context and canonical_type_key.lower() == "servicename" and v_clean.lower() in offering_map:
                use_type = "Offering"; vt_map_current = offering_map
            canonical = vt_map_current.get(v_clean.lower(), v_clean)
            per_type.setdefault(use_type, []).append(canonical)
            if canonical.lower() != v_clean.lower():
                pattern = re.compile(rf"\b{re.escape(v_clean)}\b", re.IGNORECASE)
                for m in pattern.finditer(user_ask): replacement_spans.append((m.start(), m.end(), canonical))
        for tkey, collected in per_type.items():
            seen = set(); deduped: List[str] = []
            for item in collected:
                low = item.lower();
                if low in seen: continue
                seen.add(low); deduped.append(item)
            if deduped: normalized[tkey] = deduped
    replacement_spans.sort(key=lambda x: (x[0], -(x[1]-x[0]))); selected: List[Tuple[int,int,str]] = []; last_end = -1
    for s,e,repl in replacement_spans:
        if s < last_end: continue
        selected.append((s,e,repl)); last_end = e
    rewritten = user_ask
    for s,e,repl in sorted(selected, key=lambda t: t[0], reverse=True): rewritten = rewritten[:s] + repl + rewritten[e:]
    if not offering_context:
        service_arr_preview = normalized.get("ServiceName", [])
        for cname in service_arr_preview:
            pat = re.compile(rf"(?i)(?<!\bservice\s)\b{re.escape(cname)}\b")
            rewritten = pat.sub(lambda m: f"service {cname}", rewritten)
        all_service_canonicals = set(vt_all.get("servicename", {}).values())
        for cname in all_service_canonicals:
            if cname in service_arr_preview: continue
            if re.search(rf"(?i)\b{re.escape(cname)}\b", rewritten) and not re.search(rf"(?i)\bservice\s+{re.escape(cname)}\b", rewritten):
                rewritten = re.sub(rf"(?i)\b{re.escape(cname)}\b", f"Service {cname}", rewritten)
    else:
        all_offering_tokens = set(normalized.get("Offering", [])); all_service_tokens = set(normalized.get("ServiceName", []))
        for tset in (all_offering_tokens, all_service_tokens):
            for token in list(tset):
                pattern_plain = re.compile(rf"(?i)(?<!\boffering\s)\b{re.escape(token)}\b")
                rewritten = pattern_plain.sub(lambda m: f"offering {token}", rewritten)

    # Final uniform prefix enforcement (idempotent) for clarity:
    # Every ServiceName token should be prefixed with exact lowercase 'service ' and Offering with 'offering '.
    # We operate on canonical lists to avoid over-prefixing inside already prefixed phrases.
    for svc in normalized.get("ServiceName", []):
        rewritten = re.sub(rf"(?i)(?<!\bservice\s)\b{re.escape(svc)}\b", f"service {svc}", rewritten)
    for off in normalized.get("Offering", []):
        rewritten = re.sub(rf"(?i)(?<!\boffering\s)\b{re.escape(off)}\b", f"offering {off}", rewritten)


    region_arr = normalized.get("Region", []); 
    service_arr = normalized.get("ServiceName", []); 
    offering_arr = normalized.get("Offering", []); 
    customer_arr = normalized.get("CustomerName", [])
    return {"RegionName": region_arr, 
            "ServiceName": service_arr, 
            "Offering": offering_arr, 
            "CustomerName": customer_arr, 
            "RewrittenAsk": rewritten, 
            "normalized_entity_mapping": normalized
            }

__all__ = ["normalize_entity_mapping", "build_variant_maps"]
