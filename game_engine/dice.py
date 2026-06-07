import random
import re
from typing import Dict, Any, Tuple

def roll(sides: int) -> int:
    """Rolls a single N-sided die."""
    if sides < 1:
        return 0
    return random.randint(1, sides)

def roll_check(modifier: int, difficulty_class: int, advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]:
    """Resolves a d20 roll check against a target difficulty class."""
    rolls = [roll(20)]
    
    if advantage and not disadvantage:
        rolls.append(roll(20))
        d20_roll = max(rolls)
    elif disadvantage and not advantage:
        rolls.append(roll(20))
        d20_roll = min(rolls)
    else:
        d20_roll = rolls[0]
        
    total = d20_roll + modifier
    success = total >= difficulty_class
    margin = total - difficulty_class
    
    critical_success = (d20_roll == 20)
    critical_failure = (d20_roll == 1)
    
    if critical_success:
        success = True
    elif critical_failure:
        success = False
        
    return {
        "roll": d20_roll,
        "raw_rolls": rolls,
        "modifier": modifier,
        "total": total,
        "dc": difficulty_class,
        "success": success,
        "margin": margin,
        "critical_success": critical_success,
        "critical_failure": critical_failure,
        "advantage": advantage,
        "disadvantage": disadvantage
    }

def roll_damage(dice_expr: str) -> Tuple[int, str]:
    """Parses a dice expression (e.g. '2d6+3', '1d8', '3d4-1') and returns (rolled_total, detail_string)."""
    expr = dice_expr.strip().replace(" ", "").lower()
    
    # Matches patterns like `2d6+3`, `1d8`, `3d4-1`
    match = re.match(r"^(\d+)d(\d+)(?:([+-])(\d+))?$", expr)
    if not match:
        # Fallback if invalid format
        try:
            val = int(expr)
            return val, f"{val}"
        except ValueError:
            return 0, "0"
            
    num_dice = int(match.group(1))
    sides = int(match.group(2))
    operator = match.group(3)
    modifier = int(match.group(4)) if match.group(4) else 0
    
    rolls = [roll(sides) for _ in range(num_dice)]
    sum_rolls = sum(rolls)
    
    total = sum_rolls
    mod_str = ""
    if operator == "+":
        total += modifier
        mod_str = f"+{modifier}"
    elif operator == "-":
        total -= modifier
        mod_str = f"-{modifier}"
        
    rolls_detail = "+".join(map(str, rolls))
    if num_dice > 1 or modifier != 0:
        detail = f"({rolls_detail}){mod_str} = {total}"
    else:
        detail = f"{total}"
        
    return max(0, total), detail
