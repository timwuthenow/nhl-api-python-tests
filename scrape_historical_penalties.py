#!/usr/bin/env python3
"""
Scrape historical NHL player safety penalties
Uses search and archives to find older penalties back to September 2025
"""

from playwright.sync_api import sync_playwright
import re
from datetime import datetime
import json
import logging
from typing import List, Dict, Optional
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HistoricalPenaltyScraper:
    def __init__(self):
        self.base_url = "https://www.nhl.com"
        # Try different search/archive approaches
        self.search_urls = [
            f"{self.base_url}/news/topic/player-safety",  # Topic page
            f"{self.base_url}/search?q=player+safety+fined",
            f"{self.base_url}/search?q=player+safety+suspended",
        ]

    def scrape_all_penalties(self, start_date: datetime) -> List[Dict]:
        """Scrape penalties from multiple sources"""
        all_penalties = []

        with sync_playwright() as p:
            logger.info("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Try topic page first (best source)
            logger.info("Checking topic page for articles...")
            penalties = self.scrape_topic_page(page, start_date)
            all_penalties.extend(penalties)

            # Scroll to load more articles
            logger.info("Scrolling to load more articles...")
            for i in range(10):  # Scroll 10 times
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

            # Get updated links
            penalties = self.scrape_topic_page(page, start_date)
            all_penalties.extend(penalties)

            browser.close()

        # Remove duplicates
        unique_penalties = []
        seen = set()
        for p in all_penalties:
            key = (p.get('player_name'), p.get('date'), p.get('amount'))
            if key not in seen and p.get('player_name'):
                seen.add(key)
                unique_penalties.append(p)

        logger.info(f"\nFound {len(unique_penalties)} total unique penalties")
        return unique_penalties

    def scrape_topic_page(self, page, start_date: datetime) -> List[Dict]:
        """Scrape the player safety topic page"""
        penalties = []

        try:
            url = f"{self.base_url}/news/topic/player-safety"
            logger.info(f"Loading {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)

            # Get all article links
            links = page.query_selector_all('a[href*="/news/"]')
            logger.info(f"Found {len(links)} article links")

            for link in links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        continue

                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    link_text = link.inner_text().strip()

                    # Filter to penalty-related links
                    text_lower = link_text.lower()
                    if not any(keyword in text_lower for keyword in ['fine', 'suspend', 'banned']):
                        continue

                    # Parse penalty
                    penalty = self.parse_penalty_from_link(link_text, full_url)
                    if penalty:
                        # Filter by date if we have one
                        penalty_date = datetime.fromisoformat(penalty['date'].replace('Z', '+00:00').replace('+00:00', ''))
                        if penalty_date >= start_date:
                            penalties.append(penalty)
                            logger.debug(f"Added: {penalty['player_name']} - {penalty_date.strftime('%Y-%m-%d')}")

                except Exception as e:
                    logger.debug(f"Error processing link: {e}")

        except Exception as e:
            logger.error(f"Error scraping topic page: {e}")

        return penalties

    def parse_penalty_from_link(self, text: str, url: str) -> Optional[Dict]:
        """Parse penalty from link text and URL"""
        try:
            # Extract player name from URL
            player_name = self.extract_player_name(url)
            if not player_name:
                return None

            text_lower = text.lower()

            # Determine type
            penalty_type = 'fine'
            games = None
            amount = 0

            # Check for suspension
            if 'suspend' in text_lower or 'banned' in text_lower:
                susp_match = re.search(r'(\d+)\s*-?\s*game', text_lower)
                if susp_match:
                    games = int(susp_match.group(1))
                    penalty_type = 'suspension'
                    amount = games * 20833.33

            # Check for fine
            if penalty_type == 'fine':
                amount_match = re.search(r'\$([0-9,]+)', text)
                if amount_match:
                    amount = float(amount_match.group(1).replace(',', ''))
                elif 'maximum' in text_lower:
                    amount = 5000.00
                else:
                    amount = 2500.00

            # Extract reason
            reason = self.extract_reason(url, text)

            # Try to extract date from URL or text
            date = self.extract_date_from_url(url) or datetime.now()

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
            logger.debug(f"Error parsing penalty: {e}")
            return None

    def extract_player_name(self, url: str) -> Optional[str]:
        """Extract player name from URL"""
        if not url:
            return None

        try:
            match = re.search(r'/news/([a-z-]+)', url.lower())
            if not match:
                return None

            slug = match.group(1)
            parts = slug.split('-')

            # Skip common words
            skip_words = {'the', 'of', 'for', 'suspended', 'fined', 'game', 'games',
                         'by', 'player', 'safety', 'hearing', 'actions', 'maximum',
                         'dangerous', 'trip', 'slashing', 'cross', 'checking', 'boarding',
                         'red', 'wings', 'maple', 'leafs', 'blue', 'jackets', 'in',
                         'golden', 'knights', 'wild', 'devils', 'islanders', 'banned'}

            name_parts = []
            for part in parts:
                if part in skip_words or len(part) <= 2:
                    continue
                name_parts.append(part.capitalize())
                if len(name_parts) >= 3:
                    break

            if len(name_parts) >= 2:
                return ' '.join(name_parts)

            return None

        except:
            return None

    def extract_reason(self, url: str, text: str) -> str:
        """Extract penalty reason"""
        reasons = {
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

        combined = f"{url.lower()} {text.lower()}"
        for keyword, full_reason in reasons.items():
            if keyword in combined:
                return full_reason

        return 'Unknown'

    def extract_date_from_url(self, url: str) -> Optional[datetime]:
        """Try to extract date from URL patterns"""
        # Some NHL.com URLs have dates like /news/2025/10/15/...
        date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
        if date_match:
            try:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                return datetime(year, month, day)
            except:
                pass

        return None

    def save_to_json(self, penalties: List[Dict], filename: str = 'nhl_penalties_2025.json'):
        """Save penalties to JSON, merging with existing"""
        existing = []
        try:
            with open(filename, 'r') as f:
                existing = json.load(f)
        except FileNotFoundError:
            pass

        # Deduplicate existing
        existing_unique = []
        seen = set()
        for p in existing:
            key = (p.get('player_name'), p.get('date'), p.get('amount'))
            if key not in seen:
                seen.add(key)
                existing_unique.append(p)

        # Add new
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

        return new_count, len(existing_unique)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Scrape historical NHL penalties')
    parser.add_argument('--start-date', default='2024-09-01',
                       help='Start date (YYYY-MM-DD), default: 2024-09-01')
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')

    print("=" * 70)
    print(" NHL Historical Penalty Scraper")
    print("=" * 70)
    print(f"\nSearching for penalties since: {start_date.strftime('%B %d, %Y')}")

    scraper = HistoricalPenaltyScraper()
    penalties = scraper.scrape_all_penalties(start_date)

    if penalties:
        print(f"\n📋 Found {len(penalties)} penalties:")
        print(f"\n{'Player':<25} {'Date':<12} {'Amount':>12} {'Reason'}")
        print("-" * 70)

        for p in sorted(penalties, key=lambda x: x['date'], reverse=True):
            date_str = p['date'][:10]
            print(f"{p['player_name']:<25} {date_str:<12} ${p['amount']:>10,.0f} {p['reason']}")

        new_count, total = scraper.save_to_json(penalties)
        print(f"\n✅ Added {new_count} new penalties")
        print(f"📁 Total in database: {total}")
        print(f"💰 Total amount: ${sum(p['amount'] for p in penalties):,.0f}")
    else:
        print("\n⚠️  No penalties found")


if __name__ == "__main__":
    main()
