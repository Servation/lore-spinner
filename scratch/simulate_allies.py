import sys
import os
import copy

sys.path.append(os.path.abspath("d:/agent-game"))

from game_engine.character import Character
from game_engine.combat import resolve_combat_round, generate_enemy, Ally
from game_engine.dice import roll

def run_simulation_with_allies(player_base: Character, ally_base: Ally, threat_level: int, enemy_count: int, iterations: int = 100):
    wins = 0
    deaths = 0
    total_rounds_won = 0
    total_hp_remaining = 0
    
    for _ in range(iterations):
        char = copy.deepcopy(player_base)
        char.hp = char.max_hp
        
        # Setup ally
        ally = copy.deepcopy(ally_base)
        ally.hp = ally.max_hp
        allies = [ally]
        
        enemies = [generate_enemy(f"Mob_{i}", threat_level, "fantasy") for i in range(enemy_count)]
        
        # Roll initiative
        initiatives = [
            {"id": "player", "name": "Player", "roll": roll(20) + char.speed},
            {"id": "ally_0", "name": "Rhys", "roll": roll(20) + ally.speed}
        ]
        for i, e in enumerate(enemies):
            initiatives.append({"id": f"enemy_{i}", "name": e.name, "roll": roll(20) + e.speed})
        initiatives.sort(key=lambda x: x["roll"], reverse=True)
        
        rounds = 0
        while char.hp > 0 and any(e.hp > 0 for e in enemies):
            rounds += 1
            # Player always attacks the first alive enemy
            try:
                target_idx = next(i for i, e in enumerate(enemies) if e.hp > 0)
            except StopIteration:
                break
            resolve_combat_round(char, "combat", target_idx, enemies, initiatives, None, allies)
            
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
        "win_rate": win_rate,
        "avg_rounds": avg_rounds,
        "avg_hp_remaining": avg_hp_remaining
    }

if __name__ == "__main__":
    print("Running Combat Ally Simulation...\n")
    
    # Base Player (Level 1 equivalent)
    base_player = Character(name="SimPlayer")
    base_player.max_hp = 20
    base_player.hp = 20
    base_player.speed = 3
    base_player.abilities.add_tag("combat", 2)
    base_player.abilities.add_tag("evasion", 2)
    
    # Friendly Ally (Rhys, Threat 2)
    rhys = Ally(name="Rhys", hp=15, max_hp=15, threat_level=2, defense=12, speed=3)
    
    print("--- Simulating Player Solo vs Swarms ---")
    # 3x Threat 2
    res_solo_2 = run_simulation_with_allies(base_player, Ally(name="Ghost", hp=0, max_hp=0, threat_level=0), threat_level=2, enemy_count=3, iterations=200)
    print(f"Player Solo vs 3x Threat 2 | Win Rate: {res_solo_2['win_rate']}% | Avg HP Left: {res_solo_2['avg_hp_remaining']:.1f}")
    
    # 3x Threat 3
    res_solo_3 = run_simulation_with_allies(base_player, Ally(name="Ghost", hp=0, max_hp=0, threat_level=0), threat_level=3, enemy_count=3, iterations=200)
    print(f"Player Solo vs 3x Threat 3 | Win Rate: {res_solo_3['win_rate']}% | Avg HP Left: {res_solo_3['avg_hp_remaining']:.1f}")

    print("\n--- Simulating Player + Rhys (Threat 2 Ally) vs Swarms ---")
    # 3x Threat 2 with Rhys
    res_ally_2 = run_simulation_with_allies(base_player, rhys, threat_level=2, enemy_count=3, iterations=200)
    print(f"Player + Rhys vs 3x Threat 2 | Win Rate: {res_ally_2['win_rate']}% | Avg HP Left: {res_ally_2['avg_hp_remaining']:.1f}")
    
    # 3x Threat 3 with Rhys
    res_ally_3 = run_simulation_with_allies(base_player, rhys, threat_level=3, enemy_count=3, iterations=200)
    print(f"Player + Rhys vs 3x Threat 3 | Win Rate: {res_ally_3['win_rate']}% | Avg HP Left: {res_ally_3['avg_hp_remaining']:.1f}")
