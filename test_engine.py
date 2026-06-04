import os
import json
import shutil
from game_engine.dice import roll, roll_check, roll_damage
from game_engine.ability_system import AbilitySet, AbilityTag, GENRE_SEED_TAGS
from game_engine.character import Character
from game_engine.item_system import Item
from game_engine.world import WorldState
from game_engine.combat import generate_enemy, resolve_combat_turn, Enemy
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
    
    res = resolve_combat_turn(char, "combat", enemy)
    assert "player_hit" in res
    assert "enemy_hit" in res or res["enemy_dead"]
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
    
    assert "Active Quests: Find Merlin (Locate the wizard Merlin in the woods.)" in captured_query, "Active quest not found in context"
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
    assert len(data["faction_events"]) == 1
    assert "CLOCK TRIGGERED: Faction project 'Slums Gate' completed: Gate locked down" in data["faction_events"][0]["event"]
    
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
    
    world = WorldState(setting_genre="Fantasy", current_location="Tavern")
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
    assert "Player Claim Verification" in prompt
    assert "Contested Resolution" in prompt
    assert "roll_ability_check" in prompt
    
    # Cleanup
    SaveManager.delete_save(slug)
    print("[OK] Contextual Verification prompt tests passed.")

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
        print("\n========================================")
        print("  ALL TESTS PASSED SUCCESSFULLY! (100%)")
        print("========================================")
    except AssertionError as e:
        print(f"\n[FAIL] Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
