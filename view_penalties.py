#!/usr/bin/env python3
"""
View and manage NHL penalties with year-to-date summaries
"""

import json
from datetime import datetime
from collections import defaultdict
import argparse


def load_penalties(filename='nhl_penalties_2025.json'):
    """Load penalties from JSON file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File {filename} not found. Run scraper first.")
        return []


def update_penalty_date(filename='nhl_penalties_2025.json'):
    """Interactively update penalty dates"""
    penalties = load_penalties(filename)
    if not penalties:
        return

    print("\n" + "="*70)
    print(" Update Penalty Dates")
    print("="*70)

    for i, p in enumerate(penalties):
        current_date = p['date'][:10]
        print(f"\n[{i+1}/{len(penalties)}] {p['player_name']}")
        print(f"  Current date: {current_date}")
        print(f"  Reason: {p['reason']} - ${p['amount']:,.0f}")

        new_date = input("  New date (YYYY-MM-DD) or press Enter to skip: ").strip()
        if new_date:
            try:
                # Validate date
                datetime.strptime(new_date, "%Y-%m-%d")
                p['date'] = f"{new_date}T00:00:00"
                print(f"  ✓ Updated to {new_date}")
            except ValueError:
                print(f"  ✗ Invalid date format, skipping")

    # Save updated penalties
    with open(filename, 'w') as f:
        json.dump(penalties, f, indent=2)

    print(f"\n✅ Saved updates to {filename}")


def show_summary(penalties, year=None):
    """Show year-to-date summary"""
    if not penalties:
        print("No penalties found")
        return

    # Filter by year if specified
    if year:
        penalties = [p for p in penalties if p['date'].startswith(str(year))]

    if not penalties:
        print(f"No penalties found for year {year}")
        return

    # Calculate totals
    total_fines = sum(p['amount'] for p in penalties if p['penalty_type'] == 'fine')
    total_forfeit = sum(p['amount'] for p in penalties if p['penalty_type'] == 'suspension')
    total_amount = total_fines + total_forfeit
    total_count = len(penalties)

    # By month
    by_month = defaultdict(lambda: {'count': 0, 'amount': 0})
    for p in penalties:
        month = p['date'][:7]  # YYYY-MM
        by_month[month]['count'] += 1
        by_month[month]['amount'] += p['amount']

    # By player
    by_player = defaultdict(lambda: {'count': 0, 'amount': 0, 'penalties': []})
    for p in penalties:
        player = p['player_name']
        by_player[player]['count'] += 1
        by_player[player]['amount'] += p['amount']
        by_player[player]['penalties'].append(p)

    # Print summary
    year_str = f" ({year})" if year else ""
    print("\n" + "="*70)
    print(f" NHL Player Safety Summary{year_str}")
    print("="*70)

    print(f"\n📊 Overall Totals:")
    print(f"  Total Incidents: {total_count}")
    print(f"  Total Fines: ${total_fines:,.0f}")
    print(f"  Total Salary Forfeited: ${total_forfeit:,.0f}")
    print(f"  GRAND TOTAL: ${total_amount:,.0f}")

    print(f"\n📅 By Month:")
    print(f"{'Month':<15} {'Count':>8} {'Amount':>15}")
    print("-"*40)
    for month in sorted(by_month.keys(), reverse=True):
        data = by_month[month]
        month_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        print(f"{month_name:<15} {data['count']:>8} ${data['amount']:>13,.0f}")

    print(f"\n👤 Top Offenders:")
    print(f"{'Player':<30} {'Count':>8} {'Total':>15}")
    print("-"*55)
    sorted_players = sorted(by_player.items(), key=lambda x: x[1]['amount'], reverse=True)
    for player, data in sorted_players[:10]:
        print(f"{player:<30} {data['count']:>8} ${data['amount']:>13,.0f}")

    print("\n" + "="*70)


def show_detailed_list(penalties, year=None):
    """Show detailed list of all penalties"""
    if not penalties:
        print("No penalties found")
        return

    # Filter by year
    if year:
        penalties = [p for p in penalties if p['date'].startswith(str(year))]

    if not penalties:
        print(f"No penalties found for year {year}")
        return

    # Sort by date (newest first)
    penalties = sorted(penalties, key=lambda x: x['date'], reverse=True)

    year_str = f" ({year})" if year else ""
    print("\n" + "="*90)
    print(f" All Penalties{year_str}")
    print("="*90)

    print(f"{'Date':<12} {'Player':<25} {'Amount':>12} {'Type':<12} {'Reason':<20}")
    print("-"*90)

    for p in penalties:
        date_str = p['date'][:10]
        ptype = p['penalty_type']
        if p.get('games'):
            ptype += f" ({p['games']}g)"

        print(f"{date_str:<12} {p['player_name']:<25} ${p['amount']:>10,.0f} {ptype:<12} {p['reason']:<20}")

    print("-"*90)
    print(f"Total: {len(penalties)} penalties - ${sum(p['amount'] for p in penalties):,.0f}")
    print("="*90)


def export_csv(penalties, filename='nhl_penalties_export.csv'):
    """Export penalties to CSV"""
    import csv

    if not penalties:
        print("No penalties to export")
        return

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'date', 'player_name', 'penalty_type', 'amount', 'games', 'reason', 'url'
        ])
        writer.writeheader()

        for p in sorted(penalties, key=lambda x: x['date'], reverse=True):
            writer.writerow({
                'date': p['date'][:10],
                'player_name': p['player_name'],
                'penalty_type': p['penalty_type'],
                'amount': p['amount'],
                'games': p.get('games', ''),
                'reason': p['reason'],
                'url': p.get('url', '')
            })

    print(f"✅ Exported {len(penalties)} penalties to {filename}")


def main():
    parser = argparse.ArgumentParser(description='View NHL player safety penalties')
    parser.add_argument('--summary', action='store_true', help='Show summary statistics')
    parser.add_argument('--list', action='store_true', help='Show detailed list')
    parser.add_argument('--update-dates', action='store_true', help='Interactively update dates')
    parser.add_argument('--export-csv', action='store_true', help='Export to CSV')
    parser.add_argument('--year', type=int, help='Filter by year (e.g., 2025)')
    parser.add_argument('--file', default='nhl_penalties_2025.json', help='JSON file to read')

    args = parser.parse_args()

    penalties = load_penalties(args.file)

    if not penalties:
        print("No penalties found. Run the scraper first:")
        print("  python scrape_nhl_player_safety.py")
        return

    if args.update_dates:
        update_penalty_date(args.file)
    elif args.export_csv:
        export_csv(penalties)
    elif args.list:
        show_detailed_list(penalties, args.year)
    elif args.summary:
        show_summary(penalties, args.year)
    else:
        # Default: show both
        show_summary(penalties, args.year)
        print()
        show_detailed_list(penalties, args.year)


if __name__ == "__main__":
    main()
