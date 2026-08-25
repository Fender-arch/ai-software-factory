from integrations.llm import complete_json, get_llm_provider
from integrations.llm.base import StubLLM
from integrations.llm.groq import GroqLLM


def test_stub_llm_returns_none():
    provider = get_llm_provider()
    assert isinstance(provider, StubLLM)
    assert complete_json("sys", "user") is None


def test_groq_llm_without_key_returns_none():
    llm = GroqLLM(api_key="")
    assert llm.complete_json("sys", "user") is None
