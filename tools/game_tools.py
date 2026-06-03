# game_tools.py - Shared game engine tools
from game_engine.dice import roll, roll_check, roll_damage
from game_engine.combat import resolve_combat_turn

def roll_dice(sides: int) -> int:
    """Rolls a single die with specified number of sides."""
    return roll(sides)

def perform_check(modifier: int, dc: int) -> dict:
    """Performs a d20 roll check against a difficulty class."""
    return roll_check(modifier, dc)

def roll_damage_expr(expression: str) -> int:
    """Parses and rolls a damage expression (e.g., '2d6+3')."""
    return roll_damage(expression)

def resolve_combat(character, action_tag_name: str, enemy, environmental_modifiers=None):
    """Resolves a turn of combat between a character and an enemy."""
    return resolve_combat_turn(character, action_tag_name, enemy, environmental_modifiers)
