import pytest

from app.schemas.brain import ChatRequest, ChatResponse
from app.services.brain import BrainService, BrainServiceError


class TestBrainService:
    def setup_method(self) -> None:
        self.service = BrainService()

    def test_chat_returns_placeholder(self) -> None:
        result = self.service.chat("Hello, world!")
        assert "[Falso Brain Placeholder]" in result
        assert "Hello, world!" in result

    def test_chat_raises_on_empty_prompt(self) -> None:
        with pytest.raises(BrainServiceError, match="Prompt cannot be empty"):
            self.service.chat("")

    def test_chat_raises_on_whitespace_only(self) -> None:
        with pytest.raises(BrainServiceError, match="Prompt cannot be empty"):
            self.service.chat("   \n\t  ")

    def test_chat_truncates_long_prompt_in_response(self) -> None:
        long = "a" * 200
        result = self.service.chat(long)
        assert "..." in result

    def test_chat_response_model(self) -> None:
        response = ChatResponse(
            response="test response",
            model="gpt-4o-mini",
        )
        assert response.response == "test response"
        assert response.model == "gpt-4o-mini"
        assert response.timestamp is not None

    def test_chat_request_model(self) -> None:
        request = ChatRequest(prompt="test prompt")
        assert request.prompt == "test prompt"
