"""Map management API routes."""

from __future__ import annotations

import json
import os
import sys

from flask import Blueprint, jsonify, request

# Allow importing local_data from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import local_data

map_bp = Blueprint("map", __name__, url_prefix="/api/maps")


@map_bp.route("", methods=["GET"])
def get_maps():
    """Return all maps (without bosses for the list view)."""
    locations = local_data.load_map_locations()
    result = []
    for loc in locations:
        red_count = sum(1 for b in loc.bosses if b.bossType == 1)
        golden_count = sum(1 for b in loc.bosses if b.bossType == 2)
        result.append({
            "id": loc.id,
            "mapId": loc.mapId,
            "name": loc.name,
            "totalChannel": loc.totalChannel,
            "bossCount": len(loc.bosses),
            "redCount": red_count,
            "goldenCount": golden_count,
        })
    return jsonify(result)


@map_bp.route("", methods=["POST"])
def create_map():
    """Create a new map."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    map_id = (data.get("mapId") or "").strip()
    name = (data.get("name") or "").strip()
    total_channel = int(data.get("totalChannel", 0))

    if not map_id or not name:
        return jsonify({"error": "mapId and name are required"}), 400

    locations = local_data.load_map_locations()

    # Check for duplicate mapId
    for loc in locations:
        if loc.mapId == map_id:
            return jsonify({"error": f"Map '{map_id}' already exists"}), 409

    # Auto-generate next map ID
    max_id = max((loc.id for loc in locations), default=0)
    new_id = max_id + 1

    new_map = local_data.MapLocation(
        id=new_id,
        mapId=map_id,
        name=name,
        totalChannel=total_channel,
        bosses=[],
    )
    locations.append(new_map)
    local_data.save_map_locations(locations)

    return jsonify({"id": new_id, "mapId": map_id, "message": "Map created"}), 201


@map_bp.route("/<map_id>/bosses", methods=["GET"])
def get_bosses(map_id: str):
    """Return all bosses for a given map."""
    locations = local_data.load_map_locations()
    for loc in locations:
        if loc.mapId == map_id:
            bosses = []
            for b in loc.bosses:
                bosses.append({
                    "id": b.id,
                    "name": b.name,
                    "coordX": b.coordX,
                    "coordY": b.coordY,
                    "bossType": b.bossType,
                    "durationToRevive": b.durationToRevive,
                    "mapId": b.mapId,
                })
            return jsonify(bosses)
    return jsonify({"error": "Map not found"}), 404


@map_bp.route("/<map_id>/bosses", methods=["POST"])
def create_boss(map_id: str):
    """Create a new boss in a map."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    locations = local_data.load_map_locations()
    target = None
    for loc in locations:
        if loc.mapId == map_id:
            target = loc
            break

    if target is None:
        return jsonify({"error": "Map not found"}), 404

    # Auto-generate next boss ID across all maps
    max_id = 0
    for loc in locations:
        for b in loc.bosses:
            if b.id > max_id:
                max_id = b.id
    new_id = max_id + 1

    boss = local_data.BossDto(
        id=new_id,
        name=data.get("name", ""),
        coordX=int(data.get("coordX", 0)),
        coordY=int(data.get("coordY", 0)),
        bossType=int(data.get("bossType", 1)),
        durationToRevive=int(data.get("durationToRevive", 0)),
        mapId=map_id,
    )
    target.bosses.append(boss)
    local_data.save_map_locations(locations)

    return jsonify({"id": new_id, "message": "Boss created"}), 201


@map_bp.route("/<map_id>/bosses/<int:boss_id>", methods=["PUT"])
def update_boss(map_id: str, boss_id: int):
    """Update an existing boss.

    Only name, coordX, coordY, bossType, durationToRevive are updatable.
    Only name, coordX, coordY, bossType, durationToRevive are updatable.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    # Coerce numeric fields before passing to the atomic updater
    coerced: dict = {}
    if "name" in data:
        coerced["name"] = data["name"]
    if "coordX" in data:
        coerced["coordX"] = int(data["coordX"])
    if "coordY" in data:
        coerced["coordY"] = int(data["coordY"])
    if "bossType" in data:
        coerced["bossType"] = int(data["bossType"])
    if "durationToRevive" in data:
        coerced["durationToRevive"] = int(data["durationToRevive"])

    if local_data.update_boss_fields(map_id, boss_id, coerced):
        return jsonify({"message": "Boss updated"})
    return jsonify({"error": "Boss or map not found"}), 404


@map_bp.route("/<map_id>/bosses/<int:boss_id>", methods=["DELETE"])
def delete_boss(map_id: str, boss_id: int):
    """Delete a boss from a map."""
    locations = local_data.load_map_locations()
    for loc in locations:
        if loc.mapId == map_id:
            original_len = len(loc.bosses)
            loc.bosses = [b for b in loc.bosses if b.id != boss_id]
            if len(loc.bosses) == original_len:
                return jsonify({"error": "Boss not found"}), 404
            local_data.save_map_locations(locations)
            return jsonify({"message": "Boss deleted"})
    return jsonify({"error": "Map not found"}), 404
