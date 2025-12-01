#!/usr/bin/env python3
"""
Scrape NHL player safety penalties from search page with proper dates
Uses: https://www.nhl.com/search/?query=player%20safety&type=type&value=story
"""

from playwright.sync_api import sync_playwright
import re
from datetime import datetime
import json
import logging
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NHLSearchScraper:
    def __init__(self):
        self.base_url = "https://www.nhl.com"
        self.search_url = f"{self.base_url}/search/?query=player%20safety&type=type&value=story"

    def scrape_search_pages(self, max_pages: int = 10, min_date: Optional[datetime] = None) -> List[Dict]:
        """Scrape multiple pages of search results"""
        all_penalties = []

        with sync_playwright() as p:
            logger.info("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            current_page = 1

            while current_page <= max_pages:
                logger.info(f"\n📄 Scraping page {current_page}...")

                # Load page
                url = f"{self.search_url}&page={current_page}" if current_page > 1 else self.search_url
                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)

                # Get all article links (articles are wrapped in <a> tags)
                results = page.query_selector_all('a:has(article)')
                logger.info(f"Found {len(results)} article links on page {current_page}")

                page_penalties = []
                found_old_penalty = False

                for result in results:
                    try:
                        # Get link first
                        href = result.get_attribute('href')
                        url = href if href and href.startswith('http') else f"{self.base_url}{href}" if href else ""

                        # Get text content from article inside
                        article = result.query_selector('article')
                        result_text = article.inner_text() if article else result.inner_text()

                        # Parse penalty
                        penalty = self.parse_result_card(result_text, url)

                        if penalty:
                            # Check if too old
                            if min_date:
                                penalty_date = datetime.fromisoformat(penalty['date'].replace('Z', '').replace('+00:00', ''))
                                if penalty_date < min_date:
                                    logger.info(f"⏹️  Reached penalties before {min_date.strftime('%Y-%m-%d')}, stopping")
                                    found_old_penalty = True
                                    break

                            page_penalties.append(penalty)
                            date_str = penalty['date'][:10]
                            logger.info(f"  ✓ {penalty['player_name']:<25} {date_str}  ${penalty['amount']:>10,.0f}")

                    except Exception as e:
                        logger.debug(f"Error processing result: {e}")

                all_penalties.extend(page_penalties)

                # Check if we should continue
                if found_old_penalty:
                    logger.info("Stopping pagination - found old enough penalties")
                    break

                # Check for next button
                next_button = page.query_selector('a:has-text("Next"), button:has-text("Next")')
                if not next_button:
                    logger.info("No more pages available")
                    break

                current_page += 1

            browser.close()

        # Remove duplicates
        unique_penalties = []
        seen = set()
        for p in all_penalties:
            key = (p['player_name'], p['date'][:10], p['amount'])
            if key not in seen:
                seen.add(key)
                unique_penalties.append(p)

        logger.info(f"\n✅ Found {len(unique_penalties)} unique penalties")
        return unique_penalties

    def parse_result_card(self, text: str, url: str) -> Optional[Dict]:
        """Parse a search result card"""
        try:
            # Filter to penalty-related
            text_lower = text.lower()
            if not any(keyword in text_lower for keyword in ['fine', 'suspend', 'banned']):
                return None

            # Extract date - format: "Nov 25, 2025" or "November 25, 2025"
            date = None
            date_patterns = [
                r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})',
                r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})',
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    try:
                        month_map = {
                            'jan': 1, 'january': 1,
                            'feb': 2, 'february': 2,
                            'mar': 3, 'march': 3,
                            'apr': 4, 'april': 4,
                            'may': 5,
                            'jun': 6, 'june': 6,
                            'jul': 7, 'july': 7,
                            'aug': 8, 'august': 8,
                            'sep': 9, 'september': 9,
                            'oct': 10, 'october': 10,
                            'nov': 11, 'november': 11,
                            'dec': 12, 'december': 12,
                        }
                        month_str = match.group(1).lower()
                        month = month_map.get(month_str)
                        day = int(match.group(2))
                        year = int(match.group(3))

                        if month:
                            date = datetime(year, month, day)
                            break
                    except:
                        pass

            if not date:
                date = datetime.now()  # Fallback

            # Extract player name from URL
            player_name = self.extract_player_name(url)
            if not player_name:
                return None

            # Determine penalty type
            penalty_type = 'fine'
            games = None
            amount = 0

            # Check for suspension
            if 'suspend' in text_lower or 'banned' in text_lower:
                susp_patterns = [
                    r'(\d+)\s*-?\s*game',
                    r'suspended?\s+(\d+)',
                ]
                for pattern in susp_patterns:
                    match = re.search(pattern, text_lower)
                    if match:
                        games = int(match.group(1))
                        penalty_type = 'suspension'
                        amount = games * 20833.33
                        break

            # Check for fine
            if penalty_type == 'fine':
                # Try to extract amount from text
                amount_match = re.search(r'\$([0-9,]+)', text)
                if amount_match:
                    amount = float(amount_match.group(1).replace(',', ''))
                elif 'maximum' in text_lower:
                    amount = 5000.00
                elif 'team' in text_lower and 'coach' in text_lower:
                    amount = 125000.00  # Team + coach fines
                elif 'team' in text_lower:
                    amount = 100000.00
                else:
                    amount = 2500.00

            # Extract reason
            reason = self.extract_reason(url, text)

            return {
                'player_name': player_name,
                'amount': amount,
                'penalty_type': penalty_type,
                'reason': reason,
                'date': date.isoformat(),
                'games': games,
                'url': url,
                'title': text[:100],
                'summary': text[:200]
            }

        except Exception as e:
            logger.debug(f"Error parsing result: {e}")
            return None

    def extract_player_name(self, url: str) -> Optional[str]:
        """Extract player name from URL"""
        if not url:
            return None

        try:
            match = re.search(r'/news/([a-z0-9-]+)', url.lower())
            if not match:
                return None

            slug = match.group(1)
            parts = slug.split('-')

            skip_words = {'the', 'of', 'for', 'suspended', 'fined', 'game', 'games',
                         'by', 'player', 'safety', 'hearing', 'actions', 'maximum',
                         'dangerous', 'trip', 'slashing', 'cross', 'checking', 'boarding',
                         'in', 'banned', 'butt', 'ending', 'embellishment', 'diving',
                         'red', 'wings', 'maple', 'leafs', 'blue', 'jackets',
                         'golden', 'knights', 'wild', 'devils', 'islanders'}

            name_parts = []
            for part in parts:
                if part in skip_words or len(part) <= 1:
                    continue
                # Skip numbers
                if part.isdigit():
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

    def save_to_json(self, penalties: List[Dict], filename: str = 'nhl_penalties_2025.json'):
        """Save penalties, merging with existing"""
        existing = []
        try:
            with open(filename, 'r') as f:
                existing = json.load(f)
        except FileNotFoundError:
            pass

        # Deduplicate
        all_penalties = existing + penalties
        unique = []
        seen = set()

        for p in all_penalties:
            key = (p.get('player_name'), p.get('date', '')[:10], p.get('amount'))
            if key not in seen and p.get('player_name'):
                seen.add(key)
                unique.append(p)

        # Save
        with open(filename, 'w') as f:
            json.dump(unique, f, indent=2)

        return len(unique) - len(existing), len(unique)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Scrape NHL penalties from search')
    parser.add_argument('--pages', type=int, default=10, help='Max pages to scrape (default: 10)')
    parser.add_argument('--since', default='2024-09-01', help='Min date (YYYY-MM-DD)')
    args = parser.parse_args()

    min_date = datetime.strptime(args.since, '%Y-%m-%d')

    print("=" * 70)
    print(" NHL Search Scraper (with dates!)")
    print("=" * 70)
    print(f"\nSearching since: {min_date.strftime('%B %d, %Y')}")
    print(f"Max pages: {args.pages}")

    scraper = NHLSearchScraper()
    penalties = scraper.scrape_search_pages(max_pages=args.pages, min_date=min_date)

    if penalties:
        print(f"\n📊 Summary:")
        print(f"  Total penalties found: {len(penalties)}")
        print(f"  Total amount: ${sum(p['amount'] for p in penalties):,.0f}")

        new_count, total = scraper.save_to_json(penalties)
        print(f"\n✅ Added {new_count} new penalties to database")
        print(f"📁 Total in database: {total}")

        # Show by month
        from collections import defaultdict
        by_month = defaultdict(list)
        for p in penalties:
            month = p['date'][:7]
            by_month[month].append(p)

        print(f"\n📅 By month:")
        for month in sorted(by_month.keys(), reverse=True):
            month_penalties = by_month[month]
            month_total = sum(p['amount'] for p in month_penalties)
            month_name = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
            print(f"  {month_name}: {len(month_penalties)} penalties - ${month_total:,.0f}")

    else:
        print("\n⚠️  No penalties found")


if __name__ == "__main__":
    main()
