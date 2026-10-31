import pytest

from app.schemas import MatchResult
from app.services.gemini import GeminiConnectionError, GeminiService


class Response:
    text = '{"overall_score": 80, "recommendation": "strong_match"}'


class Models:
    def generate_content(self, **kwargs):
        return Response()


class Client:
    models = Models()


class ListedModel:
    def __init__(self, name, actions=("generateContent",)):
        self.name = name
        self.supported_actions = actions


class ListingModels(Models):
    def list(self):
        return [
            ListedModel("models/gemini-3.5-flash-lite"),
            ListedModel("models/embedding-only", ()),
        ]


class ListingClient:
    models = ListingModels()


def test_structured_gemini_response_is_validated():
    result = GeminiService(client=Client()).structured("return json", MatchResult)
    assert result.overall_score == 80


def test_gemini_call_limit():
    service = GeminiService(client=Client())
    service.settings.max_llm_calls_per_run = 0
    with pytest.raises(RuntimeError, match="limit"):
        service.structured("return json", MatchResult)


def test_connection_lists_models_and_tests_generation():
    result = GeminiService(client=ListingClient()).test_connection("gemini-3.5-flash-lite")
    assert result["model"] == "gemini-3.5-flash-lite"
    assert result["models"][0]["supports_generation"] is True
    assert result["models"][1]["supports_generation"] is False


def test_connection_reports_missing_model():
    with pytest.raises(GeminiConnectionError) as error:
        GeminiService(client=ListingClient()).test_connection("gemini-nope")
    assert error.value.code == "model_not_found"


def test_connection_reports_missing_key():
    service = GeminiService(client=None, api_key="")
    service.client = None
    service.settings.gemini_api_key = ""
    with pytest.raises(GeminiConnectionError) as error:
        service.list_models()
    assert error.value.code == "authentication"
