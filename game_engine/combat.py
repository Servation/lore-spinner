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
            "defense": self.defense
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
            defense=data.get("defense", 10)
        )


def generate_enemy(name: str, threat_level: int, genre: str) -> Enemy:
    """Generates an enemy scaled to a threat level and setting genre."""
    # Scale HP and Defense based on threat level
    hp = 5 + threat_level * 5 + roll(4)
    defense = 9 + threat_level * 2
    
    # Setup some tags based on threat level
    enemy_abilities = AbilitySet()
    
    genre = genre.lower()
    if genre == "fantasy":
        weapon_damage = "1d6" if threat_level <= 2 else "1d8+1" if threat_level <= 4 else "2d6+2"
        enemy_abilities.add_tag("combat", threat_level)
        enemy_abilities.add_tag("athletics", threat_level - 1 if threat_level > 1 else 0)
    elif genre == "cyberpunk":
        weapon_damage = "1d6" if threat_level <= 2 else "1d8" if threat_level <= 4 else "2d8"
        enemy_abilities.add_tag("marksmanship", threat_level)
        enemy_abilities.add_tag("evasion", threat_level - 1 if threat_level > 1 else 0)
    elif genre == "post-apocalyptic":
        weapon_damage = "1d4+1" if threat_level <= 2 else "1d8" if threat_level <= 4 else "1d10+2"
        enemy_abilities.add_tag("melee_weapons", threat_level)
        enemy_abilities.add_tag("firearms", threat_level)
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
        defense=defense
    )


def resolve_combat_turn(
    character: Character, 
    action_tag_name: str, 
    enemy: Enemy, 
    environmental_modifiers: Optional[List[AbilityTag]] = None
) -> Dict[str, Any]:
    """Resolves a single exchange in combat.
    
    1. Player rolls vs Enemy Defense.
    2. If hit: roll damage, subtract enemy HP.
    3. If enemy is still alive: enemy counterattacks.
    4. Enemy rolls counterattack vs Player Defense (derived from Player's agility/evasion/combat tag or base 10).
    5. If enemy hits: roll enemy damage, subtract player HP.
    6. Tick tag progression if player successfully used their tag.
    
    Returns a details dictionary.
    """
    results = {
        "player_hit": False,
        "player_roll_detail": {},
        "player_damage": 0,
        "player_damage_detail": "",
        "enemy_hit": False,
        "enemy_roll": 0,
        "enemy_damage": 0,
        "enemy_damage_detail": "",
        "enemy_dead": False,
        "player_dead": False,
        "progression_triggered": False,
        "new_modifier": 0
    }
    
    # --- 1. Player attack ---
    player_mod = character.get_effective_modifier(action_tag_name, environmental_modifiers)
    check_res = roll_check(player_mod, enemy.defense)
    results["player_roll_detail"] = check_res
    
    if check_res["success"]:
        results["player_hit"] = True
        
        # Calculate damage based on equipped weapon or default 1d6
        weapon = character.equipped.get("weapon")
        dmg_expr = "1d6"
        if weapon and "damage" in weapon.tag_modifiers:
            # item has damage spec
            dmg_expr = f"1d6+{weapon.tag_modifiers['damage']}"
        elif action_tag_name.lower() in ["spellcasting", "lasers"]:
            dmg_expr = "1d8"
            
        # Add player damage modifier (capped)
        dmg, dmg_detail = roll_damage(dmg_expr)
        # Apply bonus from action tag (half of modifier, minimum 0)
        bonus = max(0, player_mod // 2)
        if bonus > 0:
            dmg += bonus
            dmg_detail += f" + {bonus} (tag bonus)"
            
        dmg_taken = enemy.take_damage(dmg)
        results["player_damage"] = dmg_taken
        results["player_damage_detail"] = dmg_detail
        
        # Tick tag usage on success
        prog, new_mod = character.abilities.tick_usage(action_tag_name)
        results["progression_triggered"] = prog
        results["new_modifier"] = new_mod
        
        if not enemy.is_alive():
            results["enemy_dead"] = True
            return results
            
    # --- 2. Enemy counterattack ---
    if enemy.is_alive():
        # Player Defense: base 10 + player's evasion or combat tag modifier
        if "evasion" in character.abilities.tags:
            evasion_tag = "evasion"
        elif "athletics" in character.abilities.tags:
            evasion_tag = "athletics"
        elif "combat" in character.abilities.tags:
            evasion_tag = "combat"
        else:
            evasion_tag = "evasion"
            
        player_def = 10 + character.get_effective_modifier(evasion_tag, environmental_modifiers)
        
        # Armor reduces damage or increases defense
        armor = character.equipped.get("armor")
        if armor:
            # armor adds defense or damage reduction
            player_def += armor.tag_modifiers.get("defense", 1)
            
        # Enemy roll d20 + threat_level
        enemy_atk_mod = enemy.threat_level + enemy.abilities.get_modifier("combat")
        enemy_roll = roll(20)
        enemy_total = enemy_roll + enemy_atk_mod
        results["enemy_roll"] = enemy_total
        
        if enemy_total >= player_def:
            results["enemy_hit"] = True
            
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
            results["enemy_damage"] = dmg_taken
            results["enemy_damage_detail"] = f"{dmg_detail} = {dmg_taken}"
            
            if not character.is_alive():
                results["player_dead"] = True
                
    return results
