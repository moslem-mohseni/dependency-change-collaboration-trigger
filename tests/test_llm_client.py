import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "llm_study"))
from client import BudgetExceeded, LLMClient


def test_mock_is_labelled_and_cached(tmp_path):
    client = LLMClient(cache_dir=tmp_path / "cache")
    messages = [{"role": "user", "content": "synthetic task"}]
    result = client.complete(messages, 3)
    assert client.last["mock"] and not client.last["cached"]
    assert client.complete(messages, 3) == result
    assert client.last["cached"]
    client.complete(messages, 4)
    assert len(list((tmp_path / "cache").glob("*.json"))) == 2


def test_budget_aborts_before_a_paid_request(tmp_path):
    called = []
    client = LLMClient("openai", "test", tmp_path / "cache", budget_usd=0.001,
                       price_input_per_million=1000, price_output_per_million=1000,
                       transport=lambda *a: called.append(a))
    with pytest.raises(BudgetExceeded):
        client.complete([{"role": "user", "content": "hello"}], 1)
    assert not called


def test_budget_reservations_survive_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    def transport(*args):
        return {"choices": [{"message": {"content": "answer"}}]}
    args = dict(backend="openai", model="test", cache_dir=tmp_path / "cache",
                budget_usd=0.008, price_input_per_million=1, price_output_per_million=1,
                transport=transport)
    client = LLMClient(**args)
    client.complete([{"role": "user", "content": "one"}], 0)
    state = json.loads((tmp_path / "budget.json").read_text())
    assert state["reserved_usd"] > 0
    restarted = LLMClient(**args)
    restarted.complete([{"role": "user", "content": "one"}], 0)
    assert json.loads((tmp_path / "budget.json").read_text()) == state
    assert "test-key-not-real" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


def test_unknown_pricing_fails_closed(tmp_path):
    with pytest.raises(BudgetExceeded):
        LLMClient("openai", "test", tmp_path / "cache").complete([], 0)
