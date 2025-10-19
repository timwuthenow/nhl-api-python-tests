#!/usr/bin/env python3
import re

# Read the template
with open('templates/reddit_rankings.html', 'r') as f:
    content = f.read()

# 1. Update tier names with puns
content = content.replace(
    'Elite Tier (1-6)',
    'Stanley Cup or Bust (1-6)'
)
content = content.replace(
    'Good Tier (7-13)',  
    'Playoff Push (7-13)'
)
content = content.replace(
    'Middle Tier (14-20)',
    'Mushy Middle (14-20)'
)
content = content.replace(
    'Struggling Tier (21-27)',
    'Trade Deadline Sellers (21-27)'
)
# Fallin' for Gavin is already done

# 2. Replace team_abbrev with team_name for full names in the display
content = re.sub(
    r'<span class="font-bold text-xs" style="color: {{ team\.team_color }}DD;">{{ team\.team_abbrev }}</span>',
    r'<span class="font-bold text-xs" style="color: {{ team.team_color }}DD;">{{ team.team_name }}</span>',
    content
)

# 3. Add fire/ice checks to all Good tier rows
good_tier_pattern = r'({% for team in rankings if team.rank >= 7 and team.rank <= 13 %})\s*\n\s*<div class="flex items-center p-1 rounded bg-white border border-yellow-300'
good_tier_replacement = r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n                        <div class="flex items-center p-1 rounded bg-white border \n                             {% if is_biggest_riser %}fire-border\n                             {% elif is_biggest_faller %}ice-border\n                             {% else %}border-yellow-300'
content = re.sub(good_tier_pattern, good_tier_replacement, content)

# 4. Add fire/ice checks to Middle tier
middle_tier_pattern = r'({% for team in rankings if team.rank >= 14 and team.rank <= 20 %})\s*\n\s*<div class="flex items-center p-1 rounded bg-white border border-blue-300'
middle_tier_replacement = r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n                        <div class="flex items-center p-1 rounded bg-white border \n                             {% if is_biggest_riser %}fire-border\n                             {% elif is_biggest_faller %}ice-border\n                             {% else %}border-blue-300'
content = re.sub(middle_tier_pattern, middle_tier_replacement, content)

# 5. Add fire/ice checks to Struggling tier
struggling_tier_pattern = r'({% for team in rankings if team.rank >= 21 and team.rank <= 27 %})\s*\n\s*<div class="flex items-center p-1 rounded bg-white border border-orange-300'
struggling_tier_replacement = r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n                        <div class="flex items-center p-1 rounded bg-white border \n                             {% if is_biggest_riser %}fire-border\n                             {% elif is_biggest_faller %}ice-border\n                             {% else %}border-orange-300'
content = re.sub(struggling_tier_pattern, struggling_tier_replacement, content)

# 6. Add fire/ice checks to Bottom tier
bottom_tier_pattern = r'({% for team in rankings if team.rank >= 28 %})\s*\n\s*<div class="flex items-center p-1 rounded bg-white border border-red-300'
bottom_tier_replacement = r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n                        <div class="flex items-center p-1 rounded bg-white border \n                             {% if is_biggest_riser %}fire-border\n                             {% elif is_biggest_faller %}ice-border\n                             {% else %}border-red-300'
content = re.sub(bottom_tier_pattern, bottom_tier_replacement, content)

# 7. Fix backgrounds for all tiers
content = content.replace('from-yellow-50 to-white', 'from-yellow-50/50 to-white')
content = content.replace('from-blue-50 to-white', 'from-blue-50/50 to-white')  
content = content.replace('from-orange-50 to-white', 'from-orange-50/50 to-white')
content = content.replace('from-red-50 to-white', 'from-red-50/50 to-white')

# 8. Make sure all rank badges are relative positioned and can show emojis
# First find all non-Elite tier rank badges and add relative class
content = re.sub(
    r'<div class="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs mr-1 shadow-md bg-gradient-to-br from-(yellow|blue|orange|red)-500',
    r'<div class="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs mr-1 shadow-md relative bg-gradient-to-br from-\1-500',
    content
)

# 9. Add fire/ice emoji logic after team.rank in non-Elite tiers
# For Good tier (yellow)
content = re.sub(
    r'(bg-gradient-to-br from-yellow-500[^>]*>)\s*{{ team.rank }}\s*(</div>)',
    r'\1\n                                {{ team.rank }}\n                                {% if is_biggest_riser %}\n                                <div class="absolute -top-1 -right-1 text-xs">🔥</div>\n                                {% elif is_biggest_faller %}\n                                <div class="absolute -top-1 -right-1 text-xs">🧊</div>\n                                {% endif %}\n                            \2',
    content
)

# For Middle tier (blue)
content = re.sub(
    r'(bg-gradient-to-br from-blue-500[^>]*>)\s*{{ team.rank }}\s*(</div>)',
    r'\1\n                                {{ team.rank }}\n                                {% if is_biggest_riser %}\n                                <div class="absolute -top-1 -right-1 text-xs">🔥</div>\n                                {% elif is_biggest_faller %}\n                                <div class="absolute -top-1 -right-1 text-xs">🧊</div>\n                                {% endif %}\n                            \2',
    content
)

# For Struggling tier (orange)
content = re.sub(
    r'(bg-gradient-to-br from-orange-500[^>]*>)\s*{{ team.rank }}\s*(</div>)',
    r'\1\n                                {{ team.rank }}\n                                {% if is_biggest_riser %}\n                                <div class="absolute -top-1 -right-1 text-xs">🔥</div>\n                                {% elif is_biggest_faller %}\n                                <div class="absolute -top-1 -right-1 text-xs">🧊</div>\n                                {% endif %}\n                            \2',
    content
)

# For Bottom tier (red)
content = re.sub(
    r'(bg-gradient-to-br from-red-500[^>]*>)\s*{{ team.rank }}\s*(</div>)',
    r'\1\n                                {{ team.rank }}\n                                {% if is_biggest_riser %}\n                                <div class="absolute -top-1 -right-1 text-xs">🔥</div>\n                                {% elif is_biggest_faller %}\n                                <div class="absolute -top-1 -right-1 text-xs">🧊</div>\n                                {% endif %}\n                            \2',
    content
)

# 10. Mark the rowsLayout div for image capture
content = content.replace(
    '<div id="rowsLayout" class="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg shadow-2xl overflow-hidden p-3 text-black" style="max-width: 700px; margin: 0 auto;">',
    '<div id="rowsLayout" class="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg shadow-2xl overflow-hidden p-3 text-black" style="max-width: 700px; margin: 0 auto;" data-capture-area="true">'
)

# Write the updated template
with open('templates/reddit_rankings.html', 'w') as f:
    f.write(content)

print("Template updated successfully!")
print("- Added pun names for all tiers")
print("- Changed to full team names")
print("- Added fire/ice effects to all tiers")
print("- Marked capture area for image generation")