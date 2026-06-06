# 7. Attribute Fallback Checks for Fairer System Resolution

## Status
Approved

## Context
Characters in Lore Spinner start with only a small set of 4 specific skill tags. When checks are made for any skill outside of these 4 tags, the check defaults to a `+0` modifier. Furthermore, the DM Agent historically defaulted almost all checks to a Difficulty Class (DC) of 12. Combined, this meant players had a flat 45% chance of success on any action they did not have a specific tag for, even if the action should have been easy or standard.

We want to introduce a mechanism to make ability checks fairer and more progressive, without introducing a full D&D sheet that would clutter the narrative-first design.

## Decision
We decided to implement the following:
1. **Attribute Tags**: Seed every character with 6 core baseline "Attribute Tags": `strength`, `dexterity`, `intellect`, `fortitude`, `presence`, and `perception`.
2. **Backstory Seeding**: Update character creation to distribute starting modifiers based on backstory (e.g., one +2, two +1s, and three +0s to base attributes), in addition to 2-3 setting-specific skill tags.
3. **Fallback Check Tool Syntax**: Update the `roll_ability_check` tool to accept a 3-part syntax: `skill_name | fallback_attribute | DC` (e.g., `lockpicking | dexterity | 15`).
4. **Engine Fallback Logic**: Modify `Character.get_effective_modifier()` to check if the specific skill tag is innate to the character. If not, it falls back to the provided `fallback_attribute` modifier. Equipped item/environmental modifiers for the specific skill or attribute are combined contextually.
5. **DM DC Selection Guidelines**: Provide the DM Agent with explicit guidelines for DC selection (DC 5: Very Easy, DC 10: Easy, DC 15: Medium, DC 20: Hard, DC 25: Very Hard) and instruct them to dynamically choose and output the appropriate DC and fallback attributes.

## Consequences
- **Fairer Math**: Players get base stat modifiers for a wider range of actions, avoiding unfair +0 defaults on standard tasks.
- **Flexible & Scaleable**: The system scales cleanly across genres (cyberpunk, fantasy) because fallbacks are determined contextually by the DM rather than hardcoded skill-to-attribute mappings.
- **Maintained Immersion**: Numeric attributes remain hidden or only show in Stats Mode, preserving the core game aesthetic.
