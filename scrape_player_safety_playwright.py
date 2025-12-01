#!/usr/bin/env python3
"""
NHL Player Safety Web Scraper using Playwright
Handles JavaScript-rendered content from https://www.nhl.com/info/player-safety
"""

from playwright.sync_api import sync_playwright
import re
from datetime import datetime
import json
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NHLPlayerSafetyScraperPlaywright:
    def __init__(self):
        self.base_url = "https://www.nhl.com"
        self.player_safety_url = f"{self.base_url}/info/player-safety"

    def scrape_penalties(self) -> List[Dict]:
        """Scrape all penalties using Playwright"""
        penalties = []

        with sync_playwright() as p:
            logger.info("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            logger.info(f"Loading {self.player_safety_url}")
            page.goto(self.player_safety_url, wait_until='networkidle', timeout=30000)

            # Wait for content to load
            page.wait_for_timeout(3000)

            # Get all story/video cards
            # Try different selectors
            card_selectors = [
                'article',
                'div.story-card',
                'div.video-card',
                'a[href*="player-safety"]',
                'div[class*="grid"] a',
            ]

            all_cards = []
            for selector in card_selectors:
                try:
                    cards = page.query_selector_all(selector)
                    if cards:
                        logger.info(f"Found {len(cards)} cards with selector: {selector}")
                        all_cards.extend(cards)
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")

            logger.info(f"Processing {len(all_cards)} total card elements")

            seen_texts = set()

            for card in all_cards:
                try:
                    # Get card text
                    card_text = card.inner_text()

                    # Skip if we've already processed this exact text
                    if card_text in seen_texts:
                        continue
                    seen_texts.add(card_text)

                    # Get link
                    card_link = ""
                    try:
                        if card.tag_name == 'a':
                            card_link = card.get_attribute('href')
                        else:
                            link_elem = card.query_selector('a')
                            if link_elem:
                                card_link = link_elem.get_attribute('href')

                        if card_link and not card_link.startswith('http'):
                            card_link = f"{self.base_url}{card_link}"
                    except:
                        pass

                    # Parse penalty
                    penalty = self.parse_penalty_card(card_text, card_link)
                    if penalty:
                        penalties.append(penalty)
                        logger.info(f"Found: {penalty['player_name']} - ${penalty['amount']:,.0f} ({penalty['reason']})")

                except Exception as e:
                    logger.debug(f"Error processing card: {e}")

            browser.close()

        # Remove duplicates
        unique_penalties = []
        seen = set()
        for p in penalties:
            key = (p['player_name'], p['date'], p['amount'])
            if key not in seen:
                seen.add(key)
                unique_penalties.append(p)

        logger.info(f"Found {len(unique_penalties)} unique penalties")
        return unique_penalties

    def parse_penalty_card(self, card_text: str, card_link: str = "") -> Dict:
        """
        Parse a penalty from card text

        Examples from real NHL.com:
        - "Ben Chiarot suspended 1 game for butt-ending"
        - "Tyler Myers fined for slashing"
        - "Mikko Rantanen suspended for cross-checking"
        """
        try:
            text_lower = card_text.lower()

            # Skip if doesn't contain penalty keywords
            penalty_keywords = ['fine', 'suspend', 'banned', 'discipline']
            if not any(keyword in text_lower for keyword in penalty_keywords):
                return None

            # Extract player name - look for patterns like "FirstName LastName"
            # More robust patterns
            name_patterns = [
                r"([A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z'-]+)+)",  # Full name
                r"([A-Z][a-z]+\s+[A-Z][a-z]+)",  # First Last
            ]

            player_name = None
            for pattern in name_patterns:
                matches = re.findall(pattern, card_text)
                if matches:
                    # Take first match that isn't a common false positive
                    for match in matches:
                        # Filter out team names and common words
                        if match not in ['Player Safety', 'Latest Stories', 'Video Room', 'Red Wings']:
                            player_name = match
                            break
                    if player_name:
                        break

            if not player_name:
                # Try to extract from title format: "Name suspended/fined"
                title_match = re.search(r"^([A-Z][a-z]+\s+[A-Z][a-z]+)", card_text)
                if title_match:
                    player_name = title_match.group(1)

            if not player_name:
                return None  # Can't determine player

            # Determine penalty type
            penalty_type = 'fine'
            games = None
            amount = 0
            reason = 'Unknown'

            # Look for suspension
            suspension_patterns = [
                r"suspended\s+(\d+)\s+games?",
                r"(\d+)-game\s+suspension",
                r"banned\s+(\d+)\s+games?",
            ]

            for pattern in suspension_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    penalty_type = 'suspension'
                    games = int(match.group(1))
                    amount = games * 20833.33  # Avg daily salary forfeiture
                    break

            # Look for fines
            if penalty_type == 'fine':
                # Try to find specific amount
                amount_match = re.search(r"\$([0-9,]+)", card_text)
                if amount_match:
                    amount = float(amount_match.group(1).replace(',', ''))
                elif 'maximum' in text_lower or 'max' in text_lower:
                    amount = 5000.00
                else:
                    amount = 2500.00  # Default fine

            # Extract reason
            reason_keywords = [
                'slashing', 'cross-checking', 'boarding', 'charging',
                'interference', 'roughing', 'butt-ending', 'spearing',
                'high-sticking', 'diving', 'embellishment', 'tripping',
                'hooking', 'holding', 'elbowing', 'kneeing',
                'abuse of officials', 'unsportsmanlike', 'illegal check',
                'checking from behind'
            ]

            for keyword in reason_keywords:
                if keyword in text_lower:
                    reason = keyword.replace('-', ' ').title()
                    break

            # Try to extract date
            date = datetime.now()
            months = ['january', 'february', 'march', 'april', 'may', 'june',
                     'july', 'august', 'september', 'october', 'november', 'december']
            for month in months:
                pattern = f"{month}\\s+(\\d{{1,2}}),?\\s+(\\d{{4}})"
                match = re.search(pattern, text_lower)
                if match:
                    try:
                        day = int(match.group(1))
                        year = int(match.group(2))
                        date = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
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
                'url': card_link if card_link else "",
                'title': card_text[:100],
                'summary': card_text[:200]
            }

        except Exception as e:
            logger.error(f"Error parsing card: {e}")
            return None

    def save_to_json(self, penalties: List[Dict], filename: str = 'nhl_penalties_2025.json'):
        """Save penalties to JSON file"""
        # Load existing
        existing = []
        try:
            with open(filename, 'r') as f:
                existing = json.load(f)
        except FileNotFoundError:
            pass

        # Merge
        existing_keys = {(p.get('player_name'), p.get('date'), p.get('amount')) for p in existing}
        new_count = 0

        for penalty in penalties:
            key = (penalty['player_name'], penalty['date'], penalty['amount'])
            if key not in existing_keys:
                existing.append(penalty)
                new_count += 1

        # Save
        with open(filename, 'w') as f:
            json.dump(existing, f, indent=2)

        logger.info(f"Saved {new_count} new penalties. Total: {len(existing)}")
        return new_count


def main():
    scraper = NHLPlayerSafetyScraperPlaywright()

    print("=" * 60)
    print("NHL Player Safety Scraper (Playwright)")
    print("=" * 60)

    penalties = scraper.scrape_penalties()

    if penalties:
        print(f"\nFound {len(penalties)} penalties:")
        print("-" * 60)

        for p in penalties:
            games_str = f" ({p['games']} games)" if p['games'] else ""
            print(f"{p['player_name']:<25} ${p['amount']:>10,.0f}  {p['reason']:<20}{games_str}")

        print("-" * 60)

        new_count = scraper.save_to_json(penalties)
        print(f"\n✅ Saved {new_count} new penalties to nhl_penalties_2025.json")
    else:
        print("\n⚠️  No penalties found.")


if __name__ == "__main__":
    main()
