import json
import subprocess
import time
from pathlib import Path


WORKER = Path(__file__).resolve().parents[1] / 'analysis_worker.mjs'


def test_analysis_worker_returns_safe_ui_payload_for_closed_candles():
    now = int(time.time() // 60) * 60
    candles = [
        {
            'epoch': now - (60 - index) * 60,
            'open': 100.0 + index,
            'high': 101.0 + index,
            'low': 99.0 + index,
            'close': 100.5 + index,
        }
        for index in range(60)
    ]
    result = subprocess.run(
        ['node', str(WORKER)],
        input=json.dumps({'candles': candles, 'seconds': 60, 'freshness': 300}) + '\n',
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    payload = json.loads(result.stdout)

    assert payload['quality']['status'] == 'VALID'
    assert payload['quality']['score'] == 100
    assert payload['signal']['direction'] == 'NO_SIGNAL'
    assert payload['signal']['executionOrder'] is False
