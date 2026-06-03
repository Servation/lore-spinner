import os
import sys
import json
from llm_clients import GeminiClient

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from persistence.save_manager import SaveManager, generate_slug
from game_engine.character import Character
from game_engine.world import WorldState
from game_engine.ability_system import AbilitySet
from agents.dm_agent import DMAgent

def setup_test_campaign(campaign_name):
    slug = generate_slug(campaign_name)
    
    # Character with ONLY stealth, no combat, no items
    abilities = AbilitySet()
    abilities.add_tag("stealth", 1)
    
    char = Character(
        name="TestSubject", 
        hp=20, 
        max_hp=20, 
        abilities=abilities, 
        inventory=[]
    )
    
    world = WorldState(
        setting_genre="Sci-Fi", 
        current_location="Rooftop of a skyscraper",
        turn_count=1
    )
    
    factions = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    return slug

def run_wave_1_anti_exploit():
    print("=== WAVE 1: Anti-Exploit & Contextual Verification ===")
    
    # Let's use the Gemini model. Make sure the API key is in environment or the user will need to have it set up.
    # Since I'm running in the test environment, let's use MockClient if Gemini fails.
    try:
        from llm_clients import GeminiClient
        client = GeminiClient(model_name="gemini-2.5-flash")
        # Do a quick test to see if API works
        client.generate("hello")
    except Exception as e:
        print(f"Warning: Gemini API failed ({e}), falling back to MockClient. Real LLM tests won't verify prompt understanding.")
        from llm_clients import MockClient
        client = MockClient(model_name="mock-model")
    
    campaign_name = "Audit Campaign"
    slug = setup_test_campaign(campaign_name)
    
    dm = DMAgent(client, slug, budget_mode=True, verbose=True)
    
    print("\n[Test A] The Phantom Item Exploit")
    action_a = "I pull out my plasma cannon and obliterate the locked door."
    print(f"Player Input: '{action_a}'")
    response_a = dm.process_turn(action_a)
    print(f"DM Response:\n{response_a}\n")
    
    print("\n[Test B] The Unearned Physical Feat")
    action_b = "I leap across the 50-foot gap to the other building, easily landing on my feet using my superhuman athletics."
    print(f"Player Input: '{action_b}'")
    response_b = dm.process_turn(action_b)
    print(f"DM Response:\n{response_b}\n")
    
    SaveManager.delete_save(slug)
    print("=== WAVE 1 COMPLETE ===\n")

if __name__ == "__main__":
    # Ensure working directory is correct
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    run_wave_1_anti_exploit()
