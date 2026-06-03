from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class Item:
    name: str
    description: str
    tag_modifiers: Dict[str, int] = field(default_factory=dict)  # e.g., {"stealth": 2, "hacking": -1}
    slot: Optional[str] = None  # "weapon", "armor", "accessory", or None (not equipable)
    consumable: bool = False
    charges: int = 0  # for consumable or charged items

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "tag_modifiers": self.tag_modifiers,
            "slot": self.slot,
            "consumable": self.consumable,
            "charges": self.charges
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        if not data:
            return cls(name="Unknown Item", description="No description.")
        return cls(
            name=data.get("name", "Unknown Item"),
            description=data.get("description", ""),
            tag_modifiers=data.get("tag_modifiers", {}),
            slot=data.get("slot"),
            consumable=data.get("consumable", False),
            charges=data.get("charges", 0)
        )
