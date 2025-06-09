import asyncio
from scholar_slack_bot.slack_bot import send_to_slack, send_messages_parallel, get_slack_config, SlackNotifier


def test_send_to_slack(monkeypatch):
    called = {}
    def fake_send(self, target, message):
        called['args'] = (target, message)
        return {'ok': True}
    monkeypatch.setattr(SlackNotifier, 'send_message', fake_send)
    res = send_to_slack('chan', 'hello', 'token')
    assert res['ok']
    assert called['args'] == ('chan', 'hello')


async def _run_parallel(monkeypatch):
    async def fake_send(self, target, msg):
        return {'ok': True, 'text': msg}
    monkeypatch.setattr(SlackNotifier, 'send_message_async', fake_send)
    res = await send_messages_parallel('chan', ['a', 'b'], 'token')
    return res


def test_send_messages_parallel(monkeypatch):
    res = asyncio.run(_run_parallel(monkeypatch))
    assert [r['text'] for r in res] == ['a', 'b']


def test_get_slack_config_env(monkeypatch):
    monkeypatch.setenv('SLACK_API_TOKEN', 'x')
    monkeypatch.setenv('SLACK_CHANNEL', 'y')
    cfg = get_slack_config()
    assert cfg == {'api_token': 'x', 'channel_name': 'y'}
