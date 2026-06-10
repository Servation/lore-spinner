from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class AbilityTag:
    name: str
    modifier: int
    usage_count: int = 0
    source: str = "innate"  # "innate", "item", "environment"

@dataclass
class AbilitySet:
    tags: Dict[str, AbilityTag] = field(default_factory=dict)

    def get_modifier(self, tag_name: str) -> int:
        """Returns the modifier for a specific tag name, or 0 if not present."""
        clean_name = tag_name.strip().lower()
        if clean_name in self.tags:
            return self.tags[clean_name].modifier
        return 0

    def get_relevant_tags(self, action_query: str) -> List[AbilityTag]:
        """Finds any tags whose name is contained in the action query."""
        clean_query = action_query.strip().lower()
        matched = []
        # Exact match check first
        if clean_query in self.tags:
            return [self.tags[clean_query]]
            
        for name, tag in self.tags.items():
            if name in clean_query or clean_query in name:
                matched.append(tag)
        return matched

    def add_tag(self, name: str, modifier: int, source: str = "innate") -> None:
        """Adds a new tag or updates an existing one if source is different or modifier is higher."""
        clean_name = name.strip().lower()
        self.tags[clean_name] = AbilityTag(name=clean_name, modifier=modifier, source=source)

    def remove_tag(self, name: str) -> None:
        """Removes a tag from the character."""
        clean_name = name.strip().lower()
        if clean_name in self.tags:
            del self.tags[clean_name]

    def tick_usage(self, tag_name: str) -> Tuple[bool, int, str]:
        """Increments usage counter for a tag and checks for level-up.
        
        Progression threshold: usage needed = (current_modifier + 1) * 3
        Returns (progression_triggered, new_modifier).
        """
        clean_name = tag_name.strip().lower()
        if clean_name not in self.tags:
            return False, 0, clean_name
            
        tag = self.tags[clean_name]
        
        # Don't level up item-based or environment-based tags
        if tag.source != "innate":
            return False, tag.modifier, clean_name
            
        tag.usage_count += 1
        
        # Determine threshold
        # If modifier is negative, threshold is smaller to get back to 0
        current_mod = tag.modifier
        if current_mod < 0:
            threshold = abs(current_mod) * 2
        else:
            threshold = (current_mod + 1) * 3
            
        if tag.usage_count >= threshold:
            tag.modifier += 1
            tag.usage_count = 0
            return True, tag.modifier, clean_name
            
        return False, tag.modifier, clean_name

    def get_combined_modifier(self, tag_names: List[str]) -> int:
        """Computes the sum of modifiers for the specified list of tags."""
        total = 0
        for name in tag_names:
            total += self.get_modifier(name)
        return total

    def to_dict(self) -> dict:
        return {
            name: {
                "name": tag.name,
                "modifier": tag.modifier,
                "usage_count": tag.usage_count,
                "source": tag.source
            }
            for name, tag in self.tags.items()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AbilitySet":
        obj = cls()
        if not data:
            return obj
        for name, info in data.items():
            obj.tags[name] = AbilityTag(
                name=info.get("name", name),
                modifier=info.get("modifier", 0),
                usage_count=info.get("usage_count", 0),
                source=info.get("source", "innate")
            )
        return obj


# Master seed list of tags by genre for references/generation
GENRE_SEED_TAGS = {
    "fantasy": {
        "swordsmanship": "Melee combat with blades and melee weapons",
        "archery": "Ranged combat using bows and crossbows",
        "spellcasting": "Channeling arcane, divine, or elemental magic",
        "stealth": "Moving silently and remaining unseen",
        "lockpicking": "Bypassing physical locks and disabling traps",
        "alchemy": "Brewing potions, poisons, and herbal mixtures",
        "athletics": "Physical feats like climbing, jumping, and swimming",
        "diplomacy": "Persuading others and peaceful negotiations",
        "lore": "Knowledge of history, magical phenomena, and world secrets"
    },
    "cyberpunk": {
        "hacking": "Bypassing firewalls, writing code, and hijacking systems",
        "cyberware_control": "Overcharging or mastering cybernetic augmentations",
        "streetwise": "Knowledge of gangs, informants, black markets, and city layouts",
        "marksmanship": "Precision shooting with pistols, rifles, and SMGs",
        "evasion": "Dodging bullets and escaping physical danger",
        "electronics": "Wiring, hardware hacking, and modifying gadgets",
        "intimidation": "Using cybernetic presence or threats to coerce others",
        "perception": "Noticing hidden details and optical overlays",
        "stealth": "Sneaking through security grids and avoiding sensors"
    },
    "post-apocalyptic": {
        "scavenging": "Finding useful items, scrap, and supplies in ruins",
        "survival": "Finding clean water, hunting, and tracking in the wastes",
        "barter": "Trading and haggling with scarce resources",
        "first_aid": "Tending to wounds, infections, and radiation sickness",
        "melee_weapons": "Fighting with clubs, axes, and scrap-metal blades",
        "firearms": "Maintaining and shooting cobbled-together weapons",
        "mechanics": "Fixing engines, generators, and scrap machinery",
        "fortitude": "Resisting poisons, diseases, and extreme exhaustion",
        "stealth": "Avoiding patrols, mutants, and raiders"
    },
    "sci-fi": {
        "astrogation": "Plotting hyperspace courses and pilot navigation",
        "lasers": "Combat with energy weapons and plasma rifles",
        "xenobiology": "Understanding alien species and extraterrestrial life",
        "hacking": "Slicing mainframes and artificial intelligences",
        "engineering": "Repairing starship drives, shields, and life support",
        "negotiation": "Galactic diplomacy and trade agreements",
        "robotics": "Programming and disabling drones and synthetics",
        "stamina": "Adapting to high-gravity or low-oxygen environments",
        "tactics": "Coordinating fleet maneuvers or tactical positioning"
    },
    "weird west": {
        "quick_draw": "Drawing and shooting firearms with blinding speed",
        "horsemanship": "Riding, controlling, and bonding with horses",
        "dueling": "One-on-one shootout focus and composure",
        "gambling": "Playing cards, cheating, and spotting bluffs",
        "brawling": "Fist-fighting and barroom combat",
        "tracking": "Following footprints, animal trails, and wind paths",
        "grit": "Resisting pain, fear, and supernatural dread",
        "mysticism": "Interacting with native spirits or occult hexes",
        "demolitions": "Using dynamite and black powder effectively"
    }
}
