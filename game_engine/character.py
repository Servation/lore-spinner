from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from game_engine.ability_system import AbilitySet, AbilityTag
from game_engine.item_system import Item

@dataclass
class Character:
    name: str
    backstory: str = ""
    appearance: str = ""
    abilities: AbilitySet = field(default_factory=AbilitySet)
    hp: int = 20
    max_hp: int = 20
    inventory: List[Item] = field(default_factory=list)
    equipped: Dict[str, Item] = field(default_factory=dict)  # slots: "weapon", "armor", "accessory"
    status_effects: List[dict] = field(default_factory=list)  # e.g., [{"name": "poison", "modifiers": {"stamina": -2}, "duration": 3}]
    position: str = "Start"
    relationships: Dict[str, str] = field(default_factory=dict)

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

    def get_effective_modifier(self, tag_name: str, environmental_modifiers: Optional[List[AbilityTag]] = None) -> int:
        """Calculates the combined modifier for a tag name, incorporating:
        1. Innate ability tag
        2. Equipped items
        3. Status effects
        4. Environmental modifiers (if passed)
        """
        clean_tag = tag_name.strip().lower()
        modifier = 0
        
        # 1. Innate
        modifier += self.abilities.get_modifier(clean_tag)
        
        # 2. Equipped items
        for slot, item in self.equipped.items():
            if clean_tag in item.tag_modifiers:
                modifier += item.tag_modifiers[clean_tag]
                
        # 3. Status effects
        for effect in self.status_effects:
            effect_mods = effect.get("modifiers", {})
            if clean_tag in effect_mods:
                modifier += effect_mods[clean_tag]
                
        # 4. Environmental modifiers
        if environmental_modifiers:
            for env_tag in environmental_modifiers:
                if env_tag.name.lower() == clean_tag:
                    modifier += env_tag.modifier
                    
        return modifier

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
            "abilities": self.abilities.to_dict(),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "inventory": [item.to_dict() for item in self.inventory],
            "equipped": {slot: item.to_dict() for slot, item in self.equipped.items()},
            "status_effects": self.status_effects,
            "position": self.position,
            "relationships": self.relationships
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        if not data:
            return cls(name="Unnamed Hero")
            
        char = cls(
            name=data.get("name", "Unnamed Hero"),
            backstory=data.get("backstory", ""),
            appearance=data.get("appearance", ""),
            abilities=AbilitySet.from_dict(data.get("abilities", {})),
            hp=data.get("hp", 20),
            max_hp=data.get("max_hp", 20),
            inventory=[Item.from_dict(item_data) for item_data in data.get("inventory", [])],
            equipped={slot: Item.from_dict(item_data) for slot, item_data in data.get("equipped", {}).items()},
            status_effects=data.get("status_effects", []),
            position=data.get("position", "Start"),
            relationships=data.get("relationships", {})
        )
        return char
