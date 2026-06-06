import time
import os
import json
from game_engine.world import WorldState, Quest, Location

def setup_data(campaign_slug):
    os.makedirs(f"saves/{campaign_slug}", exist_ok=True)
    world = WorldState()
    world.active_quests = [Quest(id=f"q{i}", name=f"Quest {i}", description=f"Desc {i}") for i in range(100)]
    world.discovered_locations = [Location(id=f"loc{i}", name=f"Location {i}", type="city", description=f"Desc {i}", discovered_turn=1) for i in range(100)]
    for loc in world.discovered_locations:
        loc.rumors = [f"Rumor {j}" for j in range(10)]
    world_path = f"saves/{campaign_slug}/world_state.json"
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=4)
    return world_path

def cleanup_data(campaign_slug, world_path):
    os.remove(world_path)
    os.rmdir(f"saves/{campaign_slug}")

# Test with DM agent
from agents.dm_agent import DMAgent
from unittest.mock import MagicMock

# We need a DMAgent initialized
agent = DMAgent(MagicMock(), "test_bench")
# Replace tools with actual DM Agent
# BUT wait, DM Agent tools are local functions in get_tools()

def extract_tools(agent):
    agent.system_instruction = "dummy"
    agent.budget_mode = False
    agent.world_keeper = MagicMock()
    agent.faction_weaver = MagicMock()
    agent.lore_keeper = MagicMock()
    return agent._get_tools()

tools = extract_tools(agent)

world_path = setup_data("test_bench")

start_time = time.time()
for i in range(50):
    tools["add_quest_note"](f"Quest {i} | New Note")
end_time = time.time()
print(f"Time taken for 50 add_quest_note: {end_time - start_time:.4f} seconds")

start_time = time.time()
for i in range(50):
    tools["add_location_rumor"](f"Location {i} | New Rumor")
end_time = time.time()
print(f"Time taken for 50 add_location_rumor: {end_time - start_time:.4f} seconds")

start_time = time.time()
for i in range(50):
    tools["resolve_location_rumor"](f"Location {i} | Rumor 0 | false")
end_time = time.time()
print(f"Time taken for 50 resolve_location_rumor: {end_time - start_time:.4f} seconds")


cleanup_data("test_bench", world_path)
