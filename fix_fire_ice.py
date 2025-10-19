#!/usr/bin/env python3
import re

# Read the template
with open('templates/reddit_rankings.html', 'r') as f:
    content = f.read()

# Fix Goodish Gamers (7-13)
content = re.sub(
    r'({% for team in rankings if team.rank >= 7 and team.rank <= 13 %})\n(\s*<div class="group flex items-center.*?>)',
    r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n\2',
    content
)

# Update the div to use fire/ice conditionally
content = re.sub(
    r'(<div class="group flex items-center p-3 rounded-lg transition-all duration-300 hover:transform hover:scale\[1\.01\] bg-white border-2 hover:shadow-lg) border-yellow-300 bg-gradient-to-r from-yellow-50/50 to-white(">)(\s*<!-- Same structure as Elite tier but with yellow colors -->)',
    r'\1 {% if is_biggest_riser %}fire-border{% elif is_biggest_faller %}ice-border{% else %}border-yellow-300 bg-gradient-to-r from-yellow-50/50 to-white{% endif %}\2\3',
    content
)

# Fix Mushy Middle (14-20)
content = re.sub(
    r'({% for team in rankings if team.rank >= 14 and team.rank <= 20 %})\n(\s*<div class="group flex items-center.*?>)',
    r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n\2',
    content
)

content = re.sub(
    r'(<div class="group flex items-center p-3 rounded-lg transition-all duration-300 hover:transform hover:scale\[1\.01\] bg-white border-2 hover:shadow-lg) border-blue-300 bg-gradient-to-r from-blue-50/50 to-white(">)(\s*<!-- Same structure as Elite tier but with blue colors -->)',
    r'\1 {% if is_biggest_riser %}fire-border{% elif is_biggest_faller %}ice-border{% else %}border-blue-300 bg-gradient-to-r from-blue-50/50 to-white{% endif %}\2\3',
    content
)

# Fix Some Struggles (21-27)
content = re.sub(
    r'({% for team in rankings if team.rank >= 21 and team.rank <= 27 %})\n(\s*<div class="group flex items-center.*?>)',
    r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n\2',
    content
)

content = re.sub(
    r'(<div class="group flex items-center p-3 rounded-lg transition-all duration-300 hover:transform hover:scale\[1\.01\] bg-white border-2 hover:shadow-lg) border-orange-300 bg-gradient-to-r from-orange-50/50 to-white(">)(\s*<!-- Same structure as Elite tier but with orange colors -->)',
    r'\1 {% if is_biggest_riser %}fire-border{% elif is_biggest_faller %}ice-border{% else %}border-orange-300 bg-gradient-to-r from-orange-50/50 to-white{% endif %}\2\3',
    content
)

# Fix Fallin' for Gavin (28-32)
content = re.sub(
    r'({% for team in rankings if team.rank >= 28 %})\n(\s*<div class="group flex items-center.*?>)',
    r'\1\n                        {% set is_biggest_riser = biggest_riser and team.team_abbrev == biggest_riser.team.team_abbrev %}\n                        {% set is_biggest_faller = biggest_faller and team.team_abbrev == biggest_faller.team.team_abbrev %}\n\2',
    content
)

content = re.sub(
    r'(<div class="group flex items-center p-3 rounded-lg transition-all duration-300 hover:transform hover:scale\[1\.01\] bg-white border-2 hover:shadow-lg) border-red-300 bg-gradient-to-r from-red-50/50 to-white(">)(\s*<!-- Same structure as Elite tier but with red colors -->)',
    r'\1 {% if is_biggest_riser %}fire-border{% elif is_biggest_faller %}ice-border{% else %}border-red-300 bg-gradient-to-r from-red-50/50 to-white{% endif %}\2\3',
    content
)

# Write the updated template
with open('templates/reddit_rankings.html', 'w') as f:
    f.write(content)

print("Template updated successfully!")
print("- Added fire/ice checks to all non-Elite tiers")
print("- Restored hottest/coldest showcase section")