from datetime import datetime
from zoneinfo import ZoneInfo

from economic_calendar import EconomicCalendar


def test_forexfactory_high_impact_events_match_pair_currencies():
    payload = b'''<?xml version="1.0" encoding="utf-8"?>
    <weeklyevents>
      <event><title>Rate decision</title><country>USD</country>
        <date><![CDATA[12-01-2026]]></date><time><![CDATA[8:30am]]></time>
        <impact><![CDATA[High]]></impact></event>
      <event><title>Minor report</title><country>EUR</country>
        <date><![CDATA[12-01-2026]]></date><time><![CDATA[9:00am]]></time>
        <impact><![CDATA[Low]]></impact></event>
    </weeklyevents>'''

    events = EconomicCalendar._parse_events(payload)
    calendar = EconomicCalendar()
    calendar.events = events
    calendar.updated_at = events[0]['startEpoch']

    assert calendar.blackout_event('frxEURUSD', events[0]['startEpoch'])['currency'] == 'USD'
    assert calendar.blackout_event('GBPJPY', events[0]['startEpoch']) is None


def test_unknown_high_impact_event_time_blocks_its_local_day():
    payload = b'''<weeklyevents>
      <event><title>Rate decision</title><country>USD</country>
        <date><![CDATA[12-01-2026]]></date><time><![CDATA[Tentative]]></time>
        <impact><![CDATA[High]]></impact></event>
    </weeklyevents>'''

    event = EconomicCalendar._parse_events(payload)[0]
    local_midday = datetime(2026, 12, 1, 12, tzinfo=ZoneInfo('America/New_York')).timestamp()
    calendar = EconomicCalendar()
    calendar.events = [event]
    calendar.updated_at = local_midday

    assert calendar.blackout_event('XAUUSD', local_midday) == event
