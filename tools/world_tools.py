# world_tools.py - Shared world tools
import os
import json
from game_engine.world import WorldState

def load_world_state(campaign_slug: str) -> WorldState:
    """Loads the world state for a given campaign slot."""
    path = os.path.join("saves", campaign_slug, "world_state.json")
    if not os.path.exists(path):
        return WorldState()
    with open(path, "r", encoding="utf-8") as f:
        return WorldState.from_dict(json.load(f))

def save_world_state(campaign_slug: str, world: WorldState) -> None:
    """Saves the world state for a given campaign slot."""
    path = os.path.join("saves", campaign_slug, "world_state.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=4)
