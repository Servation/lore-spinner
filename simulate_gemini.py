import os
import time
from dotenv import load_dotenv

# Load the GEMINI_API_KEY from .env
load_dotenv()

from llm_clients import GeminiClient
from persistence import SaveManager
from agents.dm_agent import DMAgent
from game_engine.character import Character
from game_engine.ability_system import AbilitySet
from game_engine.world import WorldState

from agents.mcp_client import SyncMCPClient

def run_simulation():
    print("Starting 20-round Gemini 2.5 simulation...")
    
    # Initialize the LLMs
    try:
        dm_llm = GeminiClient(model_name="gemini-2.5-pro")
        player_llm = GeminiClient(model_name="gemini-2.5-flash")
    except Exception as e:
        print(f"Failed to initialize Gemini Client: {e}")
        return
        
    print("Starting MCP Server...")
    try:
        orig_cwd = os.getcwd()
        os.chdir("dnd-mcp")
        mcp_client = SyncMCPClient("dnd_mcp_server.py", cwd=os.getcwd())
        os.chdir(orig_cwd)
    except Exception as e:
        print(f"MCP failed: {e}")
        mcp_client = None
    
    campaign_slug = "gemini_sim_run"
    
    # Initialize fresh save
    sm = SaveManager()
    # Delete if exists
    if os.path.exists(os.path.join("saves", campaign_slug)):
        import shutil
        shutil.rmtree(os.path.join("saves", campaign_slug))
        
    # Create a basic character with Stats Mode ON to test mechanics
    char = Character(name="Test Subject", appearance="A brave adventurer")
    char.abilities.add_tag("combat", 2)
    char.abilities.add_tag("athletics", 1)
    char.abilities.add_tag("spellcasting", 2)
    char.abilities.add_tag("stealth", 1)
    
    world = WorldState(
        setting_genre="fantasy",
        setting_description="A classic fantasy dungeon crawl.",
        dm_traits="descriptive, firm",
        stats_mode=True
    )
    
    factions = {"factions": {}, "faction_events": []}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    slug = sm.save_game("Gemini Sim Run", char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    # Instantiate DM Agent
    dm = DMAgent(dm_llm, slug, mcp_client=mcp_client)
    
    # Game Loop
    artifact_path = r"C:\Users\Jeffrey Saelee\.gemini\antigravity\brain\d200dd30-47ec-4eaa-81ba-39268d3d047f\simulation_transcript.md"
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write("# 20-Round Simulation Transcript (Gemini 2.5 Pro DM)\n")
        
    def append_log(text):
        print(text, flush=True)
        with open(artifact_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
            
    player_input = "I wake up in the middle of a bustling fantasy city square. What do I see?"
    
    for turn in range(1, 21):
        append_log(f"\n--- Turn {turn}/20 ---")
        append_log(f"## Turn {turn}")
        append_log(f"**PLAYER:** {player_input}\n")
        
        try:
            # DM processes turn
            print("DM is thinking...", flush=True)
            dm_response = dm.process_turn(player_input)
        except Exception as e:
            dm_response = f"ERROR: {e}"
            append_log(f"**DM ERROR:**\n{dm_response}\n")
            break
            
        append_log(f"DM Response Length: {len(dm_response)} characters")
        append_log(f"**DM:**\n{dm_response}\n---\n")
        
        if turn == 20:
            break
            
        # Player LLM decides next action
        player_prompt = f"""You are playing a text RPG. Here is the DM's latest response:
{dm_response}

You are a brave and slightly reckless adventurer. 
Pick one of the numbered options provided by the DM, or invent a creative, daring action of your own.
If there is combat, try to fight! If you have spellcasting, try to cast a spell!
Keep your response to a single sentence action. DO NOT output internal thoughts, just the action you perform in character."""
        
        try:
            print("Player LLM is thinking...", flush=True)
            player_input = player_llm.generate(player_prompt).strip()
        except Exception as e:
            player_input = "I look around cautiously."
            
        # Small delay to avoid Google API rate limits
        time.sleep(3)
        
    print(f"Simulation complete! Transcript saved to {artifact_path}", flush=True)

if __name__ == "__main__":
    run_simulation()
