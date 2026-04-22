import re, json, sys

REGIONS = [
    "usnatwest","ussecwest","uksouth","japanwest","northeurope","usseccentral","eastus2euap",
    "chinaeast2","usdodeast","usgoviowa","usdodsouthcentral","uaecentral","norwaywest",
    "swedensouth","indonesiacentral","koreasouth2","southcentralus","newzealandnorth",
    "austriaeast","malaysiawest","jioindiacentral","eastusslv","deloscloudgermanynorth",
    "israelnorthwest","jioindiawest","israelcentral","indiasouthcentral","australiacentral",
    "switzerlandwest","canadaeast","eastus2","uknorth","eastusstg","chinanorth2","eastasia",
    "centralus","usgovvirginia","koreacentral","francesouth","swedencentral","usgovwyoming",
    "francecentral","ussecwestcentral","germanynorth","westus","northcentralus","mexicocentral",
    "australiasoutheast","southcentralusstg","polandcentral","apacsoutheast2","westus2","ukwest",
    "westeurope","australiacentral2","usdodcentral","usgovtexas","usgovarizona","belgiumcentral",
    "germanycentral","centraluseuap","chinaeast","chilecentral","chinaeast3","germanywestcentral",
    "singaporegov","chinanorth10","italynorth","brazilnortheast","taiwannorth","taiwannorthwest",
    "westcentralus","bleufrancesouth","westindia","denmarkeast","koreasouth","australiaeast",
    "southafricanorth","germanynortheast","ocave","southeastasia","southafricawest","brazilsouth",
    "canadacentral","uksouth2","bleufrancecentral","westus3","usdodsouthwest","chinanorth3",
    "centralindia","southindia","eastus","malaysiasouth","northeurope2","brazilsoutheast",
    "norwayeast","qatarcentral","easteurope","switzerlandnorth","usdodwestcentral","arlem",
    "uaenorth","japaneast","chilenorthcentral","usseceast","usnateast","spaincentral",
    "finlandcentral","deloscloudgermanycentral","chinanorth","global"
]

def split_region(r: str):
    # heuristic splits between letter→digit and direction boundaries
    parts = re.findall(r'[a-zA-Z]+|\d+', r)
    return parts

def make_variants(canonical: str):
    parts = split_region(canonical)
    base = canonical
    variants = set()
    variants.add(base)
    # spaced
    variants.add(" ".join(parts))
    # hyphenated
    variants.add("-".join(parts))
    # insert hyphen before trailing digit clusters e.g. eastus2 -> eastus-2, east-us-2
    if re.search(r'\d', canonical):
        letter_part = re.sub(r'\d+$', '', canonical)
        digit_part = canonical[len(letter_part):]
        if letter_part and digit_part:
            variants.add(f"{letter_part}-{digit_part}")
            # further split letter part into directional tokens if possible
            letter_tokens = re.findall(r'(north|south|east|west|central|india|japan|korea|france|germany|brazil|taiwan|china|australia|canada|usgov|usdod|ussec|usnat|deloscloudgermany|sweden|norway|italy|poland|qatar|spain|switzerland|belgium|chile|uae|israel|jioindia|malaysia|newzealand|indonesia|austria|mexico|brazil|southafrica|singapore|finland|arlem|global)', letter_part)
            if letter_tokens:
                variants.add("-".join(letter_tokens + [digit_part]))
                variants.add(" ".join(letter_tokens + [digit_part]))
    # convert some compound directions (southcentralus -> south central us)
    variants.add(re.sub(r'(north|south|east|west|central)', r' \1', canonical).strip().replace("  ", " "))
    # replace 'us' prefix forms (usgovvirginia -> us gov virginia)
    variants.add(canonical.replace("usgov", "us gov").replace("usdod", "us dod").replace("ussec", "us sec").replace("usnat","us nat"))
    # remove repeating spaces / unify
    cleaned = {re.sub(r'\s+', ' ', v).strip() for v in variants if len(v) <= 40}
    # drop canonical duplicate
    cleaned.discard(canonical)
    return sorted(cleaned)

def build_mapping():
    mapping = {}
    for r in REGIONS:
        mapping[r] = make_variants(r)
    return mapping

if __name__ == "__main__":
    mapping = build_mapping()
    json.dump({"RegionSynonyms": mapping}, sys.stdout, indent=2)