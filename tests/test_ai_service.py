"""Tests for app.admin.ai_service."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from app.admin.ai_service import (EXTRACTION_PROMPT, _parse_json_response,
                                  discover_documents,
                                  discover_documents_deep, extract_regattas)

# --- _parse_json_response ---


class TestParseJsonResponse:
    def test_plain_json_array(self):
        raw = '[{"name": "Test Regatta"}]'
        result = _parse_json_response(raw)
        assert result == [{"name": "Test Regatta"}]

    def test_strips_code_fences(self):
        raw = '```json\n[{"name": "Test"}]\n```'
        result = _parse_json_response(raw)
        assert result == [{"name": "Test"}]

    def test_strips_code_fences_no_language(self):
        raw = '```\n[{"name": "Test"}]\n```'
        result = _parse_json_response(raw)
        assert result == [{"name": "Test"}]

    def test_empty_array(self):
        result = _parse_json_response("[]")
        assert result == []

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_json_response("not json at all")

    def test_non_array_raises(self):
        with pytest.raises(ValueError, match="Unexpected AI response"):
            _parse_json_response('{"name": "not an array"}')

    def test_whitespace_stripped(self):
        raw = '  \n [{"a": 1}] \n  '
        result = _parse_json_response(raw)
        assert result == [{"a": 1}]


# --- extract_regattas ---


class TestExtractRegattas:
    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_returns_parsed_regattas(self, mock_anthropic_cls, app):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text='[{"name": "Test", "start_date": "2026-03-01"}]')
        ]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            result = extract_regattas("some content", 2026)
            assert len(result) == 1
            assert result[0]["name"] == "Test"

    def test_missing_api_key_raises(self, app):
        app.config["ANTHROPIC_API_KEY"] = ""
        with app.app_context():
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                extract_regattas("content", 2026)
        app.config["ANTHROPIC_API_KEY"] = "test-key"

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_strips_code_fences_from_response(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='```json\n[{"name": "Fenced"}]\n```')]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            result = extract_regattas("content", 2026)
            assert result[0]["name"] == "Fenced"

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_timeout_raises_connection_error(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(
            request=MagicMock()
        )

        with app.app_context():
            with pytest.raises(ConnectionError, match="timed out"):
                extract_regattas("content", 2026)

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_passes_timeout_to_api(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='[{"name": "Test"}]')]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            extract_regattas("content", 2026)
            _, kwargs = mock_client.messages.create.call_args
            assert kwargs["timeout"] == 30.0


class TestExtractionPrompt:
    def test_prompt_includes_city_state_field(self):
        assert '"city_state"' in EXTRACTION_PROMPT

    def test_prompt_city_state_is_separate_from_location(self):
        assert '"location"' in EXTRACTION_PROMPT
        assert '"city_state"' in EXTRACTION_PROMPT


# --- discover_documents ---


class TestDiscoverDocuments:
    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_returns_documents(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text='[{"doc_type": "NOR", "url": "http://example.com/nor.pdf", '
                '"label": "Notice of Race"}]'
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            result = discover_documents("content", "Test Regatta", "http://example.com")
            assert len(result) == 1
            assert result[0]["doc_type"] == "NOR"

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_empty_result(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[]")]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            result = discover_documents("content", "Test", "http://example.com")
            assert result == []

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_timeout_raises_connection_error(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(
            request=MagicMock()
        )

        with app.app_context():
            with pytest.raises(ConnectionError, match="timed out"):
                discover_documents("content", "Test", "http://example.com")

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_passes_timeout_to_api(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[]")]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            discover_documents("content", "Test", "http://example.com")
            _, kwargs = mock_client.messages.create.call_args
            assert kwargs["timeout"] == 30.0


# --- discover_documents_deep ---


class TestDiscoverDocumentsDeep:
    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_returns_nor_si_only(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text='[{"doc_type": "NOR", "url": "http://example.com/nor.pdf", '
                '"label": "Notice of Race"}, '
                '{"doc_type": "SI", "url": "http://example.com/si.pdf", '
                '"label": "Sailing Instructions"}]'
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            result = discover_documents_deep(
                "content", "Test Regatta", "http://example.com"
            )
            assert len(result) == 2
            assert {d["doc_type"] for d in result} == {"NOR", "SI"}

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_timeout_raises_connection_error(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(
            request=MagicMock()
        )

        with app.app_context():
            with pytest.raises(ConnectionError, match="timed out"):
                discover_documents_deep("content", "Test", "http://example.com")

    @patch("app.admin.ai_service.anthropic.Anthropic")
    def test_passes_timeout_to_api(self, mock_cls, app):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[]")]
        mock_client.messages.create.return_value = mock_msg

        with app.app_context():
            discover_documents_deep("content", "Test", "http://example.com")
            _, kwargs = mock_client.messages.create.call_args
            assert kwargs["timeout"] == 30.0
