import os
import sys
import json
import argparse
import random
from typing import Dict, Any, List

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from llm_clients import GeminiClient, OpenAIClient, MockClient, AnthropicClient
from persistence import SaveManager, read_dm_log, write_dm_log
from game_engine.character import Character
from game_engine.world import WorldState
from game_engine.ability_system import AbilitySet
from agents.dm_agent import DMAgent

# Terminal Styling Colors
COLOR_TITLE = "\033[95m\033[1m"      # Bright bold Magenta
COLOR_DM = "\033[93m"             # Yellow/Gold for DM
COLOR_OPTION = "\033[36m"         # Cyan for options
COLOR_OOC = "\033[92m"            # Green for OOC info
COLOR_SYSTEM = "\033[90m"         # Grey for system
COLOR_ERROR = "\033[91m"          # Red for errors
COLOR_RESET = "\033[0m"

BUDGET_MODE_GLOBAL = False
VERBOSE_GLOBAL = False

def print_styled(text: str, color: str = COLOR_RESET):
    print(f"{color}{text}{COLOR_RESET}")

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def display_menu():
    print_styled("\n" + "=" * 40, COLOR_TITLE)
    print_styled("       LORE SPINNER - Narrative RPG     ", COLOR_TITLE)
    print_styled("=" * 40, COLOR_TITLE)
    print("1. New Game")
    print("2. Continue Campaign")
    print("3. Search Campaigns")
    print("4. Manage Saves")
    print("5. Settings")
    print("6. Quit")
    print_styled("=" * 40, COLOR_TITLE)

def setup_llm(provider: str, model_name: str, base_url: str):
    """Initializes LLM client based on selection."""
    if provider == "gemini":
        return GeminiClient(model_name=model_name)
    elif provider == "openai":
        return OpenAIClient(model_name=model_name, base_url=base_url)
    elif provider == "anthropic":
        return AnthropicClient(model_name=model_name)
    else:
        return MockClient(model_name=model_name)

def generate_setting_pitches(llm_client) -> List[str]:
    prompt = """You are a creative world builder.
Generate 4 distinct setting pitches for an RPG campaign.
Each pitch should be a unique blend of genres (e.g. sci-fi fantasy, post-apocalyptic cyberpunk, renaissance magic, weird west steampunk).
Each pitch should be a single paragraph including a title and a brief hook.

Format the output as:
1. [Setting Name] (Genres) - Hook description
2. [Setting Name] (Genres) - Hook description
..."""
    response = llm_client.generate(prompt)
    pitches = []
    # Parse numbered list
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    for line in lines:
        if line[0].isdigit() or line.startswith("-"):
            pitches.append(line)
    if not pitches:
        # Fallback pitches
        pitches = [
            "1. Neon Shadows (Cyberpunk Noir) - Rain-slicked megacity where cybernetic gangs trade memory shards.",
            "2. Ash & Cogs (Steampunk Post-Apocalyptic) - Survivor city built on moving gears around volcanic vents.",
            "3. Whispering Sails (Aetherpunk Fantasy) - Skyships navigating floating islands powered by arcane elements.",
            "4. Tomb of Stars (Sci-Fi Gothic) - Space scavengers exploring dead dreadnoughts haunted by synthetic entities."
        ]
    return pitches[:4]

def run_character_creation(llm_client, setting_pitch: str) -> Character:
    print_styled("\n--- Character Creation ---", COLOR_TITLE)
    name = input("\nWhat is your character's name? ").strip()
    if not name:
        name = "Adventurer"

    questions = [
        "What did you do before the world changed or your adventure began?",
        "What is your greatest fear or weakness?",
        "What is the single object you carry with you at all times and why?"
    ]
    
    answers = []
    
    for i, q in enumerate(questions):
        print_styled(f"\nQuestion {i+1}: {q}", COLOR_TITLE)
        
        # Ask LLM for suggestions
        prompt = f"""For an RPG character named '{name}' in the setting: '{setting_pitch}'.
Generate 3 short, flavor-rich example answers for the question: '{q}'.
Format as:
1. Option A
2. Option B
3. Option C"""
        
        options_text = llm_client.generate(prompt)
        print_styled(options_text, COLOR_OPTION)
        print("4. Custom (Write your own...)")
        
        choice = input("\nChoose an option (1-4) or write your own: ").strip()
        
        if choice in ["1", "2", "3"]:
            # Extract choice
            lines = [l.strip() for l in options_text.splitlines() if l.strip()]
            try:
                ans = lines[int(choice) - 1]
            except Exception:
                ans = choice
        elif choice == "4" or not choice in ["1", "2", "3"]:
            if choice == "4":
                ans = input("Describe in your own words: ").strip()
            else:
                ans = choice
        answers.append(ans)

    # Analyze answers and build starting tags
    print_styled("\nCalculating your hidden attributes...", COLOR_SYSTEM)
    analysis_prompt = f"""Based on these character details:
Name: {name}
Setting: {setting_pitch}
Backstory details:
1. Past: {answers[0]}
2. Fear: {answers[1]}
3. Item: {answers[2]}

Choose 4-6 appropriate ability tags with starting modifiers (+1 to +3) representing skills or traits.
Include one combat-related tag, one utility-related tag, and others based on backstory.
Output ONLY a valid JSON dictionary mapping tag names (lowercase strings) to integer modifiers.
Do not include any markdown formatting, thoughts, or text.
Example format:
{{"combat": 2, "stealth": 3, "hacking": 1, "stamina": 2}}"""

    response = llm_client.generate(analysis_prompt)
    
    # Try to find JSON inside response
    tags = {}
    try:
        # Strip potential markdown code blocks
        clean_res = response.strip()
        if "```json" in clean_res:
            clean_res = clean_res.split("```json")[1].split("```")[0]
        elif "```" in clean_res:
            clean_res = clean_res.split("```")[1].split("```")[0]
        clean_res = clean_res.strip()
        tags = json.loads(clean_res)
    except Exception:
        # Fallback tags
        print_styled("Warning: Using default attributes due to generation hiccup.", COLOR_ERROR)
        tags = {"combat": 2, "perception": 2, "survival": 1, "athletics": 1}

    abilities = AbilitySet()
    for t_name, mod in tags.items():
        abilities.add_tag(t_name, mod)
        
    # Also add the starting item to inventory
    from game_engine.item_system import Item
    starting_item = Item(name="Backstory Trinket", description=answers[2])
    
    # Generate appearance from character details
    print_styled("\nDescribing your appearance...", COLOR_SYSTEM)
    appearance_prompt = f"""Based on these character details:
Name: {name}
Setting: {setting_pitch}
Backstory details:
1. Past: {answers[0]}
2. Fear: {answers[1]}
3. Item: {answers[2]}

Generate a short, evocative 1-sentence physical description of this character's appearance.
Do not include any intro, thoughts, or metadata. Just the description."""
    
    appearance_text = llm_client.generate(appearance_prompt).strip()
    if not appearance_text or "```" in appearance_text or len(appearance_text) < 5:
        appearance_text = f"A traveler wearing clothing suitable for the setting of {setting_pitch}."
        
    char = Character(
        name=name,
        backstory=f"Past: {answers[0]} | Fear: {answers[1]}",
        appearance=appearance_text,
        abilities=abilities,
        inventory=[starting_item]
    )
    
    return char

def handle_ooc_command(cmd: str, campaign_slug: str):
    """Handles Out-of-Character queries locally to save API cost."""
    sub = cmd.replace("ooc:", "").strip().lower()
    
    char_path = os.path.join("saves", campaign_slug, "character.json")
    world_path = os.path.join("saves", campaign_slug, "world_state.json")
    lore_path = os.path.join("saves", campaign_slug, "lore.json")
    
    if "stats" in sub or "abilities" in sub or "character" in sub:
        if not os.path.exists(char_path):
            print_styled("Character file not found.", COLOR_ERROR)
            return
        with open(char_path, "r", encoding="utf-8") as f:
            char = Character.from_dict(json.load(f))
        print_styled(f"\n--- OOC: Character Stats for {char.name} ---", COLOR_OOC)
        print(f"HP: {char.hp}/{char.max_hp}")
        print("Ability Tags (Hidden Modifiers):")
        for t_name, tag in char.abilities.tags.items():
            print(f" - {t_name}: +{tag.modifier} (Usage: {tag.usage_count} ticks)")
        if char.equipped:
            print("Equipped Items:")
            for slot, item in char.equipped.items():
                print(f" - {slot.upper()}: {item.name} ({item.description})")
        print_styled("-" * 40, COLOR_OOC)
        
    elif "inventory" in sub or "items" in sub:
        with open(char_path, "r", encoding="utf-8") as f:
            char = Character.from_dict(json.load(f))
        print_styled(f"\n--- OOC: Inventory ---", COLOR_OOC)
        if not char.inventory:
            print("Your pockets are empty.")
        for item in char.inventory:
            print(f" - {item.name}: {item.description} (Slot: {item.slot or 'None'})")
        print_styled("-" * 25, COLOR_OOC)
        
    elif "quests" in sub:
        with open(world_path, "r", encoding="utf-8") as f:
            world = WorldState.from_dict(json.load(f))
        print_styled(f"\n--- OOC: Active Quests ---", COLOR_OOC)
        if not world.active_quests:
            print("No active quests.")
        for quest in world.active_quests:
            print(f" - [{quest.status.upper()}] {quest.name}: {quest.description}")
            for note in quest.notes:
                print(f"     * {note}")
        print_styled("-" * 30, COLOR_OOC)
        
    elif "log" in sub or "history" in sub:
        log = read_dm_log(campaign_slug)
        print_styled(f"\n--- OOC: DM Campaign Log ---", COLOR_OOC)
        print(log)
        print_styled("-" * 30, COLOR_OOC)
        
    elif "lore" in sub or "secrets" in sub:
        if os.path.exists(lore_path):
            with open(lore_path, "r", encoding="utf-8") as f:
                lore = json.load(f)
            print_styled(f"\n--- OOC: Unlocked Lore ---", COLOR_OOC)
            for entry in lore.get("unlocked_lore", []):
                print(f" * {entry.get('title')}: {entry.get('content')}")
            for secret in lore.get("secrets", []):
                print(f" * Clue: {secret}")
            print_styled("-" * 30, COLOR_OOC)
        else:
            print_styled("No lore discovered yet.", COLOR_OOC)
            
    else:
        print_styled("OOC Command Options: 'ooc: stats', 'ooc: inventory', 'ooc: quests', 'ooc: log', 'ooc: lore'", COLOR_OOC)

def extract_choices(text: str) -> List[str]:
    import re
    choices = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Check for bullet: "* " or "- "
        if stripped.startswith(("* ", "- ")):
            choice_text = stripped[2:].strip()
        # Check for numbered: e.g. "1. " or "1) " or "10. "
        elif re.match(r"^\d+[\.\)]\s+", stripped):
            parts = re.split(r"[\.\)]\s+", stripped, 1)
            choice_text = parts[1].strip()
        else:
            continue
            
        # Clean markdown bold markers
        choice_text = choice_text.replace("**", "").strip()
        if choice_text:
            choices.append(choice_text)
    return choices

def show_campaign_summary(campaign_slug: str, llm_client):
    """Compiles and displays a comprehensive, immersive summary of the player's status and story."""
    import json
    import os
    
    char_path = os.path.join("saves", campaign_slug, "character.json")
    world_path = os.path.join("saves", campaign_slug, "world_state.json")
    
    if not os.path.exists(char_path) or not os.path.exists(world_path):
        print_styled("Error: Campaign data files not found.", COLOR_ERROR)
        return
        
    with open(char_path, "r", encoding="utf-8") as f:
        char = Character.from_dict(json.load(f))
    with open(world_path, "r", encoding="utf-8") as f:
        world = WorldState.from_dict(json.load(f))
        
    print_styled("\n" + "=" * 45, COLOR_TITLE)
    print_styled("              ADVENTURE SUMMARY              ", COLOR_TITLE)
    print_styled("=" * 45, COLOR_TITLE)
    
    # 1. Narrative Story Recap (via LLM)
    log_bullets = read_dm_log(campaign_slug).strip()
    if log_bullets:
        print_styled("[ Story So Far ]", COLOR_OOC)
        prompt = f"""You are the chronicler for an RPG campaign.
Based on the following log of events:
{log_bullets}

Write a single, highly atmospheric paragraph (3-4 sentences maximum) summarizing the narrative journey, setting the mood, and capturing the current situation. 
Use the tone matching the campaign genre: {world.setting_genre}.
Do not include any intro, outro, or metadata. Write only the narrative paragraph."""
        
        try:
            recap = llm_client.generate(prompt)
            print(recap.strip())
        except Exception:
            # Fallback to listing the bullets if API call fails
            print("\n".join(log_bullets.splitlines()[-4:]))
    else:
        print("Your story is just beginning.")
        
    print_styled("-" * 45, COLOR_SYSTEM)
    
    # 2. Character Status
    print_styled("[ Character Status ]", COLOR_OOC)
    hp_pct = (char.hp / char.max_hp) * 100
    if hp_pct >= 80:
        cond = "Healthy"
    elif hp_pct >= 40:
        cond = "Wounded"
    else:
        cond = "Near Death"
        
    print(f"Name: {char.name} ({char.appearance})")
    print(f"Condition: {cond}")
    
    # 3. Equipped & Inventory
    print_styled("-" * 45, COLOR_SYSTEM)
    print_styled("[ Equipment & Inventory ]", COLOR_OOC)
    if char.equipped:
        eq_list = [f"{slot.upper()}: {item.name}" for slot, item in char.equipped.items()]
        print(f"Equipped: {', '.join(eq_list)}")
    else:
        print("Equipped: Nothing")
        
    inv_list = [item.name for item in char.inventory]
    if inv_list:
        print(f"Inventory: {', '.join(inv_list)}")
    else:
        print("Inventory: Empty")
        
    # 4. Key Relationships
    if char.relationships:
        print_styled("-" * 45, COLOR_SYSTEM)
        print_styled("[ Key Relationships ]", COLOR_OOC)
        for name, rel in char.relationships.items():
            print(f"- {name}: {rel}")

    # 5. World state and Mood
    print_styled("-" * 45, COLOR_SYSTEM)
    print_styled("[ Atmosphere & Environment ]", COLOR_OOC)
    print(f"Genre: {world.setting_genre} | Time: {world.time_of_day.upper()} (Turn: {world.turn_count})")
    if world.environmental_modifiers:
        mods = [f"{k} ({v:+})" for k, v in world.environmental_modifiers.items()]
        print(f"Active Modifiers: {', '.join(mods)}")
    else:
        print("Active Modifiers: None (Normal conditions)")
        
    # 6. Discovered Locations
    if world.discovered_locations:
        print_styled("-" * 45, COLOR_SYSTEM)
        print_styled("[ Discovered Locations ]", COLOR_OOC)
        for loc in world.discovered_locations:
            print(f"- {loc.name} ({loc.type.title()}): {loc.description} (Found Turn: {loc.discovered_turn})")

    if world.active_quests:
        print_styled("-" * 45, COLOR_SYSTEM)
        print_styled("[ Active Quests ]", COLOR_OOC)
        for q in world.active_quests:
            print(f"- {q.name}: {q.description} ({q.status})")
            
    # Unlocked Lore & Secrets
    lore_path = os.path.join("saves", campaign_slug, "lore.json")
    if os.path.exists(lore_path):
        try:
            with open(lore_path, "r", encoding="utf-8") as f:
                lore_data = json.load(f)
            unlocked = lore_data.get("unlocked_lore", [])
            secrets = lore_data.get("secrets", [])
            if unlocked or secrets:
                print_styled("-" * 45, COLOR_SYSTEM)
                print_styled("[ Knowledge & Secrets ]", COLOR_OOC)
                for entry in unlocked:
                    print(f"- [Lore] {entry.get('title')}: {entry.get('content')}")
                for secret in secrets:
                    print(f"- [Secret] {secret}")
        except Exception:
            pass

    # Factions, Clocks & Events
    factions_path = os.path.join("saves", campaign_slug, "factions.json")
    if os.path.exists(factions_path):
        try:
            with open(factions_path, "r", encoding="utf-8") as f:
                f_data = json.load(f)
            factions = f_data.get("factions", {})
            events = f_data.get("faction_events", [])
            
            if factions or events:
                print_styled("-" * 45, COLOR_SYSTEM)
                print_styled("[ Factions & Background Intrigue ]", COLOR_OOC)
                
                if factions:
                    print("Faction Standings:")
                    for f_id, f_info in factions.items():
                        npc_names = list(f_info.get("npcs", {}).keys())
                        npc_str = f" (NPCs: {', '.join(npc_names)})" if npc_names else ""
                        print(f" - {f_info.get('name', f_id)}: Reputation {f_info.get('reputation', 0)}{npc_str}")
                        
                        clocks = f_info.get("clocks", [])
                        if clocks:
                            for clock in clocks:
                                print(f"    * PROJECT CLOCK: {clock['name']} - {clock['description']} ({clock['turns_remaining']} turns remaining)")
                                
                if events:
                    print("\nRecent Faction Events:")
                    for e in events[-3:]:
                        print(f" - {e.get('event')}")
        except Exception:
            pass
            
    print_styled("=" * 45 + "\n", COLOR_TITLE)

def game_loop(llm_client, campaign_slug: str):
    """The active gameplay console loop."""
    global BUDGET_MODE_GLOBAL
    
    # Load campaign info
    states = SaveManager.load_game(campaign_slug)
    if not states:
        print_styled("Failed to load campaign.", COLOR_ERROR)
        return
        
    char_data, world_data, factions, encounters, lore = states
    char = Character.from_dict(char_data)
    world = WorldState.from_dict(world_data)
    
    dm = DMAgent(llm_client, campaign_slug, budget_mode=BUDGET_MODE_GLOBAL, verbose=VERBOSE_GLOBAL)
    
    clear_screen()
    print_styled(f"\nCampaign: {campaign_slug.replace('-', ' ').title()}", COLOR_TITLE)
    print_styled(f"Genre: {world.setting_genre} | DM Persona Traits: {', '.join(world.dm_traits)}", COLOR_SYSTEM)
    print_styled(f"Logged in as: {char.name}", COLOR_SYSTEM)
    print_styled(f"Type '/summary' to view status and story recap, 'ooc: help' for stat details, 'quit' to exit.\n", COLOR_SYSTEM)
    
    # Initial DM description prompt
    print_styled("--- Adventure Logs (compaction-active) ---", COLOR_SYSTEM)
    dm_log = read_dm_log(campaign_slug)
    print(dm_log)
    print_styled("-----------------------------------------", COLOR_SYSTEM)
    
    if world.last_narrative:
        response = world.last_narrative
        print_styled(f"\n{response}", COLOR_DM)
    else:
        print_styled("\n[System] Continuing your story...", COLOR_SYSTEM)
        # Trigger a dummy action to kick off narration if log is small
        last_log_lines = dm_log.splitlines()
        last_event = last_log_lines[-1] if last_log_lines else "Waking up in a new world."
        
        response = dm.process_turn(f"Narrate the current situation based on our last event: '{last_event}'")
        print_styled(f"\n{response}", COLOR_DM)
        
        # Save this narrative in world state and write to disk
        world.last_narrative = response
        world_path = os.path.join("saves", campaign_slug, "world_state.json")
        with open(world_path, "w", encoding="utf-8") as f:
            json.dump(world.to_dict(), f, indent=4)
            
    active_choices = extract_choices(response)
    
    while True:
        try:
            action = input(f"\n{COLOR_OPTION}What do you do? {COLOR_RESET}").strip()
            if not action:
                continue
                
            if action.isdigit():
                idx = int(action) - 1
                if 0 <= idx < len(active_choices):
                    action = active_choices[idx]
                    print_styled(f"\n[Selected: {action}]", COLOR_SYSTEM)
                
            if action.lower() in ["exit", "quit"]:
                print_styled("Saving game... Goodbye!", COLOR_SYSTEM)
                break
                
            if action.lower() == "save":
                # Resave all
                char_path = os.path.join("saves", campaign_slug, "character.json")
                with open(char_path, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                world_path = os.path.join("saves", campaign_slug, "world_state.json")
                with open(world_path, "r", encoding="utf-8") as f:
                    w_data = json.load(f)
                
                enc_path = os.path.join("saves", campaign_slug, "encounters.json")
                if os.path.exists(enc_path):
                    with open(enc_path, "r", encoding="utf-8") as f:
                        e_data = json.load(f)
                else:
                    e_data = {"active_encounter": None, "recent_loot": []}
                    
                lore_path = os.path.join("saves", campaign_slug, "lore.json")
                if os.path.exists(lore_path):
                    with open(lore_path, "r", encoding="utf-8") as f:
                        l_data = json.load(f)
                else:
                    l_data = {"unlocked_lore": [], "secrets": []}
                    
                factions_path = os.path.join("saves", campaign_slug, "factions.json")
                if os.path.exists(factions_path):
                    with open(factions_path, "r", encoding="utf-8") as f:
                        f_data = json.load(f)
                else:
                    f_data = {"factions": {}, "faction_events": []}
                    
                SaveManager.save_game(campaign_slug, c_data, w_data, f_data, e_data, l_data)
                print_styled("Game saved.", COLOR_SYSTEM)
                continue
                
            if action.lower().startswith("budget "):
                cmd = action.lower().split(" ", 1)[1].strip()
                if cmd == "on":
                    BUDGET_MODE_GLOBAL = True
                    dm.budget_mode = True
                    print_styled("Budget Mode ENABLED (reduced LLM subagent execution).", COLOR_SYSTEM)
                else:
                    BUDGET_MODE_GLOBAL = False
                    dm.budget_mode = False
                    print_styled("Budget Mode DISABLED (full autonomous subagent heartbeats).", COLOR_SYSTEM)
                continue
                
            if action.lower() == "/summary":
                show_campaign_summary(campaign_slug, llm_client)
                continue
                
            if action.lower().startswith("ooc:"):
                handle_ooc_command(action, campaign_slug)
                continue
                
            # Process standard action
            print_styled("\n[DM is thinking...]", COLOR_SYSTEM)
            # Reload objects in case subagent tools changed them on disk
            dm.budget_mode = BUDGET_MODE_GLOBAL
            dm.verbose = VERBOSE_GLOBAL
            response = dm.process_turn(action)
            print_styled(f"\n{response}", COLOR_DM)
            active_choices = extract_choices(response)
            
            # Save the last narrative to world state and update it on disk
            world.last_narrative = response
            world_path = os.path.join("saves", campaign_slug, "world_state.json")
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            
            # Check character health
            char_path = os.path.join("saves", campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char_data = json.load(f)
            char = Character.from_dict(char_data)
            
            if not char.is_alive():
                print_styled("\n!!! YOU HAVE FALLEN !!!", COLOR_ERROR)
                print("The DM will resolve your death contextually based on the story.")
                input("Press Enter to continue...")
                # DM processes recovery or death
                response = dm.process_turn("The character has run out of health. Narration must resolve this death contextually (checkpoint reset, penalty recovery, or permanent death).")
                print_styled(f"\n{response}", COLOR_DM)
                active_choices = extract_choices(response)
                
                # Save the last narrative to world state and update it on disk
                world.last_narrative = response
                world_path = os.path.join("saves", campaign_slug, "world_state.json")
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                
        except KeyboardInterrupt:
            print_styled("\nSaving game... Goodbye!", COLOR_SYSTEM)
            break
        except Exception as e:
            print_styled(f"Error during turn: {e}", COLOR_ERROR)

def run_new_game(llm_client):
    print_styled("\n--- Setting Generation ---", COLOR_TITLE)
    print("Asking the DM to generate settings...")
    pitches = generate_setting_pitches(llm_client)
    
    for pitch in pitches:
        print(pitch)
        
    choice = input("\nSelect a setting (1-4) or write your own: ").strip()
    selected_pitch = ""
    if choice in ["1", "2", "3", "4"]:
        selected_pitch = pitches[int(choice) - 1]
    else:
        selected_pitch = choice if choice else pitches[0]
        
    # Generate DM personality traits
    possible_traits = ["sardonic", "gritty", "theatrical", "mysterious", "noir", "dramatic", "poetic", "cynical", "humorous"]
    dm_traits = random.sample(possible_traits, 2)
    
    # Run character interview
    char = run_character_creation(llm_client, selected_pitch)
    
    # Ask for campaign save name
    campaign_name = input("\nWhat do you want to name this campaign? ").strip()
    if not campaign_name:
        campaign_name = f"{char.name}'s Adventure"
        
    # Initialize game objects
    world = WorldState(
        setting_genre=selected_pitch.split("(")[1].split(")")[0] if "(" in selected_pitch else "Fantasy",
        setting_description=selected_pitch,
        dm_traits=dm_traits
    )
    
    factions = {"factions": {}, "faction_events": []}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    # Save the initial files
    slug = SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    write_dm_log(slug, f"Campaign started: {campaign_name}. Genre: {world.setting_genre}.", llm_client)
    
    print_styled(f"\nCampaign '{campaign_name}' initialized successfully!", COLOR_OOC)
    input("Press Enter to begin your journey...")
    game_loop(llm_client, slug)

def run_load_game(llm_client):
    saves = SaveManager.list_saves()
    if not saves:
        print_styled("No saves found. Start a New Game!", COLOR_ERROR)
        return
        
    print_styled("\n--- Load Campaign ---", COLOR_TITLE)
    for idx, save in enumerate(saves):
        print(f"{idx+1}. {save['campaign_name']} (Character: {save['character_name']}, Genre: {save['genre']}, Turn: {save['turn_count']})")
        
    choice = input("\nChoose save (1-N) or 'q' to go back: ").strip()
    if choice.lower() == 'q':
        return
        
    try:
        idx = int(choice) - 1
        slug = saves[idx]["campaign_slug"]
        game_loop(llm_client, slug)
    except Exception:
        print_styled("Invalid choice.", COLOR_ERROR)

def run_search_game(llm_client):
    query = input("\nEnter campaign name, character name, or genre query: ").strip()
    results = SaveManager.search_saves(query)
    if not results:
        print_styled("No campaigns matched your query.", COLOR_ERROR)
        return
        
    print_styled(f"\n--- Search Results for '{query}' ---", COLOR_TITLE)
    for idx, save in enumerate(results):
        print(f"{idx+1}. {save['campaign_name']} (Character: {save['character_name']}, Genre: {save['genre']})")
        
    choice = input("\nChoose campaign to load (1-N) or 'q' to go back: ").strip()
    if choice.lower() == 'q':
        return
        
    try:
        idx = int(choice) - 1
        slug = results[idx]["campaign_slug"]
        game_loop(llm_client, slug)
    except Exception:
        print_styled("Invalid choice.", COLOR_ERROR)

def run_manage_saves():
    saves = SaveManager.list_saves()
    if not saves:
        print_styled("No campaigns found.", COLOR_ERROR)
        return
        
    print_styled("\n--- Manage Saves ---", COLOR_TITLE)
    for idx, save in enumerate(saves):
        print(f"{idx+1}. {save['campaign_name']} [{save['campaign_slug']}]")
        
    choice = input("\nChoose save to DELETE (1-N) or 'q' to go back: ").strip()
    if choice.lower() == 'q':
        return
        
    try:
        idx = int(choice) - 1
        slug = saves[idx]["campaign_slug"]
        confirm = input(f"Are you sure you want to delete campaign '{slug}' permanently? (y/n): ").strip().lower()
        if confirm == 'y':
            SaveManager.delete_save(slug)
            print_styled("Save deleted.", COLOR_OOC)
    except Exception:
        print_styled("Invalid choice.", COLOR_ERROR)

def run_settings():
    global BUDGET_MODE_GLOBAL, VERBOSE_GLOBAL
    print_styled("\n--- Settings ---", COLOR_TITLE)
    print(f"1. Toggle Budget Mode (Currently: {'ENABLED' if BUDGET_MODE_GLOBAL else 'DISABLED'})")
    print(f"2. Toggle DM Verbose Logs (Currently: {'ENABLED' if VERBOSE_GLOBAL else 'DISABLED'})")
    print("3. Back")
    
    choice = input("\nChoose option: ").strip()
    if choice == "1":
        BUDGET_MODE_GLOBAL = not BUDGET_MODE_GLOBAL
        print_styled(f"Budget mode is now {'ENABLED' if BUDGET_MODE_GLOBAL else 'DISABLED'}.", COLOR_OOC)
    elif choice == "2":
        VERBOSE_GLOBAL = not VERBOSE_GLOBAL
        print_styled(f"Verbose mode is now {'ENABLED' if VERBOSE_GLOBAL else 'DISABLED'}.", COLOR_OOC)

def main():
    parser = argparse.ArgumentParser(description="Lore Spinner - Multi-Agent RPG Campaign Console")
    parser.add_argument("--provider", choices=["gemini", "openai", "anthropic", "mock"], default="gemini", help="LLM provider (default: gemini)")
    parser.add_argument("--model", type=str, help="Model name")
    parser.add_argument("--base-url", type=str, help="Custom base URL for OpenAI-compatible clients")
    parser.add_argument("--budget", action="store_true", help="Start game with Budget Mode enabled")
    parser.add_argument("--verbose", action="store_true", help="Show DM's internal thoughts and tool actions")
    args = parser.parse_args()
    
    global BUDGET_MODE_GLOBAL, VERBOSE_GLOBAL
    if args.budget:
        BUDGET_MODE_GLOBAL = True
    if args.verbose:
        VERBOSE_GLOBAL = True
        
    # Setup LLM configuration
    model_name = args.model
    if not model_name:
        if args.provider == "gemini":
            model_name = "gemini-2.5-flash"
        elif args.provider == "openai":
            model_name = "gpt-4o-mini"
        elif args.provider == "anthropic":
            model_name = "claude-3-5-sonnet-20241022"
        else:
            model_name = "mock-model"
            
    print(f"Initializing DM Agent using {args.provider.upper()} ({model_name})...")
    try:
        client = setup_llm(args.provider, model_name, args.base_url)
    except Exception as e:
        print_styled(f"Initialization Error: {e}", COLOR_ERROR)
        print("Please configure your .env file with API keys or run with mock provider: --provider mock")
        return

    while True:
        display_menu()
        choice = input("Enter choice (1-6): ").strip()
        
        if choice == "1":
            run_new_game(client)
        elif choice == "2":
            run_load_game(client)
        elif choice == "3":
            run_search_game(client)
        elif choice == "4":
            run_manage_saves()
        elif choice == "5":
            run_settings()
        elif choice == "6":
            print_styled("May your path be clear. Farewell!", COLOR_TITLE)
            break
        else:
            print_styled("Invalid selection.", COLOR_ERROR)

if __name__ == "__main__":
    main()
