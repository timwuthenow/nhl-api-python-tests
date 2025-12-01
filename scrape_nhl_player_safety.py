#!/usr/bin/env python3
"""
NHL Player Safety Scraper - Final Version
Extracts player names from URLs for accuracy
"""

from playwright.sync_api import sync_playwright
import re
from datetime import datetime
import json
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NHLPlayerSafetyScraper:
    def __init__(self):
        self.base_url = "https://www.nhl.com"
        self.player_safety_url = f"{self.base_url}/info/player-safety"

    def extract_player_name_from_url(self, url: str) -> Optional[str]:
        """
        Extract player name from NHL.com URL
        Example: https://www.nhl.com/news/tyler-myers-fined-for-slashing-connor-mcdavid
        Returns: Tyler Myers
        """
        if not url:
            return None

        try:
            # Common URL patterns:
            # /news/firstname-lastname-...
            # /news/team-firstname-lastname-...

            # Extract the slug after /news/
            match = re.search(r'/news/([a-z-]+)', url.lower())
            if not match:
                return None

            slug = match.group(1)

            # Remove common words that aren't names
            remove_words = ['the', 'of', 'for', 'suspended', 'fined', 'game', 'games',
                          'by', 'player', 'safety', 'hearing', 'actions', 'maximum',
                          'dangerous', 'trip', 'slashing', 'cross', 'checking', 'boarding']

            # Split slug and capitalize each part
            parts = slug.split('-')

            # Try to find a name pattern (usually first 2-3 words before common words)
            name_parts = []
            for part in parts:
                if part in remove_words:
                    break
                # Skip team abbreviations (3 letters)
                if len(part) <= 2:
                    continue
                # Skip common team words
                if part in ['red', 'wings', 'maple', 'leafs', 'blue', 'jackets',
                           'golden', 'knights', 'wild', 'devils', 'islanders']:
                    continue
                name_parts.append(part.capitalize())
                # Usually names are 2-3 words max
                if len(name_parts) >= 3:
                    break

            if len(name_parts) >= 2:
                return ' '.join(name_parts)

            return None

        except Exception as e:
            logger.debug(f"Error extracting name from URL {url}: {e}")
            return None

    def scrape_penalties(self) -> List[Dict]:
        """Scrape all penalties using Playwright"""
        penalties = []

        with sync_playwright() as p:
            logger.info("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            logger.info(f"Loading {self.player_safety_url}")
            page.goto(self.player_safety_url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)

            # Get all links
            links = page.query_selector_all('a[href*="/news/"]')
            logger.info(f"Found {len(links)} news links")

            seen_urls = set()

            for link in links:
                try:
                    href = link.get_attribute('href')
                    if not href or href in seen_urls:
                        continue

                    seen_urls.add(href)

                    # Get full URL
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"

                    # Get link text
                    link_text = link.inner_text().strip()

                    # Only process if it's penalty-related
                    text_lower = link_text.lower()
                    if not any(keyword in text_lower for keyword in ['fine', 'suspend', 'banned', 'hearing']):
                        continue

                    # Parse the penalty
                    penalty = self.parse_penalty(link_text, full_url)
                    if penalty and penalty['player_name']:
                        penalties.append(penalty)
                        logger.info(f"✓ {penalty['player_name']} - ${penalty['amount']:,.0f} ({penalty['reason']})")

                except Exception as e:
                    logger.debug(f"Error processing link: {e}")

            browser.close()

        # Remove duplicates
        unique_penalties = []
        seen = set()
        for p in penalties:
            key = (p['player_name'], p.get('date', ''), p['amount'])
            if key not in seen:
                seen.add(key)
                unique_penalties.append(p)

        logger.info(f"\nFound {len(unique_penalties)} unique penalties")
        return unique_penalties

    def parse_penalty(self, text: str, url: str) -> Optional[Dict]:
        """Parse penalty details from text and URL"""
        try:
            text_lower = text.lower()

            # Extract player name from URL (most reliable)
            player_name = self.extract_player_name_from_url(url)
            if not player_name:
                return None

            # Determine penalty type
            penalty_type = 'fine'
            games = None
            amount = 0
            reason = 'Unknown'

            # Check for suspension
            if 'suspend' in text_lower or 'banned' in text_lower:
                suspension_patterns = [
                    r'(\d+)\s*-?\s*game',
                    r'suspended\s+(\d+)',
                ]

                for pattern in suspension_patterns:
                    match = re.search(pattern, text_lower)
                    if match:
                        games = int(match.group(1))
                        penalty_type = 'suspension'
                        amount = games * 20833.33
                        break

            # Check for fine
            if penalty_type == 'fine':
                # Try to extract amount
                amount_match = re.search(r'\$([0-9,]+)', text)
                if amount_match:
                    amount = float(amount_match.group(1).replace(',', ''))
                elif 'maximum' in text_lower:
                    amount = 5000.00
                else:
                    amount = 2500.00  # Default

            # Extract reason from URL and text
            reason_keywords = {
                'slash': 'Slashing',
                'cross-check': 'Cross-Checking',
                'board': 'Boarding',
                'charg': 'Charging',
                'interfer': 'Interference',
                'rough': 'Roughing',
                'butt-end': 'Butt-Ending',
                'spear': 'Spearing',
                'high-stick': 'High-Sticking',
                'div': 'Diving',
                'embellish': 'Embellishment',
                'trip': 'Tripping',
                'hook': 'Hooking',
                'hold': 'Holding',
                'elbow': 'Elbowing',
                'knee': 'Kneeing',
            }

            combined_text = f"{url.lower()} {text_lower}"
            for keyword, full_reason in reason_keywords.items():
                if keyword in combined_text:
                    reason = full_reason
                    break

            # Try to extract date
            date = datetime.now()
            date_patterns = [
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})',
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    try:
                        month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                                   'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                                   'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
                        month = month_map.get(match.group(1)[:3], 11)
                        day = int(match.group(2))
                        year = int(match.group(3))
                        date = datetime(year, month, day)
                        break
                    except:
                        pass

            return {
                'player_name': player_name,
                'amount': amount,
                'penalty_type': penalty_type,
                'reason': reason,
                'date': date.isoformat(),
                'games': games,
                'url': url,
                'title': text[:100],
                'summary': text
            }

        except Exception as e:
            logger.error(f"Error parsing penalty: {e}")
            return None

    def save_to_json(self, penalties: List[Dict], filename: str = 'nhl_penalties_2025.json'):
        """Save penalties to JSON, merging with existing"""
        existing = []
        try:
            with open(filename, 'r') as f:
                existing = json.load(f)
        except FileNotFoundError:
            logger.info(f"Creating new file: {filename}")

        # Remove duplicates from existing first
        existing_unique = []
        seen = set()
        for p in existing:
            key = (p.get('player_name'), p.get('date'), p.get('amount'))
            if key not in seen:
                seen.add(key)
                existing_unique.append(p)

        # Add new penalties
        new_count = 0
        for penalty in penalties:
            key = (penalty['player_name'], penalty['date'], penalty['amount'])
            if key not in seen:
                existing_unique.append(penalty)
                seen.add(key)
                new_count += 1

        # Save
        with open(filename, 'w') as f:
            json.dump(existing_unique, f, indent=2)

        logger.info(f"Saved {new_count} new penalties. Total: {len(existing_unique)}")
        return new_count, len(existing_unique)


def main():
    print("=" * 70)
    print(" NHL Player Safety Scraper")
    print("=" * 70)

    scraper = NHLPlayerSafetyScraper()
    penalties = scraper.scrape_penalties()

    if penalties:
        print(f"\n📋 Found {len(penalties)} penalties:\n")
        print(f"{'Player':<25} {'Amount':>12}  {'Reason':<20} {'Type'}")
        print("-" * 70)

        for p in sorted(penalties, key=lambda x: x['date'], reverse=True):
            games_str = f"({p['games']} games)" if p['games'] else ""
            type_str = f"{p['penalty_type']:<10} {games_str}"
            print(f"{p['player_name']:<25} ${p['amount']:>10,.0f}  {p['reason']:<20} {type_str}")

        print("-" * 70)

        new_count, total = scraper.save_to_json(penalties)
        print(f"\n✅ Saved {new_count} new penalties")
        print(f"📁 Total in database: {total}")
        print(f"💰 Total fines/forfeitures: ${sum(p['amount'] for p in penalties):,.0f}")
    else:
        print("\n⚠️  No penalties found")


if __name__ == "__main__":
    main()
