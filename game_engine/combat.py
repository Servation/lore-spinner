from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
from game_engine.ability_system import AbilitySet, AbilityTag
from game_engine.character import Character
from game_engine.dice import roll_check, roll_damage, roll

@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    threat_level: int  # 1 to 5
    abilities: AbilitySet = field(default_factory=AbilitySet)
    weapon_damage: str = "1d6"
    defense: int = 10  # Base DC to hit them
    speed: int = 2     # Used for calculating combat initiative

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        damage = max(0, amount)
        self.hp = max(0, self.hp - damage)
        return damage

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "threat_level": self.threat_level,
            "abilities": self.abilities.to_dict(),
            "weapon_damage": self.weapon_damage,
            "defense": self.defense,
            "speed": self.speed
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Enemy":
        if not data:
            return cls(name="Hostile", hp=10, max_hp=10, threat_level=1)
        return cls(
            name=data.get("name", "Hostile"),
            hp=data.get("hp", 10),
            max_hp=data.get("max_hp", 10),
            threat_level=data.get("threat_level", 1),
            abilities=AbilitySet.from_dict(data.get("abilities", {})),
            weapon_damage=data.get("weapon_damage", "1d6"),
            defense=data.get("defense", 10),
            speed=data.get("speed", 2)
        )


def generate_enemy(name: str, threat_level: int, genre: str) -> Enemy:
    """Generates an enemy scaled to a threat level and setting genre."""
    # Scale HP and Defense based on threat level
    # Lower base HP slightly for "swarm" approach since there are multiple
    hp = max(1, 3 + threat_level * 3 + roll(4))
    defense = 10 + threat_level
    speed = 2 + threat_level
    
    # Setup some tags based on threat level
    enemy_abilities = AbilitySet()
    
    genre = genre.lower()
    if "fantasy" in genre:
        weapon_damage = "1d6" if threat_level <= 2 else "1d8+1" if threat_level <= 4 else "2d6+2"
        enemy_abilities.add_tag("combat", threat_level)
        enemy_abilities.add_tag("athletics", threat_level - 1 if threat_level > 1 else 0)
    elif "cyberpunk" in genre or "cyber" in genre:
        weapon_damage = "1d6" if threat_level <= 2 else "1d8" if threat_level <= 4 else "2d8"
        enemy_abilities.add_tag("marksmanship", threat_level)
        enemy_abilities.add_tag("evasion", threat_level - 1 if threat_level > 1 else 0)
    elif "post-apoc" in genre or "apocalyptic" in genre or "wasteland" in genre:
        weapon_damage = "1d4+1" if threat_level <= 2 else "1d8" if threat_level <= 4 else "1d10+2"
        enemy_abilities.add_tag("melee_weapons", threat_level)
        enemy_abilities.add_tag("firearms", threat_level)
    elif "sci-fi" in genre or "space" in genre:
        weapon_damage = "1d6" if threat_level <= 2 else "1d8" if threat_level <= 4 else "2d6"
        enemy_abilities.add_tag("marksmanship", threat_level)
        enemy_abilities.add_tag("tech", threat_level - 1 if threat_level > 1 else 0)
    elif "horror" in genre or "gothic" in genre:
        weapon_damage = "1d6" if threat_level <= 2 else "1d8+1" if threat_level <= 4 else "2d6+2"
        enemy_abilities.add_tag("terror", threat_level)
        enemy_abilities.add_tag("resilience", threat_level)
    elif "western" in genre or "frontier" in genre:
        weapon_damage = "1d6" if threat_level <= 2 else "1d8" if threat_level <= 4 else "1d10+1"
        enemy_abilities.add_tag("firearms", threat_level)
        enemy_abilities.add_tag("grit", threat_level - 1 if threat_level > 1 else 0)
    else:
        weapon_damage = "1d6"
        enemy_abilities.add_tag("combat", threat_level)

    return Enemy(
        name=name,
        hp=hp,
        max_hp=hp,
        threat_level=threat_level,
        abilities=enemy_abilities,
        weapon_damage=weapon_damage,
        defense=defense,
        speed=speed
    )


def resolve_combat_round(
    character: Character, 
    action_tag_name: str, 
    target_index: int,
    enemies: List[Enemy], 
    initiative_order: List[Dict[str, Any]],
    environmental_modifiers: Optional[List[AbilityTag]] = None
) -> Dict[str, Any]:
    """Resolves a full round of combat for all participants based on initiative order.
    
    1. Iterates through initiative_order.
    2. If it's the player's turn: Player attacks target_index.
    3. If it's an enemy's turn: Enemy attacks player using Evasion mechanic.
    
    Returns a comprehensive details dictionary for the DM to narrate.
    """
    results = {
        "round_events": [],
        "progression_triggered": False,
        "new_modifier": 0,
        "player_dead": False,
        "all_enemies_dead": False
    }
    
    for turn_info in initiative_order:
        entity_id = turn_info["id"]
        
        # Stop processing if player is dead
        if not character.is_alive():
            results["player_dead"] = True
            break
            
        # Stop processing if all enemies are dead
        living_enemies = [e for e in enemies if e.is_alive()]
        if not living_enemies:
            results["all_enemies_dead"] = True
            break
            
        if entity_id == "player":
            # --- Player's Turn ---
            if target_index < 0 or target_index >= len(enemies):
                results["round_events"].append({"actor": "player", "action": "invalid_target"})
                continue
                
            target = enemies[target_index]
            if not target.is_alive():
                results["round_events"].append({"actor": "player", "action": "target_already_dead", "target_name": target.name})
                continue
                
            player_mod = character.get_effective_modifier(action_tag_name, environmental_modifiers)
            check_res = roll_check(player_mod, target.defense)
            
            event = {
                "actor": "player",
                "target": target.name,
                "hit": check_res["success"],
                "roll_detail": check_res,
                "damage": 0,
                "damage_detail": ""
            }
            
            if check_res["success"]:
                # Calculate damage based on equipped weapon or default 1d6
                weapon = character.equipped.get("weapon")
                dmg_expr = "1d6"
                if weapon and "damage" in weapon.tag_modifiers:
                    dmg_expr = f"1d6+{weapon.tag_modifiers['damage']}"
                elif action_tag_name.lower() in ["spellcasting", "lasers"]:
                    dmg_expr = "1d8"
                    
                dmg, dmg_detail = roll_damage(dmg_expr)
                bonus = max(0, player_mod // 2)
                if bonus > 0:
                    dmg += bonus
                    dmg_detail += f" + {bonus} (tag bonus)"
                    
                dmg_taken = target.take_damage(dmg)
                event["damage"] = dmg_taken
                event["damage_detail"] = dmg_detail
                event["target_dead"] = not target.is_alive()
                
                # Tick tag usage on success
                prog, new_mod, leveled_tag = character.abilities.tick_usage(action_tag_name)
                if prog:
                    results["progression_triggered"] = True
                    results["new_modifier"] = new_mod
                    
                    physical_tags = ["athletics", "combat", "fortitude", "stamina", "melee_weapons", "brawling", "evasion"]
                    if leveled_tag in physical_tags:
                        character.max_hp += 5
                        character.hp += 5
                        results["round_events"].append({
                            "actor": "system",
                            "action": "hp_growth",
                            "message": f"Physical ability '{leveled_tag}' leveled up! Max HP increased by 5."
                        })
                    
            results["round_events"].append(event)
            
        elif entity_id.startswith("enemy_"):
            # --- Enemy's Turn ---
            enemy_idx = int(entity_id.split("_")[1])
            if enemy_idx < 0 or enemy_idx >= len(enemies):
                continue
                
            enemy = enemies[enemy_idx]
            if not enemy.is_alive():
                continue # Dead enemies don't get a turn
                
            # Enemy attacks player. Player rolls Evasion.
            if "evasion" in character.abilities.tags:
                evasion_tag = "evasion"
            elif "athletics" in character.abilities.tags:
                evasion_tag = "athletics"
            elif "combat" in character.abilities.tags:
                evasion_tag = "combat"
            else:
                evasion_tag = "evasion"
                
            player_evasion_mod = character.get_effective_modifier(evasion_tag, environmental_modifiers)
            player_def_roll = roll(20) + player_evasion_mod + 10 # Base 10 + d20 + evasion
            
            # Armor reduces damage or increases defense
            armor = character.equipped.get("armor")
            if armor:
                player_def_roll += armor.tag_modifiers.get("defense", 1)
                
            enemy_atk_mod = enemy.threat_level + (enemy.threat_level // 2)
            enemy_atk_roll = roll(20) + enemy_atk_mod
            
            hit = enemy_atk_roll >= player_def_roll
            
            event = {
                "actor": enemy.name,
                "target": "player",
                "hit": hit,
                "atk_roll": enemy_atk_roll,
                "def_roll": player_def_roll,
                "damage": 0,
                "damage_detail": ""
            }
            
            if hit:
                # Enemy damage
                dmg, dmg_detail = roll_damage(enemy.weapon_damage)
                
                # Apply armor damage reduction
                dr = 0
                if armor:
                    dr = armor.tag_modifiers.get("damage_reduction", 0)
                final_dmg = max(1, dmg - dr)
                if dr > 0:
                    dmg_detail += f" - {dr} (armor)"
                    
                dmg_taken = character.take_damage(final_dmg)
                event["damage"] = dmg_taken
                event["damage_detail"] = f"{dmg_detail} = {dmg_taken}"
                
            results["round_events"].append(event)
            
    if not character.is_alive():
        results["player_dead"] = True
    living_enemies = [e for e in enemies if e.is_alive()]
    if not living_enemies:
        results["all_enemies_dead"] = True
        
    return results
