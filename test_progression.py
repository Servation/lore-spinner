import sys
import os

sys.path.append(os.path.abspath("d:/agent-game"))

from game_engine.character import Character
from game_engine.combat import resolve_combat_round, Enemy

char = Character(name="Tester")
char.hp = 20
char.max_hp = 20
# Add a tag at level 2. Threshold to level 3 is (2+1)*3 = 9 uses.
char.abilities.add_tag("athletics", 2)
# Set usage to 8 so one more use triggers level up.
char.abilities.tags["athletics"].usage_count = 8

enemy = Enemy(name="Dummy", hp=10, max_hp=10, threat_level=1, defense=5, speed=1)
enemies = [enemy]

initiatives = [{"id": "player", "name": "Player", "roll": 20}, {"id": "enemy_0", "name": "Dummy", "roll": 10}]

print(f"Before combat: HP={char.hp}/{char.max_hp}, athletics={char.abilities.get_modifier('athletics')}, usage={char.abilities.tags['athletics'].usage_count}")

res = resolve_combat_round(char, "athletics", 0, enemies, initiatives, None)

print(f"\nAfter combat: HP={char.hp}/{char.max_hp}, athletics={char.abilities.get_modifier('athletics')}, usage={char.abilities.tags['athletics'].usage_count}")

print("\nEvents:")
for e in res["round_events"]:
    print(e)
