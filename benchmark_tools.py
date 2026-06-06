import time
import os
import json
from agents.dm_agent import DMAgent

class MockClient:
    pass

def setup_benchmark():
    slug = "benchmark-campaign-tools"
    os.makedirs(os.path.join("saves", slug), exist_ok=True)

    char = {"name": "Test"}
    world = {"turn_count": 1}
    factions = {"factions": {}}
    encounters = {}
    lore = {"unlocked_lore": [{"title": f"Lore_{i}", "text": f"Content {i}"} for i in range(100)], "secrets": []}

    from persistence.save_manager import SaveManager
    SaveManager.save_game("Benchmark Tools", char, world, factions, encounters, lore)

    client = MockClient()
    dm = DMAgent(client, slug)
    return dm, slug

def run_benchmark(dm, iterations=1000):
    start = time.time()
    for _ in range(iterations):
        for tool_name, tool_func in dm.tools.items():
            if tool_name == "query_unlocked_lore":
                tool_func("Lore_50")
    end = time.time()
    return end - start

if __name__ == "__main__":
    dm, slug = setup_benchmark()
    duration = run_benchmark(dm)
    print(f"New duration for 1000 file reads via query_unlocked_lore: {duration:.4f} seconds")
