"""Testes de app.application.llm.key_pool.KeyPool"""

import pytest

from app.application.llm.key_pool import KeyPool
from app.exceptions import LlmKeyNotFoundException, LlmKeysNotConfiguredException, LlmKeysUnavailableException
from app.infrastructure.llm.keys import LlmKey, key_id_for


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _key(provider: str, secret: str) -> LlmKey:
    return LlmKey(provider=provider, key_id=key_id_for(provider, secret), secret=secret)


@pytest.fixture
def clock():
    return Clock()


def _pool(clock, *keys: LlmKey) -> KeyPool:
    return KeyPool(list(keys), clock=clock)


def test_leases_keys_in_fifo_rotation(clock):
    a, b, c = _key("gemini", "a"), _key("gemini", "b"), _key("groq", "c")
    pool = _pool(clock, a, b, c)

    leased = [pool.lease().secret for _ in range(6)]

    assert leased == ["a", "b", "c", "a", "b", "c"]


def test_provider_filter_keeps_the_fifo_order_inside_the_provider(clock):
    pool = _pool(clock, _key("gemini", "a"), _key("groq", "b"), _key("gemini", "c"))

    assert [pool.lease(provider="gemini").secret for _ in range(3)] == ["a", "c", "a"]
    assert pool.lease(provider="groq").secret == "b"


def test_embedding_skips_providers_without_embeddings(clock):
    pool = _pool(clock, _key("groq", "g"), _key("gemini", "m"))

    assert [pool.lease(embedding=True).secret for _ in range(2)] == ["m", "m"]


def test_embedding_with_only_groq_is_not_configured(clock):
    pool = _pool(clock, _key("groq", "g"))

    with pytest.raises(LlmKeysNotConfiguredException):
        pool.lease(embedding=True)


def test_exclude_skips_the_failed_key_without_consuming_its_turn(clock):
    a, b = _key("gemini", "a"), _key("gemini", "b")
    pool = _pool(clock, a, b)

    assert pool.lease(exclude={a.key_id}).secret == "b"
    assert pool.lease().secret == "a"


def test_unknown_provider_is_not_configured(clock):
    pool = _pool(clock, _key("gemini", "a"))

    with pytest.raises(LlmKeysNotConfiguredException, match="groq"):
        pool.lease(provider="groq")


def test_empty_pool_is_not_configured(clock):
    with pytest.raises(LlmKeysNotConfiguredException):
        _pool(clock).lease()


def test_rate_limited_key_leaves_the_queue_and_returns_to_the_end_after_the_cooldown(clock):
    a, b, c = _key("gemini", "a"), _key("gemini", "b"), _key("groq", "c")
    pool = _pool(clock, a, b, c)

    pool.report(a.key_id, "rate_limited", retry_after_seconds=30)

    assert [pool.lease().secret for _ in range(3)] == ["b", "c", "b"]
    clock.now += 31
    assert [pool.lease().secret for _ in range(3)] == ["c", "b", "a"]


def test_many_unavailable_keys_cost_nothing_to_skip(clock):
    keys = [_key("gemini", f"k{i}") for i in range(20)]
    pool = _pool(clock, *keys)
    for key in keys[:19]:
        pool.report(key.key_id, "rate_limited")

    assert pool.lease().secret == "k19"


def test_all_keys_cooling_down_reports_when_the_first_one_returns(clock):
    a, b = _key("gemini", "a"), _key("gemini", "b")
    pool = _pool(clock, a, b)
    pool.report(a.key_id, "rate_limited", retry_after_seconds=90)
    pool.report(b.key_id, "rate_limited", retry_after_seconds=20)

    with pytest.raises(LlmKeysUnavailableException) as exc_info:
        pool.lease()

    assert exc_info.value.retry_after_seconds == 20


def test_cooldown_uses_the_default_and_is_capped(clock):
    a = _key("gemini", "a")
    pool = _pool(clock, a)

    pool.report(a.key_id, "rate_limited")
    state = pool.snapshot().providers[0].keys[0]
    assert state.status == "cooling_down"
    assert state.available_at is not None
    assert state.available_at.timestamp() == clock.now + 60

    pool.report(a.key_id, "rate_limited", retry_after_seconds=86400)
    assert pool.snapshot().providers[0].keys[0].available_at.timestamp() == clock.now + 86400


def test_repeated_rate_limited_report_never_shortens_the_cooldown(clock):
    a = _key("gemini", "a")
    pool = _pool(clock, a)
    pool.report(a.key_id, "rate_limited", retry_after_seconds=600)

    pool.report(a.key_id, "rate_limited", retry_after_seconds=5)

    assert pool.snapshot().providers[0].keys[0].available_at.timestamp() == clock.now + 600


def test_invalid_key_is_removed_until_a_probe_accepts_it_again(clock):
    a, b = _key("gemini", "a"), _key("gemini", "b")
    pool = _pool(clock, a, b)

    pool.report(a.key_id, "invalid")

    assert [pool.lease().secret for _ in range(2)] == ["b", "b"]
    assert pool.snapshot().providers[0].keys[0].status == "invalid"
    pool.set_probe_result(a.key_id, True)
    assert [pool.lease().secret for _ in range(2)] == ["b", "a"]


def test_rate_limited_report_does_not_revive_an_invalid_key(clock):
    a = _key("gemini", "a")
    pool = _pool(clock, a)
    pool.report(a.key_id, "invalid")

    pool.report(a.key_id, "rate_limited")
    clock.now += 1000

    with pytest.raises(LlmKeysUnavailableException) as exc_info:
        pool.lease()
    assert exc_info.value.retry_after_seconds is None


def test_failed_probe_removes_key_and_successful_probe_records_the_check(clock):
    a, b = _key("gemini", "a"), _key("groq", "b")
    pool = _pool(clock, a, b)

    pool.set_probe_result(a.key_id, False)
    pool.set_probe_result(b.key_id, True)

    gemini, groq = pool.snapshot().providers
    assert gemini.keys[0].status == "invalid"
    assert groq.keys[0].status == "available"
    assert groq.keys[0].last_checked_at is not None
    assert gemini.keys[0].last_checked_at is None


def test_ok_report_keeps_the_key_in_rotation(clock):
    a = _key("gemini", "a")
    pool = _pool(clock, a)

    pool.report(a.key_id, "ok")

    assert pool.lease().secret == "a"


def test_unknown_key_id_is_rejected(clock):
    pool = _pool(clock, _key("gemini", "a"))

    with pytest.raises(LlmKeyNotFoundException):
        pool.report("gemini-unknown", "ok")
    with pytest.raises(LlmKeyNotFoundException):
        pool.set_probe_result("gemini-unknown", True)


def test_snapshot_never_exposes_secrets(clock):
    pool = _pool(clock, _key("gemini", "super-secret"))

    assert "super-secret" not in pool.snapshot().model_dump_json()
