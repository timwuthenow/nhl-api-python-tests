#!/usr/bin/env python3
"""
NHL Player Safety Web Scraper
Scrapes suspension and fine data from https://www.nhl.com/info/player-safety
"""

import requests
from bs4 import BeautifulSoup
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
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    def fetch_page(self) -> Optional[str]:
        """Fetch the player safety page HTML"""
        try:
            logger.info(f"Fetching {self.player_safety_url}")
            response = requests.get(
                self.player_safety_url,
                headers=self.headers,
                timeout=15
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching page: {e}")
            return None

    def parse_penalty_card(self, card_text: str, card_link: str = "") -> Optional[Dict]:
        """
        Parse a penalty from card text

        Examples:
        - "Ben Chiarot (Red Wings) - Butt-ending fine, maximum penalty"
        - "Mikko Rantanen (Stars) - 1-game suspension"
        - "Nick Cousins (Senators) - Diving embellishment fine"
        """
        try:
            text_lower = card_text.lower()

            # Extract player name - usually "FirstName LastName (Team)"
            player_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', card_text)
            if not player_match:
                return None

            player_name = player_match.group(1).strip()

            # Check if it's a suspension or fine
            penalty_type = 'fine'
            games = None
            amount = 0
            reason = 'Unknown'

            # Look for suspension pattern: "X-game suspension" or "suspended X games"
            suspension_patterns = [
                r'(\d+)-game\s+suspension',
                r'suspended\s+(\d+)\s+games?',
            ]

            for pattern in suspension_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    penalty_type = 'suspension'
                    games = int(match.group(1))
                    # Estimate forfeited salary: avg $20,833 per game
                    amount = games * 20833.33
                    break

            # Look for fine patterns
            if penalty_type == 'fine':
                # Check for "maximum" fine
                if 'maximum' in text_lower or 'max' in text_lower:
                    amount = 5000.00  # Maximum allowable fine
                else:
                    # Try to extract specific amount
                    amount_match = re.search(r'\$([0-9,]+)', card_text)
                    if amount_match:
                        amount = float(amount_match.group(1).replace(',', ''))
                    else:
                        # Default fine amounts
                        amount = 2500.00

            # Extract reason
            reason_keywords = [
                'slashing', 'cross-checking', 'boarding', 'charging',
                'interference', 'roughing', 'butt-ending', 'spearing',
                'high-sticking', 'diving', 'embellishment', 'tripping',
                'hooking', 'holding', 'elbowing', 'kneeing',
                'abuse of officials', 'unsportsmanlike'
            ]

            for keyword in reason_keywords:
                if keyword in text_lower:
                    reason = keyword.replace('-', ' ').title()
                    break

            # Try to extract date (if available in the text)
            # Format could be "February 15, 2025" or "Nov 30, 2025"
            date = datetime.now()  # Default to today
            date_patterns = [
                r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})',
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+(\d{1,2}),?\s+(\d{4})',
            ]

            for pattern in date_patterns:
                date_match = re.search(pattern, text_lower)
                if date_match:
                    try:
                        month_str = date_match.group(1)
                        day = int(date_match.group(2))
                        year = int(date_match.group(3))
                        date = datetime.strptime(f"{month_str} {day} {year}", "%B %d %Y")
                        break
                    except:
                        try:
                            date = datetime.strptime(f"{month_str} {day} {year}", "%b %d %Y")
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
                'url': card_link if card_link else f"{self.base_url}/news/player-safety-{player_name.lower().replace(' ', '-')}",
                'title': card_text[:100],
                'summary': card_text
            }

        except Exception as e:
            logger.error(f"Error parsing card: {e}")
            return None

    def scrape_penalties(self) -> List[Dict]:
        """Scrape all penalties from the player safety page"""
        html = self.fetch_page()
        if not html:
            logger.warning("Could not fetch page, returning empty list")
            return []

        soup = BeautifulSoup(html, 'html.parser')
        penalties = []

        # Try multiple selectors for cards/articles
        # The exact selector depends on NHL.com's current structure
        card_selectors = [
            'article',
            'div[class*="card"]',
            'div[class*="story"]',
            'div[class*="item"]',
            'a[class*="card"]',
        ]

        cards_found = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                logger.info(f"Found {len(cards)} elements with selector: {selector}")
                cards_found.extend(cards)

        # Remove duplicates
        cards_found = list({str(card): card for card in cards_found}.values())

        logger.info(f"Processing {len(cards_found)} unique cards")

        for card in cards_found:
            # Get card text
            card_text = card.get_text(strip=True)

            # Get card link
            link_elem = card.find('a') if card.name != 'a' else card
            card_link = ""
            if link_elem and link_elem.get('href'):
                href = link_elem['href']
                card_link = href if href.startswith('http') else f"{self.base_url}{href}"

            # Only process if text contains penalty-related keywords
            text_lower = card_text.lower()
            penalty_keywords = ['fine', 'suspend', 'game', 'penalty', 'banned']

            if any(keyword in text_lower for keyword in penalty_keywords):
                penalty = self.parse_penalty_card(card_text, card_link)
                if penalty:
                    penalties.append(penalty)
                    logger.info(f"Found: {penalty['player_name']} - ${penalty['amount']:,.0f} ({penalty['reason']})")

        # Remove duplicates based on player name and date
        unique_penalties = []
        seen = set()
        for p in penalties:
            key = (p['player_name'], p['date'])
            if key not in seen:
                seen.add(key)
                unique_penalties.append(p)

        logger.info(f"Found {len(unique_penalties)} unique penalties")
        return unique_penalties

    def save_to_json(self, penalties: List[Dict], filename: str = 'nhl_penalties_2025.json'):
        """Save penalties to JSON file, merging with existing data"""
        # Load existing penalties
        existing_penalties = []
        try:
            with open(filename, 'r') as f:
                existing_penalties = json.load(f)
        except FileNotFoundError:
            logger.info(f"Creating new file: {filename}")
        except Exception as e:
            logger.warning(f"Error loading existing penalties: {e}")

        # Merge with new penalties (avoid duplicates)
        existing_keys = {(p.get('player_name'), p.get('date')) for p in existing_penalties}

        new_count = 0
        for penalty in penalties:
            key = (penalty['player_name'], penalty['date'])
            if key not in existing_keys:
                existing_penalties.append(penalty)
                new_count += 1

        # Save back to file
        with open(filename, 'w') as f:
            json.dump(existing_penalties, f, indent=2)

        logger.info(f"Saved {new_count} new penalties. Total: {len(existing_penalties)}")
        return new_count


def main():
    """Main scraper execution"""
    scraper = NHLPlayerSafetyScraper()

    print("=" * 60)
    print("NHL Player Safety Scraper")
    print("=" * 60)

    penalties = scraper.scrape_penalties()

    if penalties:
        print(f"\nFound {len(penalties)} penalties:")
        print("-" * 60)

        for p in penalties:
            games_str = f" ({p['games']} games)" if p['games'] else ""
            print(f"{p['player_name']:<25} ${p['amount']:>10,.0f}  {p['reason']:<20}{games_str}")

        print("-" * 60)

        # Save to JSON
        new_count = scraper.save_to_json(penalties)
        print(f"\n✅ Saved {new_count} new penalties to nhl_penalties_2025.json")
    else:
        print("\n⚠️  No penalties found. The page structure may have changed.")
        print("Try manually adding penalties using: python add_penalty.py")


if __name__ == "__main__":
    main()
