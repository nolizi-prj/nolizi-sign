"""Unit tests for app.graph_convert — Graph-rendered PDF conversion with
LibreOffice fallback. All Graph traffic is a httpx.MockTransport; no network."""

import io
from pathlib import Path

import httpx
from reportlab.pdfgen import canvas

from app import conversion, graph_convert
from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"

SETTINGS = Settings(
    ms_tenant_id="t",
    ms_client_id="c",
    ms_client_secret="s",
    sp_drive_id="drive123",
    graph_convert=True,
)


def _pdf_bytes() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, "graph-rendered")
    c.save()
    return buf.getvalue()


def _transport(routes: dict[str, httpx.Response], calls: list[str]) -> httpx.MockTransport:
    """Route by '<METHOD> <path-suffix>' key; records every call."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            f"{request.method} {request.url.path}{'?format=pdf' if request.url.params.get('format') == 'pdf' else ''}",
        )
        for key, response in routes.items():
            method, suffix = key.split(" ", 1)
            if request.method == method and request.url.path.endswith(suffix.split("?")[0]):
                if "?format=pdf" in key and request.url.params.get("format") != "pdf":
                    continue
                return response
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_returns_none_when_disabled(monkeypatch) -> None:
    settings = SETTINGS.model_copy(update={"graph_convert": False})
    assert graph_convert.convert_via_graph(b"data", "docx", settings) is None


def test_returns_none_without_drive() -> None:
    settings = SETTINGS.model_copy(update={"sp_drive_id": ""})
    assert graph_convert.convert_via_graph(b"data", "docx", settings) is None


def test_returns_none_for_xlsx() -> None:
    # xlsx stays on LibreOffice: Graph paginates like Excel's print setup,
    # which would regress the one-page-per-sheet (SinglePageSheets) behavior.
    assert graph_convert.convert_via_graph(b"data", "xlsx", SETTINGS) is None


def test_success_uploads_converts_and_deletes(monkeypatch) -> None:
    monkeypatch.setattr(graph_convert, "acquire_token", lambda settings: "token")
    pdf = _pdf_bytes()
    calls: list[str] = []
    transport = _transport(
        {
            "PUT :/content": httpx.Response(201, json={"id": "item1"}),
            "GET :/content?format=pdf": httpx.Response(200, content=pdf),
            "DELETE ": httpx.Response(204),
        },
        calls,
    )

    result = graph_convert.convert_via_graph(b"docx-bytes", "docx", SETTINGS, transport=transport)

    assert result == pdf
    assert any(c.startswith("PUT") for c in calls)
    assert any("?format=pdf" in c for c in calls)
    assert any(c.startswith("DELETE") for c in calls), "temp file must be deleted"


def test_conversion_failure_returns_none_and_still_deletes(monkeypatch) -> None:
    monkeypatch.setattr(graph_convert, "acquire_token", lambda settings: "token")
    calls: list[str] = []
    transport = _transport(
        {
            "PUT :/content": httpx.Response(201, json={"id": "item1"}),
            "GET :/content?format=pdf": httpx.Response(406, json={"error": {"message": "Office Service"}}),
            "DELETE ": httpx.Response(204),
        },
        calls,
    )

    assert graph_convert.convert_via_graph(b"docx-bytes", "docx", SETTINGS, transport=transport) is None
    assert any(c.startswith("DELETE") for c in calls)


def test_non_pdf_response_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(graph_convert, "acquire_token", lambda settings: "token")
    transport = _transport(
        {
            "PUT :/content": httpx.Response(201, json={"id": "item1"}),
            "GET :/content?format=pdf": httpx.Response(200, content=b"<html>error page</html>"),
            "DELETE ": httpx.Response(204),
        },
        [],
    )

    assert graph_convert.convert_via_graph(b"docx-bytes", "docx", SETTINGS, transport=transport) is None


def test_token_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(graph_convert, "acquire_token", lambda settings: None)
    assert graph_convert.convert_via_graph(b"docx-bytes", "docx", SETTINGS) is None


# --- to_pdf_bytes integration ------------------------------------------------


def test_to_pdf_bytes_prefers_graph(monkeypatch) -> None:
    pdf = _pdf_bytes()
    monkeypatch.setattr(conversion, "convert_via_graph", lambda data, ext, settings: pdf)

    def _no_soffice(data: bytes, ext: str) -> bytes:
        raise AssertionError("LibreOffice must not run when Graph succeeded")

    monkeypatch.setattr(conversion, "_convert_with_soffice", _no_soffice)
    docx = (FIXTURES / "sample.docx").read_bytes()

    result, page_count = conversion.to_pdf_bytes(docx, "sample.docx", settings=SETTINGS)

    assert result == pdf
    assert page_count == 1


def test_to_pdf_bytes_falls_back_to_soffice(monkeypatch) -> None:
    pdf = _pdf_bytes()
    monkeypatch.setattr(conversion, "convert_via_graph", lambda data, ext, settings: None)
    monkeypatch.setattr(conversion, "_convert_with_soffice", lambda data, ext: pdf)
    docx = (FIXTURES / "sample.docx").read_bytes()

    result, _ = conversion.to_pdf_bytes(docx, "sample.docx", settings=SETTINGS)

    assert result == pdf


def test_to_pdf_bytes_without_settings_skips_graph(monkeypatch) -> None:
    pdf = _pdf_bytes()

    def _graph_must_not_run(data: bytes, ext: str, settings: Settings) -> bytes:
        raise AssertionError("Graph must not be consulted without settings")

    monkeypatch.setattr(conversion, "convert_via_graph", _graph_must_not_run)
    monkeypatch.setattr(conversion, "_convert_with_soffice", lambda data, ext: pdf)
    docx = (FIXTURES / "sample.docx").read_bytes()

    result, _ = conversion.to_pdf_bytes(docx, "sample.docx")

    assert result == pdf
