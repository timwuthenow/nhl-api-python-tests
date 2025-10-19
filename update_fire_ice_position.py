#!/usr/bin/env python3
import re

# Read the template
with open('templates/reddit_rankings.html', 'r') as f:
    content = f.read()

# For all tiers, we need to:
# 1. Remove the fire/ice divs from the rank badges
# 2. Add them next to the team logos

# Remove fire/ice from rank badges (all tiers)
pattern = r'(\s*{% if is_biggest_riser %}\s*<div class="absolute -top-1 -right-1 text-xs">🔥</div>\s*{% elif is_biggest_faller %}\s*<div class="absolute -top-1 -right-1 text-xs">🧊</div>\s*{% endif %})'
content = re.sub(pattern, '', content)

# Now add fire/ice indicators next to team logos
# Pattern to find team logo divs and add the indicator after them

# For Elite tier (1-6)
content = re.sub(
    r'(<!-- Team Logo -->\s*<div class="flex-shrink-0 w-6 h-6 mr-1">\s*{% if team\.logo_url %}\s*<img src="{{ team\.logo_url }}"[^>]*>\s*{% endif %}\s*</div>)',
    r'\1\n                            {% if is_biggest_riser %}\n                            <div class="text-lg mr-1 animate-pulse">🔥</div>\n                            {% elif is_biggest_faller %}\n                            <div class="text-lg mr-1 animate-pulse">🧊</div>\n                            {% endif %}',
    content
)

# For other tiers (they have similar structure but without the "Team Logo" comment)
# Find pattern for logo divs in non-Elite tiers
content = re.sub(
    r'(<div class="flex-shrink-0 w-6 h-6 mr-1">\s*{% if team\.logo_url %}\s*<img src="{{ team\.logo_url }}"[^>]*>\s*{% endif %}\s*</div>)(?!\s*{% if is_biggest_riser %})',
    r'\1\n                            {% if is_biggest_riser %}\n                            <div class="text-lg mr-1 animate-pulse">🔥</div>\n                            {% elif is_biggest_faller %}\n                            <div class="text-lg mr-1 animate-pulse">🧊</div>\n                            {% endif %}',
    content
)

# Also ensure the rank badges no longer have the "relative" class since we removed the absolute positioned emojis
content = re.sub(
    r'<div class="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs mr-1 shadow-md relative',
    r'<div class="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs mr-1 shadow-md',
    content
)

# Write the updated template
with open('templates/reddit_rankings.html', 'w') as f:
    f.write(content)

print("Template updated successfully!")
print("- Moved fire/ice emojis from rank badges to next to team logos")
print("- Added animation pulse effect to fire/ice emojis")
print("- Fire/ice effects now show for biggest riser/faller regardless of tier")