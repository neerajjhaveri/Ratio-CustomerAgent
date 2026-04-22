import re, json, sys
from typing import List, Dict, Set

OFFERING_NAMES = [
    "1esdevbox","1espaes","1esresourcemanagement","aadmidtierqueryservice","aadsyncfabric","acropolis",
    "actiongroups","activitylogs&alerts","adrs","afdplatform","afoinetworkcloud","aibuilderunstructuredml",
    "aiopshealthplatform","anvil","apimanagement","applicationgateway","applicationinsights","appservice",
    "appservice\\staticwebapps","arcuserexperiences","automation","azdevacquisitionexperience","azdevanalytics",
    "azdevartifacts","azdevazchatops","azdevblobstore","azdevfeeds","azdevmasterpartitioningservice",
    "azdevsharedplatformservices","azdevtestcasemanagement","azdevtoken","azdevuser","azswift","azureactivedirectory",
    "azurealertscontrolplane","azureanalysisservices","azurearcenabledkubernetes","azureauthzdataplane","azurebastion",
    "azurebatch","azurebotservice","azurecertificateservice","azurechaosstudio","azurechaosstudioagentservice",
    "azurecommunicationservices","azurecomputeartifacts","azurecontainerapps","azurecontainerinstances",
    "azurecontainernetworking","azurecorequalityengineering","azurecosmosdb","azuredatabaseformariadb",
    "azuredatabaseformysql","azuredatabaseformysqlflexibleservers","azuredatabaseforpostgresql",
    "azuredatabaseforpostgresqlflexibleservers","azuredatabasemigrationservice","azuredatabricks","azuredataexplorer",
    "azuredatamanagerforenergy","azuredeployments","azuredeviceprovisioningservice","azuredevops","azuredevopsserver",
    "azuredigitaltwins","azuredirectdrive","azurednsprivateresolver","azurednspubliczones","azurefirewall",
    "azurefrontdoor","azurehardwaredatacentermanager","azurehealthdataservices","azurehostagent","azureiothub",
    "azurekubernetesservice(aks)","azureloadtesting","azuremanagedgrafana","azuremaps","azuremigrate","azuremonitor",
    "azuremonitorcontrolservice","azuremonitoressentials","azuremonitormetrics","azuremonitorworkspacedataplanefrontdoor",
    "azurenetappfiles","azureopenaiservice","azurepolicy","azureportalframework(ibizafx)",
    "azureportalintelligentexperiences","azureprivilegedidentitymanagement","azureresourcegraph","azureresourcemanager",
    "azuresearch","azuresentinel","azureservicemanager","azuresignalrservice","azurespheresecuritysvcgen1","azurestack",
    "azurestackhci","azuresynapseanalytics","azuresynapsejobservice","azuresynapseplatformservice",
    "azurethrottlingsolutions","backup","billingservice","brain","brainml","buildmediainazure",
    "businessapplicationplatform","cdn","cirrus","cloudbuild","cloudshell","cloudtest",
    "cognitiveserviceformrecognizer","cognitiveservices","cognitiveservicescomputervisionapi",
    "cognitiveservicestextanalyticsapi","computeresourceprovider","connectormanagementservice","containerinsights",
    "containerregistry","conversationconductor","copilotstudioplatformextensibility","copilotstudioruntime",
    "coreservicesmicroservicesinfrastructure","cosmicplatform","costmanagement","costmanagementactionableexperiences",
    "cpim","cpimsts","credentialsmanagementux","crmbackgroundtaskservicessync","datafactory","desktopflowsruntimeservice",
    "devcenter","devdivaiservices","devdivdatainfraprocessingdatax","diskresourceprovider","dnsservingplane","dsms",
    "dynamics365dataversesearch","dynamics365filestoreservice","engineeringhub","eventgrid","eventhubs",
    "expressroute\\expressroutecircuits","expressroute\\expressroutegateways","fabriccontrollerfundamentalservices",
    "fabricnetworkdevices","fabricplatformsharedservices","functions","genevadatatransport","genevadiagnosticspipeline",
    "guestagentvmextensions","hdinsight","hybridresourceprovider","iamusersandtenants","icmincidentmanagementservice",
    "identitydiagnostics","idxreportingandauditinsights","incidentautomation","interflow","iotcentral","jarvis","keyvault",
    "loadbalancer","loganalytics","logicapps","m365experimentationandconfigurationecs","machinelearningservices",
    "managedserviceidentity","mdesignaturerelease","mdm","mediaservices","microsoftazureportal",
    "microsoftcopilotforsecurity","microsoftentraconnecthealth","microsoftgraph","microsoftinformationprotection",
    "microsoftintune","mipplatformservices","multi-factorauthentication","networkinfrastructure","networkresourceprovider",
    "networkservicemanager","networkwatcher","notificationhubs","observabilityingestionservices",
    "observabilitypipelinedeliveryservices","onebranchservices","onedeployazdeployer","onedeploybuilderandstorage",
    "onedriveconsumer","onedrivesharepoint","onefleetnode","onepubsub","overlakeengineeringsystem","perforce","pilotfish",
    "plannedmaintenance","plexinfrastructure","policyadministrationservice","powerautomatecopilot","powerautomateportal",
    "powerautomaterp","powerplatformconnectors","programmabilityservices","projectviennaservices","qualitytestservice",
    "rdos","rediscache","redisenterprise","regionalservicemanager","scalesetplatformandsolution","sdnpubsubservice",
    "securityplatform(purview)","selfservicegroupmanagement","sentinelus","servicebus","servicefabric","servicemap",
    "siterecovery","skyperegistrar","sourcedepot","sparesinventory","spartandataplatformmanagement","speechservices",
    "sqlbackuprestore","sqlblue","sqlconnectivity","sqlcontrolplane","sqldatabase","sqlmanagedinstance","sqlsecurity",
    "sqlstorageengine","srp","storage","streamanalytics","sxgmsaascaseservice","teamsauthservice",
    "teamsverticalseasyapprovals","terrapin","translator","tridentdwsqllakeplatform","trustedlaunch",
    "tssesrpfabricandplatformservices","tsspkiesrp","universalstorepurchase","usxthreatintelligence","videoindexer",
    "virtualmachines","virtualnetwork","vpn","watm","webdefenseservice","windowsvirtualdesktop","xinvestigator"
]

STOP = {"and","for","of","the","in","on","with","to","a","an"}

def tokens(raw: str):
    # split on non-alphanum + camel + slash/backslash
    interim = re.sub(r'[\\/]', ' ', raw)
    # insert space before capitals (rare here)
    interim = re.sub(r'([a-z])([A-Z])', r'\1 \2', interim)
    # split special connectors
    parts = re.split(r'[^a-zA-Z0-9]+', interim)
    return [p for p in parts if p]

def acronym(parts: List[str]):
    letters = [p[0] for p in parts if p.lower() not in STOP]
    ac = "".join(letters)
    return ac if len(ac) >= 3 else ""

def base_variants(name: str) -> Set[str]:
    v = set()
    v.add(name)  # canonical (lowercase)
    v.add(name.replace('-', ''))
    v.add(name.replace('-', ' '))
    v.add(name.replace('_',' '))
    if '\\' in name or '/' in name:
        segs = re.split(r'[\\/]+', name)
        v.update(segs)
        v.add(" ".join(segs))
    # & replacement
    if '&' in name:
        v.add(name.replace('&',' and '))
        v.add(name.replace('&','and'))
    # parentheses removal
    no_paren = re.sub(r'\([^)]*\)', '', name)
    v.add(no_paren)
    # drop common prefixes
    for pref in ("azure","microsoft"):
        if name.startswith(pref):
            v.add(name[len(pref):])
    return {re.sub(r'\s+',' ',x).strip() for x in v if x.strip()}

def smart_shorten(name: str) -> Set[str]:
    short = set()
    # specific known expansions
    mappings = {
        "analysisservices":"as",
        "apimanagement":"apim",
        "applicationgateway":"appgw",
        "applicationinsights":"appi",
        "containerregistry":"acr",
        "azurecontainerregistry":"acr",
        "eventhubs":"eh",
        "expressroute":"er",
        "keyvault":"kv",
        "kubernetesservice":"aks",
        "loadbalancer":"lb",
        "logicapps":"la",
        "loganalytics":"la-workspace",
        "machinelearningservices":"ml",
        "managedserviceidentity":"msi",
        "mediaservices":"ams",
        "networkwatcher":"nw",
        "notificationhubs":"nh",
        "servicefabric":"sf",
        "servicebus":"sb",
        "sqlmanagedinstance":"sqlmi",
        "virtualmachines":"vm",
        "virtualnetwork":"vnet",
        "windowsvirtualdesktop":"wvd",
        "storage":"stg",
        "streamanalytics":"asa",
        "webdefenseservice":"waf"
    }
    for k, v in mappings.items():
        if k in name:
            short.add(v)
    return short

def gen_synonyms(name: str) -> List[str]:
    name = name.strip().lower()
    parts = tokens(name)
    vars = base_variants(name)
    # join tokens with space and hyphen
    vars.add(" ".join(parts))
    vars.add("-".join(parts))
    # acronym
    ac = acronym(parts)
    if ac:
        vars.add(ac.lower())
    # shortenings
    vars |= smart_shorten(name)
    # remove canonical exact
    vars.discard(name)
    # clean
    cleaned = []
    seen = set()
    for v in sorted(vars, key=lambda x:(len(x), x)):
        vv = re.sub(r'\s+',' ',v).strip()
        if not vv or vv==name or vv in seen:
            continue
        seen.add(vv)
        cleaned.append(vv)
    return cleaned[:20]  # cap

def build():
    out = {}
    for o in OFFERING_NAMES:
        out[o] = gen_synonyms(o)
    return out

if __name__ == "__main__":
    json.dump({"OfferingSynonyms": build()}, sys.stdout, indent=2)