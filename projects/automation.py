"""Dependency-free portfolio demos. All outputs are local; nothing is sent."""
import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


def guest(message, knowledge):
    """Grounded FAQ drafting with mandatory human approval and safe fallback."""
    text = message.lower()
    if any(word in text for word in ('refund', 'emergency', 'cancel', 'fire', 'injury')):
        return {'status': 'escalate', 'draft': None, 'reason': 'Sensitive request requires a human'}
    matches = [v for k, v in knowledge.items() if k.lower() in text]
    if not matches:
        return {'status': 'escalate', 'draft': None, 'reason': 'No supported answer in property knowledge'}
    return {'status': 'needs_approval', 'draft': 'Hello! ' + ' '.join(matches), 'sent': False}


def leads(source, database):
    """Persist normalized leads; unique email makes repeated imports idempotent."""
    accepted = rejected = duplicates = 0
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS leads (email TEXT PRIMARY KEY, name TEXT NOT NULL)')
        with open(source, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not {'email', 'name'} <= set(reader.fieldnames or []):
                raise ValueError('CSV requires name and email columns')
            for row in reader:
                email = (row.get('email') or '').strip().lower()
                name = (row.get('name') or '').strip()
                if email.count('@') != 1 or not all(email.split('@')) or not name:
                    rejected += 1
                    continue
                cursor = db.execute('INSERT OR IGNORE INTO leads VALUES (?, ?)', (email, name))
                if cursor.rowcount:
                    accepted += 1
                else:
                    duplicates += 1
    return dict(accepted=accepted, rejected=rejected, duplicates=duplicates)


def sales(source):
    totals = defaultdict(Decimal)
    count = 0
    with open(source, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'date', 'amount'} <= set(reader.fieldnames or []):
            raise ValueError('CSV requires date and amount columns')
        for line, row in enumerate(reader, 2):
            from datetime import date
            day = date.fromisoformat(row['date']).isoformat()
            amount = Decimal(row['amount'])
            if not amount.is_finite():
                raise ValueError(f'Non-finite amount on line {line}')
            totals[day] += amount
            count += 1
    total = sum(totals.values(), Decimal(0))
    lines = ['# Sales report', '', f'Transactions: {count}', f'Net sales: {total:.2f}', '', '| Date | Net sales |', '|---|---:|']
    lines += [f'| {day} | {value:.2f} |' for day, value in sorted(totals.items())]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('guest'); p.add_argument('message'); p.add_argument('--knowledge', required=True)
    p = sub.add_parser('leads'); p.add_argument('source'); p.add_argument('--database', required=True)
    p = sub.add_parser('sales'); p.add_argument('source'); p.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'guest':
        print(json.dumps(guest(args.message, json.loads(Path(args.knowledge).read_text())), indent=2))
    elif args.command == 'leads':
        print(json.dumps(leads(args.source, args.database), indent=2))
    else:
        report = sales(args.source)
        Path(args.output).write_text(report, encoding='utf-8')
        print(report)

if __name__ == '__main__':
    main()
