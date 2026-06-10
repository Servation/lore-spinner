from dataclasses import dataclass, field
from typing import Dict, List, Optional
from game_engine.ability_system import AbilitySet, AbilityTag
from game_engine.item_system import Item

@dataclass
class Character:
    name: str
    backstory: str = ""
    appearance: str = ""
    childhood_event: str = ""        # NEW — Defining childhood moment
    past_life: str = ""              # NEW — Pre-adventure occupation
    fear: str = ""                   # NEW — Concrete scenario + emotional wound
    sentimental_item_story: str = "" # NEW — Why the carried item matters
    abilities: AbilitySet = field(default_factory=AbilitySet)
    hp: int = 20
    max_hp: int = 20
    currency: int = 0
    inventory: List[Item] = field(default_factory=list)
    equipped: Dict[str, Item] = field(default_factory=dict)  # slots: "weapon", "armor", "accessory"
    status_effects: List[dict] = field(default_factory=list)  # e.g., [{"name": "poison", "modifiers": {"stamina": -2}, "duration": 3}]
    position: str = "Start"
    relationships: Dict[str, str] = field(default_factory=dict)
    miracles: int = 1  # Number of times the character can miraculously survive a fatal injury
    speed: int = 2     # Used for calculating combat initiative
    combat_style: str = ""
    combat_maneuvers: List[str] = field(default_factory=list)

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        """Deducts HP and returns the damage actually taken."""
        damage = max(0, amount)
        self.hp = max(0, self.hp - damage)
        return damage

    def heal(self, amount: int) -> int:
        """Restores HP capped at max_hp and returns the amount healed."""
        heal_amt = max(0, amount)
        old_hp = self.hp
        self.hp = min(self.max_hp, self.hp + heal_amt)
        return self.hp - old_hp

    def add_item(self, item: Item) -> None:
        self.inventory.append(item)

    def remove_item(self, item_name: str) -> bool:
        clean_name = item_name.strip().lower()
        for idx, item in enumerate(self.inventory):
            if item.name.lower() == clean_name:
                self.inventory.pop(idx)
                return True
        return False

    def equip(self, item_name: str) -> Optional[str]:
        """Equips an item from the inventory. Returns None on success, or an error message."""
        clean_name = item_name.strip().lower()
        item_to_equip = None
        for item in self.inventory:
            if item.name.lower() == clean_name:
                item_to_equip = item
                break
                
        if not item_to_equip:
            return f"Item '{item_name}' not found in inventory."
            
        if not item_to_equip.slot:
            return f"Item '{item_to_equip.name}' is not equipable."
            
        slot = item_to_equip.slot.lower()
        
        # Remove from inventory
        self.inventory.remove(item_to_equip)
        
        # Unequip current item in that slot if it exists
        if slot in self.equipped:
            old_item = self.equipped[slot]
            self.inventory.append(old_item)
            
        self.equipped[slot] = item_to_equip
        return None

    def unequip(self, slot: str) -> Optional[str]:
        """Unequips an item from the given slot and returns it to inventory."""
        clean_slot = slot.strip().lower()
        if clean_slot not in self.equipped:
            return f"No item equipped in slot '{slot}'."
            
        item = self.equipped[clean_slot]
        del self.equipped[clean_slot]
        self.inventory.append(item)
        return None

    def get_effective_modifier(self, tag_name: str, environmental_modifiers: Optional[List[AbilityTag]] = None, fallback_attribute: Optional[str] = None) -> int:
        """Calculates the combined modifier for a tag name, incorporating:
        1. Innate ability tag (falls back to fallback_attribute if tag_name is not innate)
        2. Equipped items
        3. Status effects
        4. Environmental modifiers (if passed)
        """
        clean_tag = tag_name.strip().lower()
        clean_fallback = fallback_attribute.strip().lower() if fallback_attribute else None
        
        # 1. Innate (falls back to clean_fallback if clean_tag is not present in character abilities)
        innate_mod = 0
        if clean_tag in self.abilities.tags:
            innate_mod = self.abilities.get_modifier(clean_tag)
        elif clean_fallback and clean_fallback in self.abilities.tags:
            innate_mod = self.abilities.get_modifier(clean_fallback)
            
        # 2. Equipped items (check both specific tag and fallback)
        item_mod = 0
        for slot, item in self.equipped.items():
            if clean_tag in item.tag_modifiers:
                item_mod += item.tag_modifiers[clean_tag]
            elif clean_fallback and clean_fallback in item.tag_modifiers:
                item_mod += item.tag_modifiers[clean_fallback]
                
        # 3. Status effects (check both)
        status_mod = 0
        for effect in self.status_effects:
            effect_mods = effect.get("modifiers", {})
            if clean_tag in effect_mods:
                status_mod += effect_mods[clean_tag]
            elif clean_fallback and clean_fallback in effect_mods:
                status_mod += effect_mods[clean_fallback]
                
        # 4. Environmental modifiers (check both)
        env_mod = 0
        if environmental_modifiers:
            for env_tag in environmental_modifiers:
                if env_tag.name.lower() == clean_tag:
                    env_mod += env_tag.modifier
                elif clean_fallback and env_tag.name.lower() == clean_fallback:
                    env_mod += env_tag.modifier
                    
        return innate_mod + item_mod + status_mod + env_mod


    def tick_status_effects(self) -> List[str]:
        """Decrements status effect durations. Removes expired ones. Returns list of expired effect names."""
        expired = []
        active = []
        for effect in self.status_effects:
            effect["duration"] -= 1
            if effect["duration"] <= 0:
                expired.append(effect["name"])
            else:
                active.append(effect)
        self.status_effects = active
        return expired

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "backstory": self.backstory,
            "appearance": self.appearance,
            "childhood_event": self.childhood_event,
            "past_life": self.past_life,
            "fear": self.fear,
            "sentimental_item_story": self.sentimental_item_story,
            "abilities": self.abilities.to_dict(),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "currency": self.currency,
            "inventory": [item.to_dict() for item in self.inventory],
            "equipped": {slot: item.to_dict() for slot, item in self.equipped.items()},
            "status_effects": self.status_effects,
            "position": self.position,
            "relationships": self.relationships,
            "miracles": self.miracles,
            "speed": self.speed,
            "combat_style": self.combat_style,
            "combat_maneuvers": self.combat_maneuvers
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        if not data:
            return cls(name="Unnamed Hero")
            
        char = cls(
            name=data.get("name", "Unnamed Hero"),
            backstory=data.get("backstory", ""),
            appearance=data.get("appearance", ""),
            childhood_event=data.get("childhood_event", ""),
            past_life=data.get("past_life", ""),
            fear=data.get("fear", ""),
            sentimental_item_story=data.get("sentimental_item_story", ""),
            abilities=AbilitySet.from_dict(data.get("abilities", {})),
            hp=data.get("hp", 20),
            max_hp=data.get("max_hp", 20),
            currency=data.get("currency", 0),
            inventory=[Item.from_dict(item_data) for item_data in data.get("inventory", [])],
            equipped={slot: Item.from_dict(item_data) for slot, item_data in data.get("equipped", {}).items()},
            status_effects=data.get("status_effects", []),
            position=data.get("position", "Start"),
            relationships=data.get("relationships", {}),
            miracles=data.get("miracles", 1),
            speed=data.get("speed", 2),
            combat_style=data.get("combat_style", ""),
            combat_maneuvers=data.get("combat_maneuvers", [])
        )
        return char
