"""Idempotent, read-only extraction of uploaded SQLite; NEVER feeds live analysis."""
import asyncio
import hashlib
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    load_dotenv(Path(__file__).parent / '.env')
    source = Path(__file__).resolve().parent.parent / 'reference/dd/market_data.db'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    connection = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        for table, collection in [('candles_history', 'legacy_candles_unverified'), ('agent_signals', 'legacy_signals_unverified')]:
            await db[collection].create_index([('snapshotHash', 1), ('legacyId', 1)], unique=True)
            rows = connection.execute(f'SELECT * FROM {table}').fetchall()
            for row in rows:
                values = dict(row)
                key = {'snapshotHash': digest, 'legacyId': values.pop('id')}
                await db[collection].update_one(key, {'$setOnInsert': {**values, **key, 'provenance': 'USER_REPOSITORY_SQLITE_UNVERIFIED', 'trainingEligible': False}}, upsert=True)
            print(f'{collection}: {len(rows)} archival records imported (unverified)')
    finally:
        connection.close()
        client.close()


if __name__ == '__main__':
    asyncio.run(main())