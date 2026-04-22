import re, json, sys
from typing import List, Dict, Set

SERVICE_NAMES = [
    "Azure Portal IaaS Experiences",
"CDN Management Service",
"Xstore",
"ESTS",
"Azure Resource Manager",
"Fabric Platform Shared Services",
"Azure Monitor",
"Service Bus",
"AzDev-Team Foundation Service",
"ScaleSet Platform and Solution",
"Azure Alerts Control Plane",
"Azure Virtual Desktop",
"Azure MFA",
"Managed Service Identity",
"CoreWAN",
"Azure Monitor Metrics",
"SQL Availability and GeoDR",
"Microsoft Intune",
"Azure Kubernetes Service",
"Azure Key Vault",
"Azure Frontdoor"
]

STOPWORDS = {"a","an","and","for","of","the","to","in","on"}

def normalize_spaces(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip())

def acronym(s: str) -> str:
    tokens = re.split(r'[\s\-/]+', re.sub(r'[()]+',' ', s))
    letters = [t[0] for t in tokens if t and t.lower() not in STOPWORDS and re.search('[A-Za-z0-9]', t)]
    ac = ''.join(letters)
    return ac if len(ac) >= 2 else ""

def extract_parenthetical(s: str) -> List[str]:
    return re.findall(r'\(([^)]+)\)', s)

def strip_parentheticals(s: str) -> str:
    return normalize_spaces(re.sub(r'\([^)]*\)', ' ', s))

def hyphen_variants(s: str) -> Set[str]:
    base = strip_parentheticals(s)
    collapsed = re.sub(r'[\s_]+', '-', base)
    spaced = base
    return {collapsed.lower(), spaced.lower()}

def service_variants(name: str) -> List[str]:
    variants: Set[str] = set()
    canonical_clean = strip_parentheticals(name)
    lower_canonical = canonical_clean.lower()
    variants.add(lower_canonical)

    # Remove leading 'azure '
    if lower_canonical.startswith("azure "):
        variants.add(lower_canonical.replace("azure ", "", 1))

    # If ends with ' service' add version without it
    if lower_canonical.endswith(" service"):
        variants.add(lower_canonical.rsplit(" service",1)[0])

    # Replace 'service' -> 'svc'
    if " service" in lower_canonical:
        variants.add(lower_canonical.replace(" service", " svc"))
    variants.add(lower_canonical.replace(" service ", " svc "))

    # Replace ' services' -> ' svc'
    if " services" in lower_canonical:
        variants.add(lower_canonical.replace(" services", " svc"))

    # 'platform and solution' -> shorten
    variants.add(lower_canonical.replace(" platform and solution", " platform"))
    variants.add(lower_canonical.replace(" platform and solution", ""))

    # Parenthetical content
    for p in extract_parenthetical(name):
        pl = p.lower()
        variants.add(pl)
        if ' ' in pl:
            variants.add(pl.replace(' ', ''))
        # common uppercase acronym form
        ac = acronym(pl)
        if ac:
            variants.add(ac.lower())

    # Acronym of full phrase
    ac_full = acronym(name)
    if ac_full:
        variants.add(ac_full.lower())

    # Hyphenation / collapsed
    variants |= hyphen_variants(name)

    # Remove punctuation variants
    clean_extra = re.sub(r'[^a-zA-Z0-9\s-]', ' ', lower_canonical)
    variants.add(normalize_spaces(clean_extra))

    # Special replacements
    variants = {v.replace("datacenter", "dc") for v in variants}
    variants = {v.replace("database migration service", "dms") for v in variants}
    variants = {v.replace("managed grafana", "grafana") for v in variants}
    variants = {v.replace("bot service", "bot") for v in variants}
    variants = {v.replace("resource manager", "arm") for v in variants}
    variants = {v.replace("mfa", "multi factor auth") if v == "azure mfa" else v for v in variants}

    # Clean up
    cleaned = []
    canonical_norm = lower_canonical
    for v in variants:
        vv = normalize_spaces(v)
        if vv and vv != canonical_norm:
            cleaned.append(vv)
    # Deduplicate with order stable-ish
    seen = set()
    ordered = []
    for v in sorted(cleaned, key=len):
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered[:25]  # cap to avoid explosion

def build_service_synonyms(service_names: List[str]) -> Dict[str, List[str]]:
    out = {}
    for s in service_names:
        out[s] = service_variants(s)
    return out

if __name__ == "__main__":
    mapping = build_service_synonyms(SERVICE_NAMES)
    json.dump({"ServiceNameSynonyms": mapping}, sys.stdout, indent=2, ensure_ascii=False)