import os
import json
import shutil
from game_engine.dice import roll, roll_check, roll_damage
from game_engine.ability_system import AbilitySet, AbilityTag, GENRE_SEED_TAGS
from game_engine.character import Character
from game_engine.item_system import Item
from game_engine.world import WorldState
from game_engine.combat import generate_enemy, resolve_combat_round, Enemy
from persistence.save_manager import SaveManager, generate_slug
from persistence.log_manager import write_dm_log, read_dm_log

def test_dice():
    print("Testing Dice...")
    assert 1 <= roll(6) <= 6
    assert 1 <= roll(20) <= 20
    
    # Test roll checks
    res = roll_check(3, 10)
    assert "success" in res
    assert res["modifier"] == 3
    assert res["dc"] == 10
    
    # Test damage parser
    val, detail = roll_damage("2d6+3")
    assert val >= 5
    assert "detail" in locals() or detail != ""
    val2, detail2 = roll_damage("1d8-1")
    assert val2 >= 0
    print("[OK] Dice tests passed.")

def test_ability_system():
    print("Testing Ability System...")
    abilities = AbilitySet()
    abilities.add_tag("stealth", 2)
    abilities.add_tag("athletics", 1)
    
    assert abilities.get_modifier("stealth") == 2
    assert abilities.get_modifier("athletics") == 1
    assert abilities.get_modifier("hacking") == 0
    
    # Test fuzzy lookup
    matched = abilities.get_relevant_tags("I try to sneak past using stealth")
    assert len(matched) == 1
    assert matched[0].name == "stealth"
    
    # Test progression (learn-by-doing)
    # stealth is +2. threshold for +2 to +3 is (2+1)*3 = 9 ticks.
    for i in range(8):
        prog, mod, tag = abilities.tick_usage("stealth")
        assert not prog
        assert mod == 2
        
    prog, mod, tag = abilities.tick_usage("stealth")
    assert prog
    assert mod == 3
    assert abilities.get_modifier("stealth") == 3
    print("[OK] Ability system tests passed.")

def test_character_and_items():
    print("Testing Character & Item resolution...")
    char = Character(name="Test Hero", hp=20, max_hp=20)
    assert char.is_alive()
    
    char.take_damage(5)
    assert char.hp == 15
    char.heal(10)
    assert char.hp == 20
    
    # Items
    sword = Item(name="Laser Sword", description="Deals extra laser damage", tag_modifiers={"combat": 2, "damage": 2}, slot="weapon")
    ring = Item(name="Stealth Ring", description="Improves sneak", tag_modifiers={"stealth": 1}, slot="accessory")
    
    char.add_item(sword)
    char.add_item(ring)
    
    assert len(char.inventory) == 2
    
    # Equip
    err = char.equip("Laser Sword")
    assert err is None
    assert "weapon" in char.equipped
    assert len(char.inventory) == 1
    
    # Effective modifiers
    char.abilities.add_tag("combat", 1)
    # Combat modifier should be: innate (1) + weapon (2) = 3
    assert char.get_effective_modifier("combat") == 3
    
    # Status effects
    char.status_effects.append({"name": "poison", "modifiers": {"combat": -1}, "duration": 2})
    assert char.get_effective_modifier("combat") == 2
    
    expired = char.tick_status_effects()
    assert len(expired) == 0
    expired = char.tick_status_effects()
    assert expired == ["poison"]
    assert char.get_effective_modifier("combat") == 3
    print("[OK] Character and item tests passed.")

def test_combat():
    print("Testing Combat resolution...")
    char = Character(name="Hero", hp=20, max_hp=20)
    char.abilities.add_tag("combat", 2)
    
    enemy = generate_enemy("Thug", 2, "cyberpunk")
    assert enemy.hp > 0
    assert enemy.threat_level == 2
    
    enemies = [enemy]
    initiative_order = [{"id": "player", "speed": 2}, {"id": "enemy_0", "speed": 4}]
    res = resolve_combat_round(char, "combat", 0, enemies, initiative_order)
    assert "round_events" in res
    assert len(res["round_events"]) > 0
    print("[OK] Combat engine tests passed.")

def test_persistence():
    print("Testing Save Manager & Log Manager...")
    campaign_name = "Verification Campaign"
    slug = generate_slug(campaign_name)
    assert slug == "verification-campaign"
    
    char = Character(name="Arthur", hp=18)
    char.abilities.add_tag("swordsmanship", 3)
    
    world = WorldState(setting_genre="Fantasy", current_location="Tavern")
    factions = {"factions": {"guild": {"name": "Guild", "reputation": 10}}}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [{"title": "Old Book", "content": "Magic exists"}], "secrets": []}
    
    # Save
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    assert os.path.exists(os.path.join("saves", slug, "meta.json"))
    
    # List & Search
    saves = SaveManager.list_saves()
    assert len(saves) >= 1
    assert saves[0]["campaign_name"] == campaign_name
    
    search_res = SaveManager.search_saves("arthur")
    assert len(search_res) >= 1
    
    # Load
    loaded = SaveManager.load_game(slug)
    assert loaded is not None
    c_data, w_data, f_data, e_data, l_data = loaded
    
    loaded_char = Character.from_dict(c_data)
    assert loaded_char.name == "Arthur"
    assert loaded_char.abilities.get_modifier("swordsmanship") == 3
    
    loaded_world = WorldState.from_dict(w_data)
    assert loaded_world.setting_genre == "Fantasy"
    
    # Log manager
    write_dm_log(slug, "Entered the dark cavern.")
    log = read_dm_log(slug)
    assert "Entered the dark cavern" in log
    
    # Cleanup verification campaign directory
    SaveManager.delete_save(slug)
    assert not os.path.exists(os.path.join("saves", slug))
    print("[OK] Persistence tests passed.")

def test_dm_context():
    print("Testing DM Context injection...")
    import sys
    from agents.dm_agent import DMAgent
    from llm_clients import MockClient
    
    campaign_name = "Context Test Campaign"
    slug = generate_slug(campaign_name)
    
    char = Character(name="Arthur", hp=18)
    world = WorldState(setting_genre="Fantasy", current_location="Tavern")
    # Add active quest
    world.add_quest("q1", "Find Merlin", "Locate the wizard Merlin in the woods.")
    # Add completed quest (should not show up as active)
    world.add_quest("q2", "Defeat Rat", "Kill the rat in the cellar.")
    world.update_quest_status("q2", "completed")
    
    factions = {"factions": {}}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {
        "unlocked_lore": [{"title": "Excalibur History", "content": "The sword in the stone."}],
        "secrets": ["Lancelot loves Guinevere."]
    }
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    # Initialize DM agent with MockClient
    client = MockClient(model_name="mock-model")
    dm = DMAgent(client, slug, budget_mode=False)
    
    # Mock self.run to capture the query sent to the LLM
    captured_query = None
    def mock_run(query, max_turns=6, verbose=False, agent_name="DM"):
        nonlocal captured_query
        captured_query = query
        return "Thought: Done.\nAnswer: Okay."
        
    dm.run = mock_run
    dm.process_turn("Hello")
    
    assert captured_query is not None
    
    assert "Active Quests: [SIDE] Find Merlin (Locate the wizard Merlin in the woods.)" in captured_query, "Active quest not found in context"
    assert "Defeat Rat" not in captured_query, "Completed quest should not be in active quests context"
    assert "Unlocked Lore: Excalibur History" in captured_query, "Unlocked lore not found in context"
    assert "Secrets: Lancelot loves Guinevere." in captured_query, "Secret not found in context"
    
    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] DM Context injection tests passed.")

def test_faction_clocks():
    print("Testing Faction Clocks...")
    from agents.subagents.faction_weaver import FactionWeaver
    
    campaign_name = "Faction Clocks Test Campaign"
    slug = generate_slug(campaign_name)
    
    char = Character(name="Arthur", hp=18)
    world = WorldState(setting_genre="Fantasy", current_location="Tavern", turn_count=0)
    factions = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    # Initialize FactionWeaver
    from llm_clients import MockClient
    client = MockClient(model_name="mock-model")
    fw = FactionWeaver(client, slug)
    
    # Add a clock using add_faction_clock tool
    res = fw.tools["add_faction_clock"]("corporation | gate | Slums Gate | Gate build | 3 | Gate locked down | gate_modifier | -3")
    assert "Registered faction clock" in res
    
    # Verify clock exists on disk
    path = os.path.join("saves", slug, "factions.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "corporation" in data["factions"]
    clocks = data["factions"]["corporation"]["clocks"]
    assert len(clocks) == 1
    assert clocks[0]["id"] == "gate"
    assert clocks[0]["turns_remaining"] == 3
    
    # Progress turn count by 2 in world state
    world.turn_count = 2
    world_path = os.path.join("saves", slug, "world_state.json")
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=4)
        
    # Trigger heartbeat (should tick clock down by 2)
    fw.heartbeat(budget_mode=True)
    
    # Check that turns remaining is now 1
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    clocks = data["factions"]["corporation"]["clocks"]
    assert len(clocks) == 1
    assert clocks[0]["turns_remaining"] == 1
    
    # Progress turn count by another 2 (total 4 turns elapsed)
    world.turn_count = 4
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=4)
        
    # Trigger heartbeat (should trigger and resolve clock)
    fw.heartbeat(budget_mode=True)
    
    # Check that clock is removed and event is recorded
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    clocks = data["factions"]["corporation"]["clocks"]
    assert len(clocks) == 0
    # Budget mode may also append a random scheming event (20% chance), so assert >= 1 event
    assert len(data["faction_events"]) >= 1
    clock_events = [e for e in data["faction_events"] if "CLOCK TRIGGERED" in e["event"]]
    assert len(clock_events) == 1
    assert "Faction project 'Slums Gate' completed: Gate locked down" in clock_events[0]["event"]
    
    # Verify environmental modifier is applied to world state
    with open(world_path, "r", encoding="utf-8") as f:
        w_data = json.load(f)
    world_loaded = WorldState.from_dict(w_data)
    mods = world_loaded.environmental_modifiers
    assert len(mods) == 1
    assert mods[0].name == "gate_modifier"
    assert mods[0].modifier == -3
    
    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] Faction Clocks tests passed.")

def test_inventory_systems():
    print("Testing Inventory Systems (Disassembly, Consumables, Crafting)...")
    from agents.dm_agent import DMAgent
    from llm_clients import MockClient
    
    campaign_name = "Inventory Systems Test Campaign"
    slug = generate_slug(campaign_name)
    
    char = Character(name="Arthur", hp=10, max_hp=20) # Wounded
    # Add items to inventory for testing
    from game_engine.item_system import Item
    char.add_item(Item(name="Rusty Metal Blade", description="A rusty iron blade.", slot="weapon"))
    char.add_item(Item(name="Broken Battery", description="A leaking power cell."))
    
    world = WorldState(setting_genre="Fantasy", current_location="Tavern", is_camping=True)
    factions = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    client = MockClient(model_name="mock-model")
    dm = DMAgent(client, slug)
    
    # 1. Test disassembly of Rusty Metal Blade (should yield Junk Metal)
    res = dm.tools["disassemble_item"]("Rusty Metal Blade")
    assert "Disassembled" in res
    assert "Junk Metal" in res
    
    # Verify inventory state
    char_path = os.path.join("saves", slug, "character.json")
    with open(char_path, "r", encoding="utf-8") as f:
        char_data = json.load(f)
    loaded_char = Character.from_dict(char_data)
    assert not any(i.name == "Rusty Metal Blade" for i in loaded_char.inventory)
    assert any(i.name == "Junk Metal" for i in loaded_char.inventory)
    
    # 2. Test disassembly of Broken Battery (should yield Scrap Electronics and Copper Wire)
    res = dm.tools["disassemble_item"]("Broken Battery")
    assert "Scrap Electronics" in res
    assert "Copper Wire" in res
    
    with open(char_path, "r", encoding="utf-8") as f:
        char_data = json.load(f)
    loaded_char = Character.from_dict(char_data)
    assert not any(i.name == "Broken Battery" for i in loaded_char.inventory)
    assert any(i.name == "Scrap Electronics" for i in loaded_char.inventory)
    assert any(i.name == "Copper Wire" for i in loaded_char.inventory)
    
    # 3. Test modify_inventory adding a consumable with charges and description
    res = dm.tools["modify_inventory"]("add | Healing Salve | heals 8 HP | None | True | 2")
    assert "Successfully added" in res
    
    with open(char_path, "r", encoding="utf-8") as f:
        char_data = json.load(f)
    loaded_char = Character.from_dict(char_data)
    salve = next(i for i in loaded_char.inventory if i.name == "Healing Salve")
    assert salve.consumable is True
    assert salve.charges == 2
    assert salve.tag_modifiers.get("heal") == 8
    
    # 4. Test use_consumable_item on Healing Salve (should heal 8 HP and decrement charges to 1)
    res = dm.tools["use_consumable_item"]("Healing Salve")
    assert "Successfully used" in res
    assert "Healed 8 HP" in res
    assert "1 charges remaining" in res
    
    with open(char_path, "r", encoding="utf-8") as f:
        char_data = json.load(f)
    loaded_char = Character.from_dict(char_data)
    assert loaded_char.hp == 18 # 10 + 8
    salve = next(i for i in loaded_char.inventory if i.name == "Healing Salve")
    assert salve.charges == 1
    
    # 5. Test use_consumable_item again (should remove item from inventory)
    res = dm.tools["use_consumable_item"]("Healing Salve")
    assert "consumed and removed" in res
    
    with open(char_path, "r", encoding="utf-8") as f:
        char_data = json.load(f)
    loaded_char = Character.from_dict(char_data)
    assert not any(i.name == "Healing Salve" for i in loaded_char.inventory)
    
    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] Inventory Systems tests passed.")

def test_contextual_verification():
    print("Testing Contextual Verification prompt constraints...")
    from agents.dm_agent import DMAgent
    from llm_clients import MockClient
    
    campaign_name = "Verification Prompts Campaign"
    slug = generate_slug(campaign_name)
    
    char = Character(name="Arthur", hp=20, max_hp=20)
    world = WorldState(setting_genre="Fantasy", current_location="Tavern")
    factions = {"factions": {}, "faction_events": [], "last_tick_turn": 0}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}
    
    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)
    
    client = MockClient(model_name="mock-model")
    dm = DMAgent(client, slug)
    
    prompt = dm._build_dynamic_prompt()
    assert "Player Validity & Spatial Limits" in prompt
    assert "Contested Resolution" in prompt
    assert "roll_ability_check" in prompt
    
    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] Contextual Verification prompt tests passed.")

def test_story_spine_and_cast():
    print("Testing Story Spine & Cast System...")
    from game_engine.world import StoryBeat, StorySpine, WorldState
    from game_engine.character import Character
    from agents.subagents.lore_keeper import LoreKeeper
    from llm_clients import MockClient

    # 1. StoryBeat & StorySpine Serialization Round-Trip
    beat1 = StoryBeat(id=1, name="The Hook", dramatic_question="Why did Aldric flee?", tonal_direction="Suspense", status="active", pressure_mechanism="Nemesis approaches")
    beat2 = StoryBeat(id=2, name="The Deepening", dramatic_question="Who is the Collector?", tonal_direction="Mystery", status="pending", pressure_mechanism="Clocks tick")
    spine = StorySpine(theme="Betrayal and redemption", beats=[beat1, beat2], current_beat=1)

    spine_dict = spine.to_dict()
    assert spine_dict["theme"] == "Betrayal and redemption"
    assert len(spine_dict["beats"]) == 2
    assert spine_dict["beats"][0]["name"] == "The Hook"
    assert spine_dict["beats"][1]["status"] == "pending"

    spine_loaded = StorySpine.from_dict(spine_dict)
    assert spine_loaded.theme == "Betrayal and redemption"
    assert len(spine_loaded.beats) == 2
    assert spine_loaded.beats[0].dramatic_question == "Why did Aldric flee?"
    assert spine_loaded.beats[1].pressure_mechanism == "Clocks tick"

    # 2. StorySpine.advance_beat() logic
    next_beat = spine.advance_beat("Aldric's diary was found.")
    assert next_beat is not None
    assert next_beat.id == 2
    assert next_beat.status == "active"
    assert spine.beats[0].status == "resolved"
    assert spine.beats[0].resolution_notes == "Aldric's diary was found."
    assert spine.current_beat == 2

    last_beat = spine.advance_beat("The Collector is Aldric's brother.")
    assert last_beat is None
    assert spine.beats[1].status == "resolved"

    # 3. Character structured fields & backward compatibility
    old_char_data = {
        "name": "Old Arthur",
        "backstory": "A brave knight.",
        "abilities": {}
    }
    char_loaded = Character.from_dict(old_char_data)
    assert char_loaded.name == "Old Arthur"
    assert char_loaded.backstory == "A brave knight."
    assert char_loaded.childhood_event == ""
    assert char_loaded.past_life == ""
    assert char_loaded.fear == ""
    assert char_loaded.sentimental_item_story == ""

    # 4. WorldState story_spine backward compatibility
    old_world_data = {
        "setting_genre": "Cyberpunk",
        "current_location": "Neon Street"
    }
    world_loaded = WorldState.from_dict(old_world_data)
    assert world_loaded.setting_genre == "Cyberpunk"
    assert world_loaded.story_spine is not None
    assert len(world_loaded.story_spine.beats) == 0

    # 5. Cast management and promotion (LoreKeeper tools check)
    campaign_name = "Cast Test Campaign"
    slug = generate_slug(campaign_name)
    char = Character(name="Hero")
    world = WorldState(setting_genre="Fantasy")
    world.story_spine = StorySpine(theme="Test theme", beats=[
        StoryBeat(id=1, name="Hook", dramatic_question="?", tonal_direction="?", status="active")
    ])
    factions = {"factions": {}}
    encounters = {}
    lore = {}

    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)

    client = MockClient(model_name="mock-model")
    lk = LoreKeeper(client, slug)

    # Test store_cast_member
    res_cm = lk.tools["store_cast_member"]("anchor_01 | Master Aldric | anchor | Weathered man | Wise | Secret diary | Mentor | Hook anchor")
    assert "stored in cast" in res_cm

    # Test promote_npc
    res_promo = lk.tools["promote_npc"]("Sera | promoted | Tall woman | Calculative | Double agent | Ally | Info source")
    assert "promoted to cast" in res_promo

    # Verify cast file on disk
    cast_path = os.path.join("saves", slug, "cast.json")
    assert os.path.exists(cast_path)
    with open(cast_path, "r", encoding="utf-8") as f:
        cast_data = json.load(f)
    assert "anchor_01" in cast_data["spine_characters"]
    assert cast_data["spine_characters"]["anchor_01"]["name"] == "Master Aldric"
    assert len(cast_data["promoted_npcs"]) == 1

    # Test modify_cast_member
    res_mod = lk.tools["modify_cast_member"]("anchor_01 | status | dead")
    assert "status = dead" in res_mod
    with open(cast_path, "r", encoding="utf-8") as f:
        cast_data = json.load(f)
    assert cast_data["spine_characters"]["anchor_01"]["status"] == "dead"

    # Test advance_spine_beat
    res_adv = lk.tools["advance_spine_beat"]("Aldric is dead.")
    assert "all beats resolved" in res_adv.lower()
    
    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] Story Spine & Cast System tests passed.")

def test_register_and_move_location():
    print("Testing register_and_move_location tool...")
    from agents.dm_agent import DMAgent
    from llm_clients import MockClient
    import uuid
    from game_engine.world import Location

    campaign_name = "Location Tool Test"
    slug = generate_slug(campaign_name)

    char = Character(name="Arthur", hp=18)
    start_loc_id = "start_node_id"
    start_loc = Location(
        id=start_loc_id,
        name="Tavern",
        description="A cozy tavern",
        type="tavern",
        discovered_turn=0
    )
    world = WorldState(setting_genre="Fantasy")
    world.discovered_locations = [start_loc]
    world.current_location_id = start_loc_id
    world.turn_count = 1

    factions = {"factions": {}}
    encounters = {"active_encounter": None, "recent_loot": []}
    lore = {"unlocked_lore": [], "secrets": []}

    SaveManager.save_game(campaign_name, char.to_dict(), world.to_dict(), factions, encounters, lore)

    client = MockClient(model_name="mock-model")
    dm = DMAgent(client, slug, budget_mode=False)

    # 1. Test moving to a new location
    result1 = dm.tools["register_and_move_location"]("Hemlock's General Store | A dusty store | shop")
    assert "Successfully moved player to new location" in result1
    
    # Reload world state to check changes
    world_path = os.path.join("saves", slug, "world_state.json")
    with open(world_path, "r", encoding="utf-8") as f:
        world_data = json.load(f)
    world = WorldState.from_dict(world_data)
    
    assert len(world.discovered_locations) == 2
    new_loc = [l for l in world.discovered_locations if l.id != start_loc_id][0]
    assert new_loc.name == "Hemlock's General Store"
    assert new_loc.description == "A dusty store"
    assert new_loc.type == "shop"
    assert world.current_location_id == new_loc.id
    
    # Check bidirectional connections
    assert start_loc_id in new_loc.connections
    old_loc = [l for l in world.discovered_locations if l.id == start_loc_id][0]
    assert new_loc.id in old_loc.connections

    # 2. Test moving to an existing location (dedup check)
    result2 = dm.tools["register_and_move_location"]("Tavern | A cozy tavern | tavern")
    assert "Moved player to existing location: 'Tavern'" in result2

    # Reload world state
    with open(world_path, "r", encoding="utf-8") as f:
        world_data = json.load(f)
    world = WorldState.from_dict(world_data)

    assert len(world.discovered_locations) == 2  # No new location should be created
    assert world.current_location_id == start_loc_id

    # 3. Test invalid format
    result3 = dm.tools["register_and_move_location"]("Invalid Input")
    assert "Error: Format must be" in result3

    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] register_and_move_location tests passed.")

def main():
    import sys
    print("========================================")
    print("   Starting RPG Game Engine Test Suite  ")
    print("========================================\n")
    try:
        test_dice()
        test_ability_system()
        test_character_and_items()
        test_combat()
        test_persistence()
        test_dm_context()
        test_faction_clocks()
        test_inventory_systems()
        test_contextual_verification()
        test_story_spine_and_cast()
        test_register_and_move_location()
        print("\n========================================")
        print("  ALL TESTS PASSED SUCCESSFULLY! (100%)")
        print("========================================")
    except AssertionError as e:
        import traceback
        print(f"\n[FAIL] Assertion Failed: {e}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
