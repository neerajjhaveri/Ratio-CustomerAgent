"""Plugin: normalize_entity_mapping_tool

Extracted from tools.py into a standalone plugin module.
Entry point: run(entity_mapping, user_ask) -> JSON string.
"""
from __future__ import annotations
import json, logging, os
from core.mcp_app import LOCAL_DATASETS_DIR
from helper.normalize_entity_mapping import normalize_entity_mapping, build_variant_maps
from registry.resources import servicename_synonyms, offering_synonyms, region_synonyms

logger = logging.getLogger("ratio_mcp")


def _resolve_resource(res_fn):
    """Call a resource loader function and return the data dict."""
    if res_fn is None:
        return {}
    try:
        if callable(res_fn):
            return res_fn()
    except Exception as e:
        logger.debug("_resolve_resource failure: %s", e)
    return {}


async def run(entity_mapping: dict, user_ask: str) -> str:
    """Normalize entity mapping fields (ServiceName, Offering, Region) using synonym datasets."""
    try:
        if not isinstance(entity_mapping, dict):
            return json.dumps({"error": "entity_mapping must be a dict"})
        if not isinstance(user_ask, str):
            return json.dumps({"error": "user_ask must be a string"})

        service_raw = _resolve_resource(servicename_synonyms)
        offering_raw = _resolve_resource(offering_synonyms)
        region_raw = _resolve_resource(region_synonyms)

        service_block = service_raw.get("ServiceNameSynonyms") if isinstance(service_raw, dict) else None
        offering_block = offering_raw.get("OfferingSynonyms") if isinstance(offering_raw, dict) else None
        region_block = region_raw.get("RegionSynonyms") if isinstance(region_raw, dict) else None

        # Fallback: load directly from local datasets if resource resolution failed
        if not (service_block and offering_block and region_block):
            datasets_dir = LOCAL_DATASETS_DIR
            if not service_block:
                f = os.path.join(datasets_dir, "ServiceNameSynonyms.json")
                if os.path.exists(f):
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    service_block = data.get("ServiceNameSynonyms") if isinstance(data, dict) else service_block
            if not offering_block:
                f = os.path.join(datasets_dir, "OfferingSynonyms.json")
                if os.path.exists(f):
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    offering_block = data.get("OfferingSynonyms") if isinstance(data, dict) else offering_block
            if not region_block:
                f = os.path.join(datasets_dir, "RegionSynonyms.json")
                if os.path.exists(f):
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    region_block = data.get("RegionSynonyms") if isinstance(data, dict) else region_block

        variant_maps = build_variant_maps(service_block, offering_block, region_block)
        result = normalize_entity_mapping(entity_mapping, user_ask, variant_maps=variant_maps)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("normalize_entity_mapping plugin failed: %s", e, exc_info=True)
        return json.dumps({"error": str(e)})
