import os
import sys
import json
from persistence.save_manager import SaveManager, generate_slug
from game_engine.character import Character
from game_engine.world import WorldState
from agents.subagents.faction_weaver import FactionWeaver
from agents.subagents.world_keeper import WorldKeeper

# Mock Client to avoid API costs during structural tests
from llm_clients import MockClient

def run_wave_2_persistence():
    print("=== WAVE 2: Persistence & Save Integrity ===")
    campaign_name = "Persistence Audit"
    slug = generate_slug(campaign_name)
    
    # 1. Setup complex state
    char = Character(name="StateTester", hp=15, max_hp=20)
    char.status_effects.append({"name": "poisoned", "modifiers": {"combat": -2}, "duration": 3})
    
    world = WorldState(setting_genre="Fantasy", turn_count=5)
    factions = {"factions": {"guild": {"name": "Thieves Guild", "reputation": -5, "npcs": {}, "clocks": []}}, "faction_events": [], "last_tick_turn": 4}
    encounters = {"active_encounter": {"type": "combat", "threat_level": 3, "enemies": [{"name": "Goblin", "hp": 5}]}, "recent_loot": []}
    lore = {"unlocked_lore": [{"title": "Old Key", "content": "It opens the back door."}], "secrets": ["The king is dead."]}
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    # 2. Reload and verify
    c_data, w_data, f_data, e_data, l_data = SaveManager.load_game(slug)
    char_loaded = Character.from_dict(c_data)
    
    assert char_loaded.status_effects[0]["name"] == "poisoned", "Status effect lost!"
    assert e_data["active_encounter"]["enemies"][0]["name"] == "Goblin", "Active encounter lost!"
    print("[OK] Complex state saved and loaded successfully.")
    
    # 3. Corruption test (delete factions file, corrupt world_state JSON)
    path_world = os.path.join("saves", slug, "world_state.json")
    path_fact = os.path.join("saves", slug, "factions.json")
    
    os.remove(path_fact) # simulate missing file
    with open(path_world, "w") as f:
        f.write("{ invalid_json...") # Corrupt world state
        
    try:
        data = SaveManager.load_game(slug)
        assert data is None, "Should have returned None on corrupted JSON."
        print("[OK] Handled corruption gracefully: returned None")
    except Exception as e:
        print(f"[FAIL] Threw unhandled exception instead of None: {type(e).__name__}")
        
    SaveManager.delete_save(slug)
    print("=== WAVE 2 COMPLETE ===\n")

def run_wave_3_subagents():
    print("=== WAVE 3: Subagent Autonomy (20 Heartbeats) ===")
    campaign_name = "Autonomy Audit"
    slug = generate_slug(campaign_name)
    
    char = Character(name="Watcher", hp=20)
    world = WorldState(setting_genre="Sci-Fi", turn_count=0)
    factions = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    client = MockClient(model_name="mock-model")
    weaver = FactionWeaver(client, slug)
    world_keeper = WorldKeeper(client, slug)
    
    # Inject a 10-turn clock manually
    res = weaver.tools["add_faction_clock"]("Corp | megastructure | Building the Spire | A massive spire | 10 | The spire is complete | corporate_dominance | -2")
    print("Add Clock Result:", res)
    assert "Registered faction clock" in res, "Clock registration failed"
    
    print("Simulating 20 turns (4 heartbeats)...")
    for turn in range(1, 21):
        world_path = os.path.join("saves", slug, "world_state.json")
        with open(world_path, "r", encoding="utf-8") as f:
            w_data = json.load(f)
        current_world = WorldState.from_dict(w_data)
        current_world.turn_count = turn
        with open(world_path, "w", encoding="utf-8") as f:
            json.dump(current_world.to_dict(), f, indent=4)
            
        weaver.heartbeat(budget_mode=True)
        world_keeper.heartbeat(budget_mode=True)
        
    # Verify clock completed and event generated
    fact_path = os.path.join("saves", slug, "factions.json")
    with open(fact_path, "r", encoding="utf-8") as f:
        f_data = json.load(f)
        
    events = f_data.get("faction_events", [])
    assert any("Building the Spire' completed" in e["event"] for e in events), "Clock did not complete!"
    
    clocks = f_data["factions"]["Corp"]["clocks"]
    assert len(clocks) == 0, "Clock was not removed after completion!"
    
    with open(world_path, "r", encoding="utf-8") as f:
        w_data = json.load(f)
    world_loaded = WorldState.from_dict(w_data)
    
    assert any(m.name == "corporate_dominance" for m in world_loaded.environmental_modifiers), "Modifier not applied to world!"
    
    print("[OK] Faction clocks resolved autonomously over 20 turns.")
    SaveManager.delete_save(slug)
    print("=== WAVE 3 COMPLETE ===\n")

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    run_wave_2_persistence()
    run_wave_3_subagents()
