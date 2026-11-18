"""本地 / OpenAI 兼容 LLM：URL、工厂、调用、凭证与环境变量回退。"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from httpx import AsyncClient

from app.core.errors import NotFoundError
from app.core.security import create_access_token
from app.llm.base import LlmError
from app.llm.config_service import get_active_llm, invalidate, llm_from_env
from app.llm.connection_tester import test_credential as run_credential_test
from app.llm.openai_compat import (
    OpenAICompatProvider,
    openai_chat_completions_url,
    openai_compat_base_url,
)
from app.llm.providers import AnthropicCompatProvider, make_provider
from app.models.credential import Credential
from app.models.user import User
from app.services.discover_models import discover_models


def test_base_url_normalization():
    assert openai_compat_base_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434/v1"
    assert openai_compat_base_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434/v1"
    assert openai_compat_base_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434/v1"
    assert openai_compat_base_url("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434/v1"
    assert (
        openai_compat_base_url("http://127.0.0.1:1234/v1/chat/completions")
        == "http://127.0.0.1:1234/v1"
    )
    assert openai_compat_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert (
        openai_compat_base_url("http://127.0.0.1:8001/openai/v1")
        == "http://127.0.0.1:8001/openai/v1"
    )
    assert openai_compat_base_url("127.0.0.1:11434") == "http://127.0.0.1:11434/v1"
    assert (
        openai_chat_completions_url("http://127.0.0.1:8080")
        == "http://127.0.0.1:8080/v1/chat/completions"
    )
    with pytest.raises(LlmError):
        openai_compat_base_url("")
    with pytest.raises(LlmError):
        openai_compat_base_url("   ")


def test_factory_keeps_minimax_and_routes_openai_compat():
    local = make_provider(
        provider_name="local",
        api_key="",
        base_url=None,
        model_name="qwen2.5",
    )
    assert isinstance(local, OpenAICompatProvider)
    assert local.base_url == "http://127.0.0.1:11434/v1"

    hosted = make_provider(
        provider_name="openai",
        api_key="sk-test",
        base_url=None,
        model_name="gpt-4o-mini",
    )
    assert isinstance(hosted, OpenAICompatProvider)
    assert hosted.base_url == "https://api.openai.com/v1"

    deepseek = make_provider(
        provider_name="deepseek",
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
        model_name="deepseek-chat",
    )
    assert isinstance(deepseek, OpenAICompatProvider)

    minimax = make_provider(
        provider_name="minimax",
        api_key="sk-test",
        base_url="https://api.minimaxi.com/v1",
        model_name="MiniMax-M3",
    )
    assert isinstance(minimax, AnthropicCompatProvider)

    with pytest.raises(LlmError, match="不支持对话"):
        make_provider(provider_name="whisper", api_key="", base_url=None, model_name="whisper-1")


class _JSONResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.posts: list[dict] = []
        self.streams: list[dict] = []
        self.stream_lines: list[str] = [
            'data: {"choices":[{"delta":{"content":"你"}}]}\n',
            'data: {"choices":[{"delta":{"content":"好"}}],"usage":{"prompt_tokens":5,"completion_tokens":2}}\n',
            "data: [DONE]\n",
        ]
        self.stream_status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self.posts.append({"url": url, "headers": headers, "json": json})
        if json and json.get("model") == "missing":
            return _JSONResponse(404, {"error": {"message": "model not found"}})
        return _JSONResponse(
            200,
            {
                "choices": [{"message": {"role": "assistant", "content": "本地回复"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    def stream(self, method, url, headers=None, json=None):
        self.streams.append({"method": method, "url": url, "headers": headers, "json": json})
        return _StreamCM(self.stream_lines, status=self.stream_status)


class _StreamCM:
    def __init__(self, lines: list[str], status: int = 200):
        self.status_code = status
        self._lines = lines
        self.headers = {"content-type": "application/json" if lines[0].startswith("{") else "text/event-stream"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return "".join(self._lines).encode()


def _patch_client(monkeypatch) -> list[_FakeClient]:
    created: list[_FakeClient] = []

    def factory(*args, **kwargs):
        client = _FakeClient(*args, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr("app.llm.openai_compat.httpx.AsyncClient", factory)
    return created


@pytest.mark.asyncio
async def test_complete_posts_chat_completions_without_key(monkeypatch):
    created = _patch_client(monkeypatch)
    provider = make_provider(
        provider_name="local",
        api_key="",
        base_url="http://127.0.0.1:11434",
        model_name="qwen2.5",
        params_json={"temperature": 0.2},
    )
    text = await provider.complete(
        "现在呢",
        system="只回答一句",
        history=[{"role": "user", "content": "你好"}, {"role": "assistant", "content": "在"}],
        max_tokens=128,
    )
    assert text == "本地回复"
    assert provider.last_usage is not None
    assert provider.last_usage.prompt_tokens == 4
    assert provider.last_usage.completion_tokens == 2
    posted = created[0].posts[0]
    assert posted["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert "Authorization" not in posted["headers"]
    assert posted["headers"]["Content-Type"] == "application/json"
    assert posted["json"]["model"] == "qwen2.5"
    assert posted["json"]["max_tokens"] == 128
    assert posted["json"]["temperature"] == 0.2
    assert posted["json"]["stream"] is False
    assert posted["json"]["messages"][0] == {"role": "system", "content": "只回答一句"}
    assert posted["json"]["messages"][-1]["role"] == "user"
    assert "现在呢" in posted["json"]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_complete_sends_bearer_and_surfaces_http_error(monkeypatch):
    created = _patch_client(monkeypatch)
    provider = make_provider(
        provider_name="openai",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model_name="missing",
    )
    with pytest.raises(LlmError, match="model not found"):
        await provider.complete("hi")
    assert created[0].posts[0]["headers"]["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_stream_chat_yields_sse_tokens(monkeypatch):
    created = _patch_client(monkeypatch)
    provider = make_provider(
        provider_name="local",
        api_key="ollama",
        base_url="http://127.0.0.1:1234/v1",
        model_name="llama3.1",
    )
    parts: list[str] = []
    async for token in provider.stream_chat("问", system="答", max_tokens=32):
        parts.append(token)
    assert "".join(parts) == "你好"
    assert provider.last_usage is not None
    assert provider.last_usage.completion_tokens == 2
    sent = created[0].streams[0]
    assert sent["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert sent["json"]["stream"] is True
    assert sent["headers"]["Authorization"] == "Bearer ollama"


@pytest.mark.asyncio
async def test_stream_accepts_non_sse_json_body(monkeypatch):
    created = _patch_client(monkeypatch)

    def factory(*args, **kwargs):
        client = _FakeClient(*args, **kwargs)
        client.stream_lines = [
            json.dumps(
                {
                    "choices": [{"message": {"content": "整段"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            )
        ]
        created.append(client)
        return client

    monkeypatch.setattr("app.llm.openai_compat.httpx.AsyncClient", factory)
    provider = make_provider(
        provider_name="local",
        api_key="",
        base_url="http://127.0.0.1:8001/v1",
        model_name="qwen2.5",
    )
    parts = [token async for token in provider.stream_chat("问")]
    assert parts == ["整段"]
    assert provider.last_usage is not None
    assert provider.last_usage.prompt_tokens == 1


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        assert self.path == "/v1/chat/completions"
        assert self.headers.get("Authorization") is None
        if body.get("stream"):
            raw = (
                'data: {"choices":[{"delta":{"content":"流"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"式"}}],"usage":{"prompt_tokens":2,"completion_tokens":2}}\n\n'
                "data: [DONE]\n\n"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        raw = json.dumps(
            {
                "choices": [{"message": {"role": "assistant", "content": "本地回复"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        return


@pytest.mark.asyncio
async def test_complete_and_stream_against_local_http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        provider = make_provider(
            provider_name="local",
            api_key="",
            base_url=base,
            model_name="qwen2.5",
        )
        assert await provider.complete("你好", system="简短") == "本地回复"
        assert provider.last_usage is not None
        assert provider.last_usage.prompt_tokens == 3
        parts = [token async for token in provider.stream_chat("再来")]
        assert "".join(parts) == "流式"
        assert provider.last_usage.completion_tokens == 2
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_local_connection_test_allows_empty_key(monkeypatch):
    captured: dict = {}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"id": "qwen2.5"}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return _Resp()

    monkeypatch.setattr("app.llm.connection_tester.httpx.AsyncClient", _Client)
    result = await run_credential_test("local", "", base_url="http://127.0.0.1:11434")
    assert result["ok"] is True
    assert captured["url"] == "http://127.0.0.1:11434/v1/models"
    assert "Authorization" not in captured["headers"]

    missing = await run_credential_test("openai", "")
    assert missing["ok"] is False
    assert "api_key" in (missing["error"] or "")


@pytest.mark.asyncio
async def test_discover_local_without_key(monkeypatch):
    captured: dict = {}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"id": "qwen2.5"}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return _Resp()

    monkeypatch.setattr("app.services.discover_models.httpx.AsyncClient", _Client)
    cred = Credential(
        name="ollama",
        provider="local",
        modalities_json=["language"],
        base_url="http://127.0.0.1:11434",
    )
    cred.set_api_key("")
    result = await discover_models(cred)
    assert result.error is None
    assert [item["name"] for item in result.items] == ["qwen2.5"]
    assert captured["url"] == "http://127.0.0.1:11434/v1/models"
    assert "Authorization" not in captured["headers"]


class _Env:
    def __init__(self, provider: str, model: str, base: str = "", key: str = ""):
        self.llm_provider = provider
        self.llm_model_name = model
        self.llm_base_url = base
        self.llm_api_key = key


def test_llm_from_env_local_optional_key(monkeypatch):
    monkeypatch.setattr(
        "app.llm.config_service.get_settings",
        lambda: _Env("local", "qwen2.5", "http://127.0.0.1:11434/v1", ""),
    )
    resolved = llm_from_env()
    assert resolved is not None
    assert resolved.provider == "local"
    assert resolved.model_name == "qwen2.5"
    assert resolved.api_key == ""
    assert resolved.base_url == "http://127.0.0.1:11434/v1"


def test_llm_from_env_skips_hosted_without_key(monkeypatch):
    monkeypatch.setattr(
        "app.llm.config_service.get_settings",
        lambda: _Env("openai", "gpt-4o-mini", "", ""),
    )
    assert llm_from_env() is None

    monkeypatch.setattr(
        "app.llm.config_service.get_settings",
        lambda: _Env("whisper", "whisper-1", "", "sk"),
    )
    assert llm_from_env() is None


async def _admin(db_session) -> str:
    admin = User(phone="13800000911", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    token, _ = create_access_token(admin.id, role="admin")
    return token


@pytest.mark.asyncio
async def test_get_active_llm_uses_env_when_chat_default_missing(db_session, monkeypatch):
    invalidate()
    monkeypatch.setattr(
        "app.llm.config_service.get_settings",
        lambda: _Env("local", "qwen2.5", "http://127.0.0.1:11434", ""),
    )
    try:
        resolved = await get_active_llm(db_session)
        assert resolved.provider == "local"
        assert resolved.model_name == "qwen2.5"
        assert resolved.base_url == "http://127.0.0.1:11434"
    finally:
        invalidate()


@pytest.mark.asyncio
async def test_get_active_llm_db_default_beats_env(client: AsyncClient, db_session, monkeypatch):
    invalidate()
    monkeypatch.setattr(
        "app.llm.config_service.get_settings",
        lambda: _Env("local", "qwen2.5", "http://127.0.0.1:11434/v1", ""),
    )
    token = await _admin(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    cred = await client.post(
        "/api/admin/credentials",
        headers=headers,
        json={"name": "mm-env", "provider": "minimax", "api_key": "sk-minimax-test"},
    )
    assert cred.status_code == 201, cred.text
    model = await client.post(
        "/api/admin/models",
        headers=headers,
        json={
            "name": "MiniMax-M3",
            "provider": "minimax",
            "type": "language",
            "credential_id": cred.json()["id"],
        },
    )
    assert model.status_code == 201, model.text
    default = await client.put(
        "/api/admin/default-models/chat",
        headers=headers,
        json={"model_id": model.json()["id"]},
    )
    assert default.status_code == 200, default.text
    try:
        resolved = await get_active_llm(db_session)
        assert resolved.provider == "minimax"
        assert resolved.model_name == "MiniMax-M3"
        assert resolved.api_key == "sk-minimax-test"
    finally:
        invalidate()


@pytest.mark.asyncio
async def test_create_local_credential_without_api_key(client: AsyncClient, db_session):
    token = await _admin(db_session)
    resp = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "ollama",
            "provider": "local",
            "base_url": "http://127.0.0.1:11434/v1",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["provider"] == "local"
    assert body["has_api_key"] is False
    assert body["base_url"] == "http://127.0.0.1:11434/v1"
    assert body["modalities"] == ["language", "embedding"]

    denied = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "oa", "provider": "openai", "api_key": ""},
    )
    assert denied.status_code == 400


@pytest.mark.asyncio
async def test_providers_endpoint_marks_local_key_optional(client: AsyncClient):
    resp = await client.get("/api/providers")
    assert resp.status_code == 200
    rows = {item["name"]: item for item in resp.json()}
    assert rows["local"]["requires_api_key"] is False
    assert rows["local"]["default_base_url"] == "http://127.0.0.1:11434/v1"
    assert rows["ollama"]["requires_api_key"] is False
    assert rows["ollama"]["modalities"] == ["language", "embedding"]
    assert rows["openai"]["requires_api_key"] is True
    assert rows["minimax"]["requires_api_key"] is True


@pytest.mark.asyncio
async def test_env_without_model_still_reports_missing_default(db_session, monkeypatch):
    invalidate()
    monkeypatch.setattr(
        "app.llm.config_service.get_settings",
        lambda: _Env("local", "", "http://127.0.0.1:11434/v1", ""),
    )
    try:
        with pytest.raises(NotFoundError, match="没有默认模型"):
            await get_active_llm(db_session)
    finally:
        invalidate()


@pytest.mark.parametrize("api_key", ["", "gateway-key"])
async def test_ollama_embeddings_use_configured_endpoint(monkeypatch, api_key):
    import httpx

    from app.llm.config_service import EmbeddingResolved
    from app.vector.embeddings import embed_texts

    def respond(request):
        assert str(request.url) == "http://models.test:11434/v1/embeddings"
        assert request.headers.get("authorization") == (f"Bearer {api_key}" if api_key else None)
        assert json.loads(request.content)["input"] == ["one", "two"]
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]},
        ]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("app.vector.embeddings.httpx.AsyncClient", lambda **kwargs: client)
    config = EmbeddingResolved("ollama", "http://models.test:11434", api_key, "embedding-model", None)
    assert await embed_texts(config, ["one", "two"]) == [[1.0], [2.0]]


async def test_partial_stream_fails_without_completion_marker(monkeypatch):
    client = _FakeClient()
    client.stream_lines = ['data: {"choices":[{"delta":{"content":"partial"}}]}\n']
    monkeypatch.setattr("app.llm.openai_compat.httpx.AsyncClient", lambda **kwargs: client)
    provider = make_provider(provider_name="ollama", api_key="", base_url=None, model_name="chat")
    stream = provider.stream_chat("hi")
    assert await anext(stream) == "partial"
    with pytest.raises(LlmError, match="提前结束"):
        await anext(stream)
