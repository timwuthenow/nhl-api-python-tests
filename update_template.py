#!/usr/bin/env python3
import re

# Read the template
with open('templates/reddit_rankings.html', 'r') as f:
    content = f.read()

# 1. Hide the layout toggle buttons and disable grid layout
content = content.replace(
    '        <!-- Layout Toggle Buttons -->\n        <div class="bg-white rounded-lg shadow-lg p-4 mb-6 no-print">',
    '        <!-- Layout Toggle Buttons (Hidden) -->\n        <div class="hidden">'
)

# 2. Hide grid layout
content = content.replace(
    '        <div id="gridLayout" class="bg-white rounded-lg shadow-2xl overflow-hidden p-8 text-black" style="max-width: 1400px; margin: 0 auto;">',
    '        <div id="gridLayout" class="hidden">'
)

# 3. Show single column by default and make it more compact
content = content.replace(
    '        <div id="rowsLayout" class="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg shadow-2xl overflow-hidden p-6 text-black hidden" style="max-width: 900px; margin: 0 auto;">',
    '        <div id="rowsLayout" class="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg shadow-2xl overflow-hidden p-3 text-black" style="max-width: 700px; margin: 0 auto;">'
)

# 4. Make tier headers smaller
content = re.sub(r'<h3 class="text-lg font-bold ([^"]*) mb-2 uppercase tracking-wider">',
                 r'<h3 class="text-sm font-bold \1 mb-1 uppercase tracking-wide">', content)

# 5. Reduce spacing between tiers
content = content.replace('            <div class="space-y-6">', '            <div class="space-y-3">')
content = content.replace('                    <div class="space-y-1">', '                    <div class="space-y-0.5">')

# 6. Remove hover effects and make rows smaller for ALL tiers
# Elite tier
content = re.sub(
    r'<div class="group flex items-center p-2 rounded-lg transition-all duration-300 hover:transform hover:scale\[1\.01\] bg-white border-2 hover:shadow-lg',
    r'<div class="flex items-center p-1 rounded bg-white border', 
    content
)

# Other tiers
content = re.sub(
    r'<div class="group flex items-center p-3 rounded-lg transition-all duration-300 hover:transform hover:scale\[1\.01\] bg-white border-2 hover:shadow-lg',
    r'<div class="flex items-center p-1 rounded bg-white border', 
    content
)

# 7. Make all badges smaller (w-8 h-8 -> w-6 h-6)
content = re.sub(r'w-8 h-8 rounded-full', r'w-6 h-6 rounded-full', content)
content = re.sub(r'w-10 h-10 rounded-full', r'w-6 h-6 rounded-full', content)

# 8. Make all logos smaller
content = re.sub(r'<div class="flex-shrink-0 w-8 h-8 mr-2">', r'<div class="flex-shrink-0 w-6 h-6 mr-1">', content)
content = re.sub(r'<div class="flex-shrink-0 w-10 h-10 mr-3">', r'<div class="flex-shrink-0 w-6 h-6 mr-1">', content)

# 9. Make text smaller
content = re.sub(r'font-bold text-xs mr-2', r'font-bold text-xs mr-1', content)
content = re.sub(r'font-bold text-sm mr-3', r'font-bold text-xs mr-1', content)
content = re.sub(r'<span class="font-bold text-base"', r'<span class="font-bold text-xs"', content)
content = re.sub(r'<span class="font-bold text-sm"', r'<span class="font-bold text-xs"', content)

# 10. Make stats smaller
content = re.sub(r'space-x-4 text-xs', r'space-x-1 text-xs', content)
content = re.sub(r'space-x-2 text-xs', r'space-x-1 text-xs', content)
content = re.sub(r'rounded px-2 py-1', r'rounded px-1 py-0.5', content)
content = re.sub(r'rounded px-1\.5 py-0\.5', r'rounded px-1 py-0.5', content)

# 11. Make change indicators smaller
content = re.sub(r'text-lg ml-3 flex', r'text-xs ml-1 flex', content)
content = re.sub(r'text-sm ml-2 flex', r'text-xs ml-1 flex', content)

# 12. Make padding smaller in team name boxes
content = re.sub(r'px-3 py-1 rounded', r'px-1 py-0.5 rounded', content)
content = re.sub(r'px-2 py-0\.5 rounded', r'px-1 py-0.5 rounded', content)

# 13. Force single column layout on load
content = content.replace(
    "// Load saved layout preference on page load\ndocument.addEventListener('DOMContentLoaded', function() {\n    const savedLayout = localStorage.getItem('preferredLayout');\n    if (savedLayout === 'rows') {\n        switchLayout('rows');\n    } else {\n        switchLayout('grid'); // Default to grid\n    }",
    "// Force single column layout\ndocument.addEventListener('DOMContentLoaded', function() {\n    const gridLayout = document.getElementById('gridLayout');\n    const rowsLayout = document.getElementById('rowsLayout');\n    if (gridLayout) gridLayout.classList.add('hidden');\n    if (rowsLayout) rowsLayout.classList.remove('hidden');"
)

# Write the updated template
with open('templates/reddit_rankings.html', 'w') as f:
    f.write(content)

print("Template updated successfully!")
print("- Removed hover effects")
print("- Made all elements smaller and more compact")
print("- Disabled grid layout")
print("- Fire/ice effects preserved in single column")