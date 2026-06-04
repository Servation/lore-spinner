import sys
import os
import copy

sys.path.append(os.path.abspath("d:/agent-game"))

from game_engine.character import Character
from game_engine.combat import resolve_combat_round, generate_enemy
from game_engine.dice import roll

def run_simulation(player_base: Character, threat_level: int, enemy_count: int, iterations: int = 100):
    wins = 0
    deaths = 0
    total_rounds_won = 0
    total_hp_remaining = 0
    
    for _ in range(iterations):
        char = copy.deepcopy(player_base)
        char.hp = char.max_hp
        
        enemies = [generate_enemy(f"Mob_{i}", threat_level, "fantasy") for i in range(enemy_count)]
        
        # Roll initiative
        initiatives = [{"id": "player", "name": "Player", "roll": roll(20) + char.speed}]
        for i, e in enumerate(enemies):
            initiatives.append({"id": f"enemy_{i}", "name": e.name, "roll": roll(20) + e.speed})
        initiatives.sort(key=lambda x: x["roll"], reverse=True)
        
        rounds = 0
        while char.hp > 0 and any(e.hp > 0 for e in enemies):
            rounds += 1
            # Player always attacks the first alive enemy
            target_idx = next(i for i, e in enumerate(enemies) if e.hp > 0)
            resolve_combat_round(char, "combat", target_idx, enemies, initiatives, None)
            
        if char.hp > 0:
            wins += 1
            total_rounds_won += rounds
            total_hp_remaining += char.hp
        else:
            deaths += 1
            
    win_rate = (wins / iterations) * 100
    avg_rounds = total_rounds_won / wins if wins > 0 else 0
    avg_hp_remaining = total_hp_remaining / wins if wins > 0 else 0
    
    return {
        "threat": threat_level,
        "count": enemy_count,
        "win_rate": win_rate,
        "avg_rounds": avg_rounds,
        "avg_hp_remaining": avg_hp_remaining
    }

if __name__ == "__main__":
    print("Running Combat Balance Simulation...\n")
    
    # Base Player (Level 1 equivalent)
    base_player = Character(name="SimPlayer")
    base_player.max_hp = 20
    base_player.hp = 20
    base_player.speed = 3
    base_player.abilities.add_tag("combat", 2)
    base_player.abilities.add_tag("evasion", 2)
    
    # Test 1: Single Enemy Scaling
    print("--- Test 1: 1v1 Enemy Scaling (Threat 1 to 5) ---")
    for t in range(1, 6):
        res = run_simulation(base_player, threat_level=t, enemy_count=1, iterations=100)
        print(f"Threat {t} | Win Rate: {res['win_rate']}% | Avg Rounds: {res['avg_rounds']:.1f} | Avg HP Left: {res['avg_hp_remaining']:.1f}")

    # Test 2: Multi-Enemy Scaling
    print("\n--- Test 2: 1v3 Enemy Swarm (Threat 1 to 3) ---")
    for t in range(1, 4):
        res = run_simulation(base_player, threat_level=t, enemy_count=3, iterations=100)
        print(f"3x Threat {t} | Win Rate: {res['win_rate']}% | Avg Rounds: {res['avg_rounds']:.1f} | Avg HP Left: {res['avg_hp_remaining']:.1f}")
        
    # Mid-game Player (Level 5 equivalent)
    mid_player = Character(name="SimPlayer_Mid")
    mid_player.max_hp = 35
    mid_player.hp = 35
    mid_player.speed = 4
    mid_player.abilities.add_tag("combat", 4)
    mid_player.abilities.add_tag("evasion", 4)
    # Give mid player a weapon
    from game_engine.item_system import Item
    weapon = Item("Steel Sword", "weapon", tag_modifiers={"damage": 2, "combat": 1})
    mid_player.inventory.append(weapon)
    mid_player.equipped["weapon"] = weapon
    
    print("\n--- Test 3: Mid-Game Player vs Boss (Threat 5 to 8) ---")
    for t in range(5, 9):
        res = run_simulation(mid_player, threat_level=t, enemy_count=1, iterations=100)
        print(f"Threat {t} Boss | Win Rate: {res['win_rate']}% | Avg Rounds: {res['avg_rounds']:.1f} | Avg HP Left: {res['avg_hp_remaining']:.1f}")
