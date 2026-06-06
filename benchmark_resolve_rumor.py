import time
import os
import json
import random
from persistence.save_manager import SaveManager, generate_slug
from game_engine.world import WorldState, Location
from game_engine.character import Character
from llm_clients import MockClient
from agents.dm_agent import DMAgent

def setup_benchmark(num_locations=1000, num_rumors_per_loc=5):
    campaign_name = "Benchmark Campaign"
    slug = generate_slug(campaign_name)

    char = Character(name="Hero")
    world = WorldState(setting_genre="Fantasy")

    for i in range(num_locations):
        loc = Location(
            id=f"loc_{i}",
            name=f"Location {i}",
            description="A place",
            type="town",
            discovered_turn=0
        )
        for j in range(num_rumors_per_loc):
            loc.rumors.append(f"Rumor {j}")
        world.discovered_locations.append(loc)

    world.current_location_id = "loc_0"

    factions = {"factions": {}}
    encounters = {}
    lore = {}

    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    return slug

def run_benchmark(slug, dm, num_resolutions=100):
    start_time = time.time()
    for _ in range(num_resolutions):
        loc_idx = random.randint(0, 999)
        rumor_idx = random.randint(0, 4)
        dm.tools["resolve_location_rumor"](f"Location {loc_idx} | Rumor {rumor_idx}")
    end_time = time.time()
    return end_time - start_time

def main():
    slug = setup_benchmark()
    client = MockClient(model_name="mock-model")
    dm = DMAgent(client, slug, budget_mode=False)

    duration = run_benchmark(slug, dm)
    print(f"Benchmark: {duration:.4f} seconds for 100 resolves.")

    SaveManager.delete_save(slug)

if __name__ == "__main__":
    main()
