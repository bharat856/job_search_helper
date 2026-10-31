import pytest

from app.schemas import MatchResult
from app.services.gemini import GeminiService


class Response:
    text = '{"overall_score": 80, "recommendation": "strong_match"}'


class Models:
    def generate_content(self, **kwargs):
        return Response()


class Client:
    models = Models()


def test_structured_gemini_response_is_validated():
    result = GeminiService(client=Client()).structured("return json", MatchResult)
    assert result.overall_score == 80


def test_gemini_call_limit():
    service = GeminiService(client=Client())
    service.settings.max_llm_calls_per_run = 0
    with pytest.raises(RuntimeError, match="limit"):
        service.structured("return json", MatchResult)
