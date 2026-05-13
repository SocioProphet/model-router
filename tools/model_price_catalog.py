#!/usr/bin/env python3
"""Governed model price catalog helpers for model-router."""

from __future__ import annotations

from typing import Any


class PriceCatalogError(Exception):
    """Raised when a price catalog cannot price a lane."""


def _by_lane(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for lane in catalog.get("lanes", []):
        lane_id = str(lane.get("laneId", ""))
        if lane_id:
            result[lane_id] = lane
    return result


def _default_profile(lane_doc: dict[str, Any]) -> dict[str, Any]:
    default_ref = lane_doc.get("defaultProfileRef")
    profiles = lane_doc.get("profiles", [])
    for profile in profiles:
        if profile.get("profileRef") == default_ref:
            return profile
    if profiles:
        return profiles[0]
    raise PriceCatalogError(f"lane has no pricing profiles: {lane_doc.get('laneId')}")


def estimate_lane_cost(catalog: dict[str, Any], lane: str, resources: dict[str, Any]) -> dict[str, Any]:
    """Estimate lane cost from governed price catalog and resource estimates."""

    override = resources.get("estimatedLaneCosts", {})
    if isinstance(override, dict) and lane in override:
        value = round(float(override[lane]), 6)
        return {
            "estimatedCost": value,
            "catalogId": catalog.get("catalogId"),
            "currency": catalog.get("currency", "USD"),
            "costModel": "external-override",
            "profileRef": "resource-estimatedLaneCosts",
            "providerRef": "resource-override",
            "modelRef": lane,
            "components": {"override": value},
        }

    lane_doc = _by_lane(catalog).get(lane)
    if lane_doc is None:
        raise PriceCatalogError(f"missing price catalog lane: {lane}")

    profile = _default_profile(lane_doc)
    pricing = profile.get("pricing", {})
    cost_model = lane_doc.get("costModel")

    input_tokens = float(resources.get("estimatedInputTokens", 0))
    output_tokens = float(resources.get("estimatedOutputTokens", 0))
    cache_tokens = float(resources.get("estimatedCacheReadTokens", 0))
    tool_calls = float(resources.get("estimatedToolCalls", 0))
    runtime_minutes = float(resources.get("estimatedLocalRuntimeMinutes", 0))
    energy_minutes = float(resources.get("estimatedLocalEnergyMinutes", runtime_minutes))

    request_base = float(pricing.get("requestBaseCost", 0))
    input_cost = input_tokens * float(pricing.get("inputPerMillion", 0)) / 1_000_000
    output_cost = output_tokens * float(pricing.get("outputPerMillion", 0)) / 1_000_000
    cache_cost = cache_tokens * float(pricing.get("cacheReadPerMillion", 0)) / 1_000_000
    tool_cost = tool_calls * float(pricing.get("toolCallCost", 0))
    runtime_cost = runtime_minutes * float(pricing.get("localRuntimeCostPerMinute", 0))
    energy_cost = energy_minutes * float(pricing.get("localEnergyCostPerMinute", 0))
    min_cost = float(pricing.get("minCost", 0))

    if cost_model == "none":
        total = 0.0
    else:
        total = request_base + input_cost + output_cost + cache_cost + tool_cost + runtime_cost + energy_cost
        total = max(total, min_cost)

    return {
        "estimatedCost": round(total, 6),
        "catalogId": catalog.get("catalogId"),
        "currency": catalog.get("currency", "USD"),
        "costModel": cost_model,
        "profileRef": profile.get("profileRef"),
        "providerRef": profile.get("providerRef"),
        "modelRef": profile.get("modelRef"),
        "components": {
            "requestBase": round(request_base, 6),
            "input": round(input_cost, 6),
            "output": round(output_cost, 6),
            "cacheRead": round(cache_cost, 6),
            "toolCalls": round(tool_cost, 6),
            "localRuntime": round(runtime_cost, 6),
            "localEnergy": round(energy_cost, 6),
            "minCost": round(min_cost, 6),
        },
    }


def price_catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "catalogId": catalog.get("catalogId"),
        "currency": catalog.get("currency", "USD"),
        "effectiveAt": catalog.get("effectiveAt"),
    }
