"""Tests for helper functions in app.admin.routes."""

import json
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from app.admin.routes import (
    _extract_data_attributes,
    _fetch_clubspot_documents,
    _is_private_ip,
    _parse_clubspot_regatta_id,
)


# --- _is_private_ip ---


class TestIsPrivateIp:
    def test_public_ip(self):
        assert _is_private_ip("google.com") is False

    def test_localhost(self):
        assert _is_private_ip("localhost") is True

    def test_127_0_0_1(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_unresolvable_returns_true(self):
        assert _is_private_ip("does-not-exist.invalid") is True


# --- _parse_clubspot_regatta_id ---


class TestParseClubspotRegattaId:
    def test_valid_clubspot_url(self):
        url = "https://theclubspot.com/regatta/qsBq5fuO8F"
        assert _parse_clubspot_regatta_id(url) == "qsBq5fuO8F"

    def test_clubspot_url_with_subpath(self):
        url = "https://theclubspot.com/regatta/abc123/documents"
        assert _parse_clubspot_regatta_id(url) == "abc123"

    def test_non_clubspot_url(self):
        url = "https://thistleclass.com/events/foo/"
        assert _parse_clubspot_regatta_id(url) is None

    def test_clubspot_non_regatta_path(self):
        url = "https://theclubspot.com/club/abc123"
        assert _parse_clubspot_regatta_id(url) is None

    def test_empty_url(self):
        assert _parse_clubspot_regatta_id("") is None

    def test_clubspot_with_http(self):
        url = "http://theclubspot.com/regatta/XYZ789"
        assert _parse_clubspot_regatta_id(url) == "XYZ789"


# --- _extract_data_attributes ---


class TestExtractDataAttributes:
    def test_extracts_json_from_body(self):
        html = '<html><body data-regatta=\'{"name": "Test", "startDate": "2026-03-01"}\'></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_data_attributes(soup)
        assert "data-regatta" in result
        assert "Test" in result
        assert "2026-03-01" in result

    def test_ignores_non_json_attributes(self):
        html = '<html><body data-page="home" data-id="123"></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_data_attributes(soup)
        assert result == ""

    def test_ignores_non_data_attributes(self):
        html = '<html><body class="main" id="body"></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_data_attributes(soup)
        assert result == ""

    def test_handles_no_body(self):
        html = "<html></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_data_attributes(soup)
        assert result == ""

    def test_extracts_json_array(self):
        html = '<html><body data-events=\'[{"name": "A"}, {"name": "B"}]\'></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_data_attributes(soup)
        assert "data-events" in result

    def test_skips_malformed_json(self):
        html = '<html><body data-broken=\'{"unclosed: true\'></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_data_attributes(soup)
        assert result == ""


# --- _fetch_clubspot_documents ---


class TestFetchClubspotDocuments:
    @patch("app.admin.routes.requests.get")
    def test_returns_nor_document(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "type": "nor",
                    "URL": "https://cdn.example.com/nor.pdf",
                    "active": True,
                    "archived": False,
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        docs = _fetch_clubspot_documents("abc123")
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "NOR"
        assert docs[0]["url"] == "https://cdn.example.com/nor.pdf"
        assert docs[0]["label"] == "Notice of Race"

    @patch("app.admin.routes.requests.get")
    def test_returns_si_document(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "type": "si",
                    "URL": "https://cdn.example.com/si.pdf",
                    "active": True,
                    "archived": False,
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        docs = _fetch_clubspot_documents("abc123")
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "SI"

    @patch("app.admin.routes.requests.get")
    def test_ignores_unknown_doc_types(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "type": "results",
                    "URL": "https://cdn.example.com/results.pdf",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        docs = _fetch_clubspot_documents("abc123")
        assert docs == []

    @patch("app.admin.routes.requests.get")
    def test_ignores_docs_without_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"type": "nor", "URL": ""}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        docs = _fetch_clubspot_documents("abc123")
        assert docs == []

    @patch("app.admin.routes.requests.get")
    def test_returns_empty_on_api_error(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("timeout")
        docs = _fetch_clubspot_documents("abc123")
        assert docs == []

    @patch("app.admin.routes.requests.get")
    def test_returns_multiple_docs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"type": "nor", "URL": "https://cdn.example.com/nor.pdf"},
                {"type": "si", "URL": "https://cdn.example.com/si.pdf"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        docs = _fetch_clubspot_documents("abc123")
        assert len(docs) == 2
        assert {d["doc_type"] for d in docs} == {"NOR", "SI"}

    @patch("app.admin.routes.requests.get")
    def test_sends_correct_headers(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        _fetch_clubspot_documents("abc123")

        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["X-Parse-Application-Id"] == "myclubspot2017"
