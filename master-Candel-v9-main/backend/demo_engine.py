"""Deterministic virtual-money simulation; never used by live analytical signals."""
import copy
import json
import math
import time
from pathlib import Path
from fastapi import HTTPException

CATALOG = json.loads((Path(__file__).parent / 'demo_catalog.json').read_text())
DURATIONS = [5, 15, 30, 60, 120, 300]
ACTIVE = {'OPEN', 'PENDING'}


def quote(pair_id, timestamp):
    market = CATALOG[pair_id]
    t = (timestamp % 120000) / 1000
    value = market['base'] * (1 + .00065 * (math.sin(t * math.pi / 6) * .72 + math.sin(t * math.pi / 2) * .18))
    return round(value, market['precision'])


def settle(account, now):
    for trade in account['trades']:
        if trade['status'] == 'PENDING' and now >= trade['startsAt']:
            trade.update(status='OPEN', entryPrice=quote(trade['pairId'], trade['startsAt']))
        if trade['status'] == 'OPEN' and now >= trade['expiresAt']:
            exit_price = quote(trade['pairId'], trade['expiresAt'])
            tied = exit_price == trade['entryPrice']
            won = exit_price > trade['entryPrice'] if trade['direction'] == 'UP' else exit_price < trade['entryPrice']
            credit = trade['stakeCents'] if tied else trade['stakeCents'] + math.floor(trade['stakeCents'] * trade['payoutPercent'] / 100 + .5) if won else 0
            trade.update(exitPrice=exit_price, creditCents=credit, status='TIED' if tied else 'WON' if won else 'LOST')
            account['balanceCents'] += credit


def apply_action(original, action=None):
    account = copy.deepcopy(original)
    now = int(time.time() * 1000)
    settle(account, now)
    if action is None:
        return account, ''
    request_id = action['requestId']
    if request_id in account['receipts']:
        return account, 'Request already saved.'
    kind = action['kind']
    if kind in {'deposit', 'withdraw'}:
        amount = action['cents']
        if amount is None or not 100 <= amount <= 100_000_000:
            raise HTTPException(422, 'Enter a demo amount between $1 and $1,000,000.')
        if kind == 'withdraw' and amount > account['balanceCents']:
            raise HTTPException(409, 'Insufficient available demo balance.')
        if kind == 'deposit' and account['balanceCents'] + amount > 1_000_000_000:
            raise HTTPException(422, 'Maximum demo balance is $10,000,000.')
        account['balanceCents'] += amount if kind == 'deposit' else -amount
        message = 'Demo funds added. No real payment was made.' if kind == 'deposit' else 'Demo funds removed. No real withdrawal was made.'
    elif kind == 'reset':
        for trade in account['trades']:
            if trade['status'] in ACTIVE:
                trade['status'] = 'CANCELLED'
        account['archive'].extend(account['trades'])
        account.update(balanceCents=1_000_000, trades=[])
        message = 'Demo account reset to $10,000.00. Previous history archived.'
    else:
        pair, stake, duration = action['pairId'], action['stakeCents'], action['duration']
        if pair not in CATALOG or duration not in DURATIONS or action['direction'] not in {'UP', 'DOWN'}:
            raise HTTPException(422, 'Choose a valid market, direction and expiry time.')
        if stake is None or stake < 100:
            raise HTTPException(422, 'Minimum demo investment is $1.00.')
        if stake > account['balanceCents']:
            raise HTTPException(409, 'Insufficient demo balance for this investment.')
        if sum(t['status'] in ACTIVE for t in account['trades']) >= 20:
            raise HTTPException(409, 'Maximum 20 active demo trades. Wait for an expiry.')
        starts_at = (now // 60000 + 1) * 60000 if action['pending'] else now
        trade = dict(id=request_id, pairId=pair, direction=action['direction'], stakeCents=stake,
                     payoutPercent=CATALOG[pair]['payoutPercent'], duration=duration, createdAt=now,
                     startsAt=starts_at, expiresAt=starts_at + duration * 1000,
                     entryPrice=None if action['pending'] else quote(pair, starts_at), exitPrice=None,
                     status='PENDING' if action['pending'] else 'OPEN', creditCents=0)
        account['trades'].insert(0, trade)
        account['balanceCents'] -= stake
        message = f"{action['direction']} demo trade {'scheduled for the next minute' if action['pending'] else 'opened'}."
    account['receipts'] = (account['receipts'] + [request_id])[-2000:]
    return account, message