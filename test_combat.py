import sys
import os

# Add current directory to path
sys.path.append(os.path.abspath("d:/agent-game"))

from game_engine.combat import generate_enemy, resolve_combat_round, Enemy
from game_engine.character import Character
from game_engine.dice import roll

char = Character(name="Tester")
char.hp = 20
char.max_hp = 20
char.speed = 4
char.abilities.add_tag("combat", 2)
char.abilities.add_tag("evasion", 3)

enemies = [
    generate_enemy("Goblin A", 1, "fantasy"),
    generate_enemy("Goblin B", 1, "fantasy")
]

initiatives = [
    {"id": "player", "name": "Player", "roll": roll(20) + char.speed},
    {"id": "enemy_0", "name": enemies[0].name, "roll": roll(20) + enemies[0].speed},
    {"id": "enemy_1", "name": enemies[1].name, "roll": roll(20) + enemies[1].speed}
]

initiatives.sort(key=lambda x: x["roll"], reverse=True)

print("Initiative Order:")
for i in initiatives:
    print(f"{i['name']} ({i['roll']})")
    
res = resolve_combat_round(char, "combat", 0, enemies, initiatives, None)
print("\nRound Results:")
for event in res["round_events"]:
    print(event)

print(f"\nPlayer HP: {char.hp}/{char.max_hp}")
print(f"Enemy 0 HP: {enemies[0].hp}/{enemies[0].max_hp}")
print(f"Enemy 1 HP: {enemies[1].hp}/{enemies[1].max_hp}")
