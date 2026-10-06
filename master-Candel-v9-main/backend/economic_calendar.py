"""ForexFactory high-impact event blackout using its public weekly XML feed."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, time as local_time
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DEFAULT_CALENDAR_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.xml'
CALENDAR_TIMEZONE = ZoneInfo('America/New_York')
EVENT_BLACKOUT_BEFORE_SECONDS = 30 * 60
EVENT_BLACKOUT_AFTER_SECONDS = 30 * 60
CALENDAR_MAX_AGE_SECONDS = 20 * 60
CALENDAR_REFRESH_SECONDS = 15 * 60
CALENDAR_MAX_BYTES = 2_000_000


class EconomicCalendar:
    def __init__(self, url=None):
        self.url = url or os.environ.get('FOREX_FACTORY_CALENDAR_URL', DEFAULT_CALENDAR_URL)
        self.events = []
        self.updated_at = None
        self.error = None

    @staticmethod
    def _parse_events(payload):
        root = ET.fromstring(payload)
        events = []
        for item in root.findall('.//event'):
            impact = (item.findtext('impact') or '').strip().lower()
            if impact != 'high':
                continue
            currency = (item.findtext('country') or '').strip().upper()
            date_text = (item.findtext('date') or '').strip()
            time_text = (item.findtext('time') or '').strip()
            if not currency or not date_text:
                continue
            event_date = datetime.strptime(date_text, '%m-%d-%Y').date()
            try:
                event_time = datetime.strptime(time_text.replace(' ', '').upper(), '%I:%M%p').time()
                start = datetime.combine(event_date, event_time, CALENDAR_TIMEZONE)
                end = start
            except ValueError:
                start = datetime.combine(event_date, local_time.min, CALENDAR_TIMEZONE)
                end = datetime.combine(event_date, local_time.max, CALENDAR_TIMEZONE)
            events.append({
                'currency': currency,
                'impact': 'high',
                'startEpoch': start.timestamp(),
                'endEpoch': end.timestamp(),
                'title': (item.findtext('title') or '').strip(),
            })
        return events

    @classmethod
    def _fetch_events(cls, url):
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'MasterCandle/1.0 economic-calendar risk filter'},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = response.read(CALENDAR_MAX_BYTES + 1)
        if len(payload) > CALENDAR_MAX_BYTES:
            raise ValueError('ECONOMIC_CALENDAR_RESPONSE_TOO_LARGE')
        return cls._parse_events(payload)

    async def refresh(self):
        try:
            events = await asyncio.to_thread(self._fetch_events, self.url)
        except (OSError, TimeoutError, ValueError, ET.ParseError) as exc:
            self.events = []
            self.updated_at = None
            self.error = type(exc).__name__
            logger.warning('ForexFactory calendar unavailable; using candle-based safety filters: %s', self.error)
            return False
        self.events = events
        self.updated_at = time.time()
        self.error = None
        return True

    @staticmethod
    def _symbol_currencies(symbol):
        normalized = ''.join(character for character in str(symbol).upper() if character.isalpha())
        if normalized.startswith('FRX'):
            normalized = normalized[3:]
        normalized = normalized.replace('OTC', '')
        if len(normalized) == 6:
            return {normalized[:3], normalized[3:]}
        return set()

    def blackout_event(self, symbol, now=None):
        now = time.time() if now is None else float(now)
        if self.updated_at is None or now - self.updated_at > CALENDAR_MAX_AGE_SECONDS:
            return None
        currencies = self._symbol_currencies(symbol)
        if not currencies:
            return None
        for event in self.events:
            if event['currency'] not in currencies:
                continue
            if event['startEpoch'] - EVENT_BLACKOUT_BEFORE_SECONDS <= now <= event['endEpoch'] + EVENT_BLACKOUT_AFTER_SECONDS:
                return event
        return None

    def status(self, now=None):
        now = time.time() if now is None else float(now)
        available = self.updated_at is not None and now - self.updated_at <= CALENDAR_MAX_AGE_SECONDS
        return {
            'source': 'FOREX_FACTORY_WEEKLY_XML',
            'available': available,
            'eventCount': len(self.events) if available else 0,
            'updatedAt': self.updated_at,
            'error': self.error,
            'fallback': 'ATR_SPIKE_AND_TICK_VOLUME_FILTERS',
        }
