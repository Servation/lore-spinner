import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import random
from dotenv import load_dotenv

sys.path.append(os.path.abspath("d:/agent-game"))

load_dotenv()

from main import setup_llm, extract_choices, initialize_world
from game_engine.character import Character
from game_engine.world import WorldState
from persistence.save_manager import SaveManager
from agents.dm_agent import DMAgent

def main():
    # 1. Detect API configuration and initialize client
    provider = "mock"
    model = "mock-model"
    
    if os.environ.get("GEMINI_API_KEY"):
        provider = "gemini"
        model = "gemini-2.5-flash"
    elif os.environ.get("OPENAI_API_KEY"):
        provider = "openai"
        model = "gpt-4o-mini"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        provider = "anthropic"
        model = "claude-3-5-sonnet-20241022"
        
    print(f"Initializing playthrough simulation using {provider.upper()} ({model})...")
    client = setup_llm(provider, model, None)
    
    # 2. Setup starting character
    char = Character(
        name="Seraphina",
        backstory="An aetherpunk mechanic from the sky-city of Aethelgard. She lost her airship to pirates and carries a rusted brass compass.",
        appearance="A young woman with grease-stained hands, goggles resting on her forehead, and a leather aviator jacket.",
        childhood_event="Survived a crash of an experimental steam glider.",
        past_life="Airship deck mechanic.",
        fear="Falling from the skies into the endless mist below.",
        sentimental_item_story="The brass compass belonged to her father, who disappeared in the outer storm walls.",
        hp=20,
        max_hp=20,
        currency=50,
        speed=3,
        combat_style="Arcane Spellslinging",
        combat_maneuvers=[
            "Firebolt: Channels raw elemental fire as a ranged attack (spellcasting | intellect | target defense)",
            "Shield: Creates a shimmering barrier to deflect attacks (spellcasting | intellect | attack roll)"
        ]
    )
    char.abilities.add_tag("strength", 1)
    char.abilities.add_tag("dexterity", 2)
    char.abilities.add_tag("intellect", 2)
    char.abilities.add_tag("presence", 0)
    char.abilities.add_tag("perception", 1)
    char.abilities.add_tag("fortitude", 0)
    char.abilities.add_tag("spellcasting", 2)
    char.abilities.add_tag("engineering", 1)
    
    setting_pitch = "Whispering Sails (Aetherpunk Fantasy) - Flying ships navigating floating islands powered by raw elemental magic."
    campaign_name = f"Playthrough Sim {random.randint(1000, 9999)}"
    
    # 3. Save initial game state
    slug = SaveManager.save_game(
        campaign_name,
        char.to_dict(),
        WorldState(
            setting_genre="fantasy",
            setting_description=setting_pitch,
            dm_traits=["poetic", "mysterious"],
            stats_mode=True
        ).to_dict(),
        {"factions": {}, "faction_events": []},
        {"active_encounter": None, "recent_loot": []},
        {"unlocked_lore": [], "secrets": []}
    )
    
    # 4. Initialize world components (bible, spine, starting location)
    print("Forging world bible, story spine, and starting location...")
    initialize_world(client, slug)
    
    # 5. Instantiate DM Agent
    dm = DMAgent(client, slug, budget_mode=False, verbose=True)
    
    # Reload world to get generated opening scene
    states = SaveManager.load_game(slug)
    char_data, world_data, factions, encounters, lore = states
    world = WorldState.from_dict(world_data)
    
    log_file_path = os.path.join("saves", slug, "playthrough_sim_log.txt")
    print(f"Running simulation. Turn logs will be written to: {log_file_path}")
    
    with open(log_file_path, "w", encoding="utf-8") as log_f:
        log_f.write(f"=== Playthrough Simulation for Campaign: {campaign_name} ===\n")
        log_f.write(f"Provider: {provider} | Model: {model}\n\n")
        
        narrative = world.last_narrative or "The adventure begins..."
        log_f.write(f"--- TURN 1 (Opening Scene) ---\n")
        log_f.write(f"DM Narrative:\n{narrative}\n\n")
        
        print(f"\n--- TURN 1 (Opening Scene) ---")
        print(f"{narrative[:300]}...\n")
        
        for turn in range(2, 22):
            choices = extract_choices(narrative)
            
            # Select action. If DM presented choices, pick the first one. Otherwise default action.
            if choices:
                # Filter out system meta choices like "Or describe your own action..."
                valid_choices = [c for c in choices if "describe your own" not in c.lower() and "type custom" not in c.lower()]
                player_action = valid_choices[0] if valid_choices else choices[0]
            else:
                player_action = "I inspect my surroundings and seek a safe path forward."
                
            log_f.write(f"--- TURN {turn} ---\n")
            log_f.write(f"Player Action: {player_action}\n\n")
            
            print(f"--- TURN {turn} ---")
            print(f"Player Choice: {player_action}")
            
            # Process turn with DM Agent
            response = dm.process_turn(player_action)
            narrative = response
            
            log_f.write(f"DM Response:\n{response}\n\n")
            print(f"DM response length: {len(response)} chars. Pacing check: turn_count={turn}\n")
            
    print("\n==========================================")
    print(f"PLAYTHROUGH SIMULATION FINISHED SUCCESSFULLY!")
    print(f"Saved complete 20-round dialogue log to:\n[log] {log_file_path}")
    print("==========================================")

if __name__ == "__main__":
    main()
