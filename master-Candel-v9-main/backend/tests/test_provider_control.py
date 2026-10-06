import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import provider_control
from provider_control import ProviderController


class FakeDeriv:
    def __init__(self):
        self.state = 'STOPPED'
        self.started = asyncio.Event()

    async def run(self):
        self.state = 'CONNECTING'
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.state = 'STOPPED'
            raise

    def status(self):
        return {'state': self.state, 'acceptedCount': 0, 'requestedCount': 0}


class FakeProcess:
    pid = 1234
    returncode = None


def test_provider_control_requires_configured_operator_key(monkeypatch):
    monkeypatch.setattr(provider_control, 'PROVIDER_CONTROL_KEY_SHA256', '')
    with pytest.raises(HTTPException) as error:
        provider_control._authorize('anything')
    assert error.value.status_code == 503


def test_provider_control_compares_operator_key_hash(monkeypatch):
    key = 'test-only-provider-key'
    digest = hashlib.sha256(key.encode()).hexdigest()
    monkeypatch.setattr(provider_control, 'PROVIDER_CONTROL_KEY_SHA256', digest)
    provider_control._authorize(key)
    with pytest.raises(HTTPException) as error:
        provider_control._authorize('wrong-key')
    assert error.value.status_code == 401


def test_deriv_provider_can_be_started_and_stopped():
    deriv = FakeDeriv()
    controller = ProviderController(deriv)

    async def exercise():
        await controller.start('deriv')
        await deriv.started.wait()
        assert controller.status()['providers']['deriv']['state'] == 'RUNNING'
        await controller.stop('deriv')
        assert controller.status()['providers']['deriv']['state'] == 'STOPPED'

    asyncio.run(exercise())


def test_deriv_provider_reports_unexpected_task_exit_as_failed():
    deriv = FakeDeriv()
    controller = ProviderController(deriv)

    async def exercise():
        async def fail():
            raise ConnectionError('socket closed')

        controller.deriv_task = asyncio.create_task(fail())
        try:
            await controller.deriv_task
        except ConnectionError:
            pass
        assert controller.status()['providers']['deriv']['state'] == 'FAILED'

    asyncio.run(exercise())


def test_observer_modes_are_mutually_exclusive(monkeypatch):
    processes = []

    async def spawn(*args, **kwargs):
        process = FakeProcess()
        processes.append((process, args, kwargs))
        return process

    monkeypatch.setattr(provider_control.asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setenv('OBSERVER_SERVICE_KEY', 'test-only-service-key')
    controller = ProviderController(FakeDeriv())

    async def exercise():
        status = await controller.start('ws_sniffer')
        assert status['providers']['ws_sniffer']['state'] == 'RUNNING'
        assert processes[0][2]['env']['OBSERVER_MODE'] == 'ws_sniffer'
        with pytest.raises(RuntimeError, match='WS_SNIFFER_ALREADY_RUNNING'):
            await controller.start('playwright_observer')

    asyncio.run(exercise())
