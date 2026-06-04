import os
import sys
import json
import argparse
import random
import textwrap
import questionary
from questionary import Style
from halo import Halo
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
from game_engine.themes import get_theme, VALID_THEMES_LIST
from agents.dm_agent import DMAgent
from agents.subagents.lore_keeper import LoreKeeper

# Default Terminal Styling Colors
default_theme = get_theme("default")
COLOR_TITLE = default_theme.color_title
COLOR_DM = default_theme.color_dm
COLOR_OPTION = default_theme.color_ooc
COLOR_OOC = default_theme.color_ooc
COLOR_SYSTEM = default_theme.color_system
COLOR_ERROR = default_theme.color_error
COLOR_RESET = "\033[0m"

custom_style = default_theme.q_style

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
    
    choice = questionary.select(
        "Main Menu",
        choices=[
            "1. New Game",
            "2. Continue Campaign",
            "3. Search Campaigns",
            "4. Manage Saves",
            "5. Settings",
            "6. Quit"
        ],
        style=custom_style
    ).ask()
    return choice

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
    import random
    seed = random.randint(1, 10000)
    prompt = f"""You are a creative world builder.
Generate 4 distinct setting pitches for an RPG campaign.
Ensure at least 3 of the pitches are grounded in very traditional, classic tropes (e.g., standard High Fantasy, standard Sci-Fi, standard Cyberpunk). 
The 4th pitch can be a totally wild and unique blend of genres (e.g. post-apocalyptic weird west steampunk).
Each pitch should be a single paragraph including a title and a brief hook.

Use the unique random seed {seed} to guarantee that these 4 pitches are completely different from any previous generations you've made. Give them unique names and unique conflicts.

Format the output as:
1. [Setting Name] (Genres) - Hook description
2. ...
Make each pitch 2 sentences max. Format as a numbered list."""
    
    with Halo(text='Generating worlds...', spinner='dots', color='cyan'):
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

def run_character_creation(llm_client, setting_pitch: str):
    print_styled("\n--- Character Creation ---", COLOR_TITLE)
    name = questionary.text("What is your character's name? ", default="Adventurer", style=custom_style).ask()
    if name is None: return None
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
        
        prompt = f"""For an RPG character named '{name}' in the setting: '{setting_pitch}'.
Generate 3 short, flavor-rich example answers for the question: '{q}'.
Format as:
1. Option A
2. Option B
3. Option C"""
        
        with Halo(text='Consulting the DM...', spinner='dots', color='magenta'):
            options_text = llm_client.generate(prompt)
            
        print_styled(f"\n{options_text}\n", COLOR_DM)
        
        lines = [l.strip() for l in options_text.splitlines() if l.strip() and (l[0].isdigit() or l.startswith("-"))]
        if not lines:
            lines = ["Option A", "Option B", "Option C"]
            
        display_choices = [truncate_choice(l) for l in lines]
        choices = display_choices + ["Custom (Write your own...)", "Cancel Character Creation"]
        
        choice = questionary.select(
            "Choose an option:",
            choices=choices,
            style=custom_style
        ).ask()
        
        if not choice or choice == "Cancel Character Creation":
            return None
        elif choice == "Custom (Write your own...)":
            ans = questionary.text("Describe in your own words: ", style=custom_style).ask()
            if not ans: return None
        else:
            idx = display_choices.index(choice)
            ans = lines[idx]
            
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

    with Halo(text='Calculating attributes...', spinner='dots', color='cyan'):
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
    appearance_prompt = f"Based on this character: Name: {name}, Setting: {setting_pitch}, Stats: {tags}, write a highly evocative 3-sentence physical description of what this character looks like."
    
    with Halo(text='Visualizing character...', spinner='dots', color='magenta'):
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
        print(f"Currency: {char.currency}")
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
        print(f"Currency: {char.currency}")
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
            
    elif "world" in sub or "environment" in sub:
        if not os.path.exists(world_path):
            print_styled("World state not found.", COLOR_ERROR)
            return
        with open(world_path, "r", encoding="utf-8") as f:
            world = WorldState.from_dict(json.load(f))
        print_styled(f"\n--- OOC: World State ---", COLOR_OOC)
        print(f"Turn: {world.turn_count} | Time of Day: {world.time_of_day.upper()}")
        print(f"Genre: {world.setting_genre}")
        if world.environmental_modifiers:
            mods = [f"{m.name} ({m.modifier:+})" for m in world.environmental_modifiers if m.modifier != 0]
            weather = [m.name for m in world.environmental_modifiers if m.modifier == 0]
            parts = []
            if mods: parts.append(", ".join(mods))
            if weather: parts.append(f"Weather: {', '.join(weather)}")
            print(f"Active Modifiers: {'; '.join(parts) if parts else 'None'}")
        else:
            print("Active Modifiers: None")
        if world.active_quests:
            print(f"Active Quests: {', '.join(q.name for q in world.active_quests if q.status == 'active')}")
        print_styled("-" * 30, COLOR_OOC)

    else:
        print_styled("OOC Command Options: 'ooc: stats', 'ooc: inventory', 'ooc: quests', 'ooc: log', 'ooc: lore', 'ooc: world'", COLOR_OOC)

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

def truncate_choice(text: str, length: int = 80) -> str:
    """Truncates a choice string for the TUI menu so it doesn't wrap off-screen."""
    if len(text) > length:
        return text[:length-3] + "..."
    return text

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
        mods = [f"{m.name} ({m.modifier:+})" for m in world.environmental_modifiers if m.modifier != 0]
        weather = [m.name for m in world.environmental_modifiers if m.modifier == 0]
        parts = []
        if mods: parts.append(", ".join(mods))
        if weather: parts.append(f"Weather: {', '.join(weather)}")
        print(f"Active Modifiers: {'; '.join(parts) if parts else 'None'}")
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

def run_travel_mode(llm_client, campaign_slug: str, world: WorldState) -> None:
    from game_engine.world import Location
    while True:
        current = next((l for l in world.discovered_locations if l.id == world.current_location_id), None)
        if not current:
            print_styled("Error: You are lost in the void (current_location_id invalid).", COLOR_ERROR)
            return

        theme_name = current.theme if current else "default"
        theme = get_theme(theme_name)

        print_styled(f"\n--- TRAVEL MODE ---", theme.color_title)
        print_styled(f"You are at: {current.name} ({current.type.title()})", theme.color_ooc)
        print(f"Description: {current.description}")
        
        connected_locs = [l for l in world.discovered_locations if l.id in current.connections]
        
        choices = [f"Travel to: {loc.name}" for loc in connected_locs]
        choices.append(questionary.Separator())
        choices.append("[Explore Unknown Paths]")
        choices.append("Cancel Travel")
        
        choice = questionary.select(
            "Where to?",
            choices=choices,
            style=theme.q_style
        ).ask()
        
        if not choice or choice == "Cancel Travel":
            print_styled("You stay where you are.", theme.color_system)
            return
            
        if choice == "[Explore Unknown Paths]":
            prompt = f"The player is currently at '{current.name}' ({current.description}). Based on the '{world.setting_genre}' genre, generate 1 to 3 brand new, distinct adjacent locations they could travel to from here. Output ONLY a valid JSON list of objects with keys: 'name', 'description', 'type' (e.g. 'street', 'dungeon room', 'wilderness'), and 'theme' (Must be exactly one of: {', '.join(VALID_THEMES_LIST)})."
            
            with Halo(text='Scouting for new paths...', spinner='dots', color='cyan'):
                res = llm_client.generate(prompt)
                
            try:
                import uuid
                import json
                clean = res.replace("```json", "").replace("```", "").strip()
                new_nodes = json.loads(clean)
                for node_data in new_nodes:
                    new_loc = Location(
                        id=str(uuid.uuid4()),
                        name=node_data["name"],
                        description=node_data["description"],
                        type=node_data["type"],
                        discovered_turn=world.turn_count,
                        theme=node_data.get("theme", "default")
                    )
                    new_loc.connections.append(current.id)
                    current.connections.append(new_loc.id)
                    world.discovered_locations.append(new_loc)
                
                world_path = os.path.join("saves", campaign_slug, "world_state.json")
                with open(world_path, "w", encoding="utf-8") as f:
                    json.dump(world.to_dict(), f, indent=4)
                    
                print_styled("You discovered new paths!", theme.color_ooc)
            except Exception as e:
                print_styled(f"Failed to explore: {e}", COLOR_ERROR)
            continue
            
        dest_name = choice.replace("Travel to: ", "")
        dest = next((l for l in connected_locs if l.name == dest_name), None)
        if dest:
            world.current_location_id = dest.id
            world.turn_count += 1
            world_path = os.path.join("saves", campaign_slug, "world_state.json")
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            print_styled(f"\nYou travel to {dest.name}.", theme.color_ooc)
            return

def initialize_world(llm_client, campaign_slug: str) -> bool:
    """Lazily generates missing world components. Returns True if successful or already initialized."""
    states = SaveManager.load_game(campaign_slug)
    if not states: return False
    char_data, world_data, factions, encounters, lore = states
    char = Character.from_dict(char_data)
    world = WorldState.from_dict(world_data)
    
    try:
        if not world.world_bible_summary:
            print_styled("\nForging the World Bible...", COLOR_SYSTEM)
            bible_prompt = f"""Generate a comprehensive 'World Bible' for this setting.
Genre: {world.setting_genre}
Background: {world.setting_description}
Character Backstory: {char.backstory}

You MUST explicitly define:
1. Ancient History & Mythos: The origin of the world and ruling religions/pantheons.
2. Magic System / Technology Rules: Strict rules on how magic or advanced tech works, including costs, limits, and dangers.
3. Core Regions: Define 2-3 massive continents or primary regions. For *each* region, explicitly define:
   - Geopolitics & Power Struggles: Who rules and what the tensions are.
   - Economy & Currency: The primary currency and valuable resources.
   - Taboos & Laws: Unbreakable cultural laws.
   - Geography & Climate: The physical terrain and weather.

Output the World Bible in detailed Markdown format."""
            
            with Halo(text='Drafting the World Bible...', spinner='dots', color='cyan'):
                world_bible_content = llm_client.generate(bible_prompt)
                
            bible_path = os.path.join("saves", campaign_slug, "world_bible.md")
            with open(bible_path, "w", encoding="utf-8") as f:
                f.write(world_bible_content)
                
            summary_prompt = f"Distill the following World Bible into a strict 2-sentence 'Core Theme & Era Summary' that captures the vibe, magic/tech limits, and main conflict of the world.\n\nBible:\n{world_bible_content}"
            
            with Halo(text='Distilling World Summary...', spinner='dots', color='cyan'):
                world.world_bible_summary = llm_client.generate(summary_prompt).strip()
            
            SaveManager.save_game(campaign_slug, char.to_dict(), world.to_dict(), factions, encounters, lore)

        if not world.current_location_id:
            with Halo(text='Weaving the starting Inciting Incident...', spinner='dots', color='yellow'):
                lore_keeper = LoreKeeper(llm_client, campaign_slug)
                lore_keeper.generate_inciting_incident()
            
            loc_prompt = f"Based on the campaign genre '{world.setting_genre}' and the starting scenario, generate the starting location (a specific room, street, or small area). Output ONLY valid JSON with keys: 'name', 'description', 'type' (e.g. 'city', 'dungeon'), and 'theme' (Must be exactly one of: {', '.join(VALID_THEMES_LIST)}). Do not include markdown."
            
            with Halo(text='Generating starting location map...', spinner='dots', color='cyan'):
                loc_res = llm_client.generate(loc_prompt)
                
            import uuid
            from game_engine.world import Location
            clean_res = loc_res.replace("```json", "").replace("```", "").strip()
            loc_data = json.loads(clean_res)
            start_loc = Location(
                id=str(uuid.uuid4()),
                name=loc_data["name"],
                description=loc_data["description"],
                type=loc_data["type"],
                discovered_turn=0,
                theme=loc_data.get("theme", "default")
            )
            
            # Reload world to get the lore keeper updates
            states = SaveManager.load_game(campaign_slug)
            if states:
                _, world_data, _, _, _ = states
                world = WorldState.from_dict(world_data)
                
            world.discovered_locations.append(start_loc)
            world.current_location_id = start_loc.id
            SaveManager.save_game(campaign_slug, char.to_dict(), world.to_dict(), factions, encounters, lore)

        return True
    except Exception as e:
        print_styled(f"\n[Error during world generation: {e}]", COLOR_ERROR)
        print_styled("Please load the save from the main menu to resume setup.", COLOR_SYSTEM)
        return False

def game_loop(llm_client, campaign_slug: str):
    """The active gameplay console loop."""
    global BUDGET_MODE_GLOBAL
    
    # Initialize world if draft
    if not initialize_world(llm_client, campaign_slug):
        return
        
    # Load campaign info
    states = SaveManager.load_game(campaign_slug)
    if not states:
        print_styled("Failed to load campaign.", COLOR_ERROR)
        return
        
    char_data, world_data, factions, encounters, lore = states
    char = Character.from_dict(char_data)
    world = WorldState.from_dict(world_data)
    
    dm = DMAgent(llm_client, campaign_slug, budget_mode=BUDGET_MODE_GLOBAL, verbose=VERBOSE_GLOBAL)
    
    current_loc = next((l for l in world.discovered_locations if l.id == world.current_location_id), None)
    theme_name = current_loc.theme if current_loc else "default"
    theme = get_theme(theme_name)
    
    clear_screen()
    print_styled(f"\nCampaign: {campaign_slug.replace('-', ' ').title()}", theme.color_title)
    print_styled(f"Genre: {world.setting_genre} | DM Persona Traits: {', '.join(world.dm_traits)}", theme.color_system)
    print_styled(f"Logged in as: {char.name}", theme.color_system)
    print_styled(f"Type '/summary' to view status and story recap, 'ooc: help' for stat details, 'quit' to exit.\n", theme.color_system)
    
    # Initial DM description prompt
    print_styled("--- Adventure Logs (compaction-active) ---", theme.color_system)
    dm_log = read_dm_log(campaign_slug)
    print(dm_log)
    print_styled("-----------------------------------------", theme.color_system)
    
    if world.last_narrative:
        response = world.last_narrative
        print_styled(f"\n{response}", theme.color_dm)
    else:
        print_styled("\n[System] The DM is preparing your adventure...", theme.color_system)
        
        if world.turn_count <= 1 and world.active_quests:
            first_quest = world.active_quests[0]
            action_prompt = f"The campaign has just begun! Our inciting incident quest is: '{first_quest.name} - {first_quest.description}'. Narrate the grand opening scene of the campaign. Vividly describe my surroundings and immediately thrust me into the inciting incident of this quest so I know exactly what my goal is!"
        else:
            last_log_lines = dm_log.splitlines()
            last_event = last_log_lines[-1] if last_log_lines else "Waking up in a new world."
            action_prompt = f"Narrate the current situation based on our last event: '{last_event}'"
            
        with Halo(text='The DM is narrating...', spinner='dots', color='yellow'):
            response = dm.process_turn(action_prompt)
            
        print_styled(f"\n{response}", theme.color_dm)
        
        # Save this narrative in world state and write to disk
        world.last_narrative = response
        world_path = os.path.join("saves", campaign_slug, "world_state.json")
        with open(world_path, "w", encoding="utf-8") as f:
            json.dump(world.to_dict(), f, indent=4)
            
    active_choices = extract_choices(response)
    
    while True:
        try:
            current_loc = next((l for l in world.discovered_locations if l.id == world.current_location_id), None)
            theme_name = current_loc.theme if current_loc else "default"
            theme = get_theme(theme_name)
            
            display_choices = [truncate_choice(c) for c in active_choices]
            choices = display_choices + [
                questionary.Separator(),
                "Type custom action...",
                "Travel (Move to new location)",
                "System Menu..."
            ]
            
            choice = questionary.select(
                "What do you do?",
                choices=choices,
                style=theme.q_style
            ).ask()
            
            if not choice:
                continue
                
            if choice == "System Menu...":
                sys_choice = questionary.select(
                    "System Menu:",
                    choices=[
                        "OOC Commands...",
                        "View Campaign Summary",
                        f"Toggle Budget Mode (Current: {'ON' if BUDGET_MODE_GLOBAL else 'OFF'})",
                        "Save",
                        "Quit",
                        "Back"
                    ],
                    style=theme.q_style
                ).ask()
                
                if not sys_choice or sys_choice == "Back":
                    continue
                choice = sys_choice

            if choice == "Quit":
                print_styled("Saving game... Goodbye!", theme.color_system)
                break
                
            if choice == "Type custom action...":
                action = questionary.text("Describe your action: ", style=theme.q_style).ask()
                if not action: continue
            elif choice == "Travel (Move to new location)":
                run_travel_mode(llm_client, campaign_slug, world)
                # After travel, trigger DM to narrate arrival
                action = "I have traveled to a new location. Narrate my arrival and what I see."
            elif choice == "OOC Commands...":
                ooc_choice = questionary.select(
                    "OOC Command:",
                    choices=["stats", "inventory", "quests", "log", "lore", "Back"],
                    style=theme.q_style
                ).ask()
                if ooc_choice and ooc_choice != "Back":
                    handle_ooc_command(f"ooc: {ooc_choice}", campaign_slug)
                continue
            elif choice == "View Campaign Summary":
                show_campaign_summary(campaign_slug, llm_client)
                continue
            elif choice.startswith("Toggle Budget Mode"):
                BUDGET_MODE_GLOBAL = not BUDGET_MODE_GLOBAL
                dm.budget_mode = BUDGET_MODE_GLOBAL
                print_styled(f"Budget Mode is now {'ENABLED' if BUDGET_MODE_GLOBAL else 'DISABLED'}.", theme.color_ooc)
                continue
            elif choice == "Save":
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
            else:
                idx = display_choices.index(choice)
                action = active_choices[idx]
                print_styled(f"\n[Selected: {action}]", theme.color_system)
                
            # Process standard action
            with Halo(text='The DM is thinking...', spinner='dots', color='yellow'):
                # Reload objects in case subagent tools changed them on disk
                dm.budget_mode = BUDGET_MODE_GLOBAL
                dm.verbose = VERBOSE_GLOBAL
                response = dm.process_turn(action)
                
            print_styled(f"\n{response}", theme.color_dm)
            active_choices = extract_choices(response)
            
            # Save the last narrative to world state and update it on disk
            world.last_narrative = response
            world_path = os.path.join("saves", campaign_slug, "world_state.json")
            with open(world_path, "w", encoding="utf-8") as f:
                json.dump(world.to_dict(), f, indent=4)
            
            # Check character health + tick status effects
            char_path = os.path.join("saves", campaign_slug, "character.json")
            with open(char_path, "r", encoding="utf-8") as f:
                char_data = json.load(f)
            char = Character.from_dict(char_data)
            
            # Tick status effects each turn so they expire properly
            expired = char.tick_status_effects()
            if expired:
                print_styled(f"[Status effects expired: {', '.join(expired)}]", theme.color_ooc)
            with open(char_path, "w", encoding="utf-8") as f:
                json.dump(char.to_dict(), f, indent=4)
            
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
    
    selected_pitch = ""
    while True:
        pitches = generate_setting_pitches(llm_client)
        
        print_styled("\n--- Available Settings ---", COLOR_TITLE)
        for i, pitch in enumerate(pitches):
            print_styled(f"{pitch}\n", COLOR_DM)
            
        display_choices = [truncate_choice(p) for p in pitches]
        choices = display_choices + ["Regenerate new options", "Custom (Write your own)", "Cancel and Return to Main Menu"]
        choice = questionary.select(
            "Select a setting:",
            choices=choices,
            style=custom_style
        ).ask()
        
        if not choice or choice == "Cancel and Return to Main Menu": return
        
        if choice == "Regenerate new options":
            continue
        elif choice == "Custom (Write your own)":
            selected_pitch = questionary.text("Describe your custom setting: ", style=custom_style).ask()
            if not selected_pitch: return
            break
        else:
            idx = display_choices.index(choice)
            selected_pitch = pitches[idx]
            break
        
    # Generate DM personality traits
    possible_traits = ["sardonic", "gritty", "theatrical", "mysterious", "noir", "dramatic", "poetic", "cynical", "humorous"]
    dm_traits = random.sample(possible_traits, 2)
    
    # Run character interview
    char = run_character_creation(llm_client, selected_pitch)
    if not char:
        print_styled("\nNew game cancelled.", COLOR_SYSTEM)
        return
    
    # Ask for campaign save name
    campaign_name = questionary.text("What do you want to name this campaign? ", default=f"{char.name}'s Adventure", style=custom_style).ask()
    if not campaign_name:
        print_styled("\nNew game cancelled.", COLOR_SYSTEM)
        return
        
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
    
    print_styled(f"\nWelcome to {campaign_name}!", COLOR_TITLE)
    input("Press Enter to begin...")
    game_loop(llm_client, slug)

def run_load_game(llm_client):
    saves = SaveManager.list_saves()
    if not saves:
        print_styled("No saves found. Start a New Game!", COLOR_ERROR)
        return
        
    print_styled("\n--- Load Campaign ---", COLOR_TITLE)
    choices = [f"{save['campaign_name']} (Character: {save['character_name']}, Genre: {save['genre']}, Turn: {save['turn_count']})" for save in saves]
    choices.append("Back")
    
    choice = questionary.select(
        "Choose save:",
        choices=choices,
        style=custom_style
    ).ask()
    
    if not choice or choice == "Back": return
    idx = choices.index(choice)
    slug = saves[idx]["campaign_slug"]
    game_loop(llm_client, slug)

def run_search_game(llm_client):
    query = questionary.text("Enter campaign name, character name, or genre query: ", style=custom_style).ask()
    if not query: return
    
    results = SaveManager.search_saves(query)
    if not results:
        print_styled("No campaigns matched your query.", COLOR_ERROR)
        return
        
    print_styled(f"\n--- Search Results for '{query}' ---", COLOR_TITLE)
    choices = [f"{save['campaign_name']} (Character: {save['character_name']}, Genre: {save['genre']})" for save in results]
    choices.append("Back")
    
    choice = questionary.select(
        "Choose campaign to load:",
        choices=choices,
        style=custom_style
    ).ask()
    
    if not choice or choice == "Back": return
    idx = choices.index(choice)
    slug = results[idx]["campaign_slug"]
    game_loop(llm_client, slug)

def run_manage_saves():
    saves = SaveManager.list_saves()
    if not saves:
        print_styled("No campaigns found.", COLOR_ERROR)
        return
        
    print_styled("\n--- Manage Saves ---", COLOR_TITLE)
    choices = [f"{save['campaign_name']} [{save['campaign_slug']}]" for save in saves]
    choices.append("Back")
    
    choice = questionary.select(
        "Choose save to DELETE:",
        choices=choices,
        style=custom_style
    ).ask()
    
    if not choice or choice == "Back": return
    idx = choices.index(choice)
    slug = saves[idx]["campaign_slug"]
    
    confirm = questionary.confirm(f"Are you sure you want to delete campaign '{slug}' permanently?", default=False, style=custom_style).ask()
    if confirm:
        SaveManager.delete_save(slug)
        print_styled("Save deleted.", COLOR_OOC)

def run_settings():
    global BUDGET_MODE_GLOBAL, VERBOSE_GLOBAL
    print_styled("\n--- Settings ---", COLOR_TITLE)
    
    choice = questionary.select(
        "Choose option:",
        choices=[
            f"1. Toggle Budget Mode (Currently: {'ENABLED' if BUDGET_MODE_GLOBAL else 'DISABLED'})",
            f"2. Toggle DM Verbose Logs (Currently: {'ENABLED' if VERBOSE_GLOBAL else 'DISABLED'})",
            "3. Back"
        ],
        style=custom_style
    ).ask()
    
    if not choice: return
    
    if choice.startswith("1"):
        BUDGET_MODE_GLOBAL = not BUDGET_MODE_GLOBAL
        print_styled(f"Budget mode is now {'ENABLED' if BUDGET_MODE_GLOBAL else 'DISABLED'}.", COLOR_OOC)
    elif choice.startswith("2"):
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
        choice = display_menu()
        if not choice: break
        
        if choice.startswith("1"):
            run_new_game(client)
        elif choice.startswith("2"):
            run_load_game(client)
        elif choice.startswith("3"):
            run_search_game(client)
        elif choice.startswith("4"):
            run_manage_saves()
        elif choice.startswith("5"):
            run_settings()
        elif choice.startswith("6"):
            print_styled("May your path be clear. Farewell!", COLOR_TITLE)
            break

if __name__ == "__main__":
    main()
