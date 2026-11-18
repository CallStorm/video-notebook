"""自定义 ASR 后端：默认 OpenAI 兼容路径不变，本地进程和本地服务另选。"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from httpx import AsyncClient

from app.asr.engines import cues_from_ticks, cues_from_whisper_cpp_json
from app.asr.settings import backend_kind, http_backend, model_ref, settings_from_stt
from app.core.security import create_access_token
from app.llm.config_service import SttResolved, get_active_stt
from app.models.user import User
from app.subtitles.srt import Cue, format_srt, parse_srt
from app.subtitles.transcribe import TranscribeError, request_model_name, transcribe_file


def _stt(**kwargs) -> SttResolved:
    base = {
        "provider": "whisper",
        "api_key": "sk-test",
        "model_name": "whisper-1",
        "config": None,
        "base_url": "https://api.openai.com/v1",
    }
    base.update(kwargs)
    return SttResolved(**base)


def test_default_providers_stay_openai_compatible():
    for provider in ("openai", "whisper"):
        stt = _stt(provider=provider, model_name="large-v3")
        assert backend_kind(stt) == "openai_compat"
        assert request_model_name(stt) == "whisper-1"
        assert settings_from_stt(stt).language is None


def test_local_backends_and_language():
    fw = _stt(
        provider="faster_whisper",
        api_key="",
        model_name="small",
        base_url=None,
        config={"language": "zh", "device": "cpu", "model_path": "/models/fw-small"},
    )
    assert backend_kind(fw) == "faster_whisper"
    assert model_ref(fw) == "/models/fw-small"
    settings = settings_from_stt(fw)
    assert settings.language == "zh"
    assert settings.device == "cpu"
    assert settings.api_key is None

    cpp = _stt(provider="whisper_cpp", api_key="", model_name="/models/ggml-base.bin", base_url=None)
    assert backend_kind(cpp) == "whisper_cpp"

    server = _stt(
        provider="asr_server",
        api_key="",
        model_name="large-v3",
        base_url="http://127.0.0.1:8080",
        config={"protocol": "whisper.cpp", "language": "auto"},
    )
    assert backend_kind(server) == "http_whisper_cpp"
    assert settings_from_stt(server).language is None
    assert request_model_name(server) == "large-v3"
    assert http_backend({"protocol": "openai"}) == "http_openai"


def test_backend_override_and_unknown_provider():
    forced = _stt(config={"backend": "faster_whisper"})
    assert backend_kind(forced) == "faster_whisper"
    with pytest.raises(Exception, match="还不支持"):
        backend_kind(_stt(provider="no-such"))


def test_optional_faster_whisper_decodes_wav(tmp_path):
    import wave

    faster_whisper = pytest.importorskip("faster_whisper")
    sample = tmp_path / "sample.wav"
    with wave.open(str(sample), "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", ""))
        wav.writeframes(bytes(3200))
    assert len(faster_whisper.decode_audio(str(sample))) == 1600


def test_whisper_cpp_json_becomes_cues():
    data = {
        "result": {"language": "zh"},
        "transcription": [
            {
                "timestamps": {"from": "00:00:00,000", "to": "00:00:01,200"},
                "offsets": {"from": 0, "to": 1200},
                "text": " 你好",
            }
        ],
    }
    cues, language = cues_from_whisper_cpp_json(data)
    assert language == "zh"
    assert cues == [Cue(0, 1200, "你好")]
    again = parse_srt(format_srt(cues))
    assert again == cues

    seconds, _lang = cues_from_whisper_cpp_json(
        {"language": "en", "segments": [{"start": 1.5, "end": 2.0, "text": "world"}]}
    )
    assert seconds == [Cue(1500, 2000, "world")]
    assert cues_from_ticks([(10, 25, " hi")], tick_ms=10) == [Cue(100, 250, "hi")]


@pytest.mark.asyncio
async def test_hosted_path_still_requires_key_and_known_provider():
    with pytest.raises(TranscribeError, match="API Key"):
        await transcribe_file(_stt(api_key=""), "missing.wav")
    with pytest.raises(TranscribeError, match="还不支持"):
        await transcribe_file(_stt(provider="minimax"), "missing.wav")


@pytest.mark.asyncio
async def test_post_audio_keeps_hosted_request_and_optional_local_auth(tmp_path):
    from app.subtitles import transcribe as tr

    captured: dict = {}

    class Resp:
        status_code = 200
        content = b'{"text":"hi"}'
        text = '{"text":"hi"}'

    class Client:
        async def post(self, url, headers=None, data=None, files=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["data"] = data
            return Resp()

    await tr._post_audio(Client(), _stt(model_name="large-v3"), b"abc", "a.wav", {"response_format": "json"})
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["data"]["model"] == "whisper-1"
    assert "language" not in captured["data"]

    local = _stt(
        provider="asr_server",
        api_key="",
        model_name="large-v3",
        base_url="http://127.0.0.1:9/v1",
        config={"language": "zh"},
    )
    await tr._post_audio(Client(), local, b"abc", "a.wav", {"response_format": "json"})
    assert captured["headers"] == {}
    assert captured["data"]["model"] == "large-v3"
    assert captured["data"]["language"] == "zh"


@pytest.mark.asyncio
async def test_faster_whisper_dispatch_returns_same_cue_shape(monkeypatch, tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"not-audio")

    def fake(settings, audio_path):
        assert settings.model == "tiny"
        assert settings.language == "zh"
        assert audio_path == str(audio)
        return [Cue(0, 1500, "本地转写结果很长很长很长很长很长很长很长很长")], "zh"

    monkeypatch.setattr("app.asr.engines.transcribe_faster_whisper_sync", fake)
    cues, language = await transcribe_file(
        _stt(
            provider="faster_whisper",
            api_key="",
            model_name="tiny",
            base_url=None,
            config={"language": "zh"},
        ),
        str(audio),
    )
    assert language == "zh"
    assert cues[0].start_ms == 0
    assert all(cue.end_ms > cue.start_ms for cue in cues)
    assert parse_srt(format_srt(cues))


@pytest.mark.asyncio
async def test_whisper_cpp_cli_writes_cues(monkeypatch, tmp_path):
    from app.asr.engines import transcribe_whisper_cpp_cli_sync
    from app.asr.settings import settings_from_stt as to_settings

    model = tmp_path / "ggml-base.bin"
    model.write_bytes(b"model")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"audio")
    seen: dict = {}

    def fake_run(cmd, **_kwargs):
        seen["cmd"] = cmd
        out = cmd[cmd.index("-of") + 1] + ".json"
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "result": {"language": "zh"},
                    "transcription": [
                        {"offsets": {"from": 0, "to": 800}, "text": "命令行"}
                    ],
                },
                handle,
            )

        class Proc:
            returncode = 0
            stderr = b""
            stdout = b""

        return Proc()

    monkeypatch.setattr("app.asr.engines.subprocess.run", fake_run)
    monkeypatch.setattr("app.asr.engines.resolve_whisper_cli", lambda: "/bin/whisper-cli")
    settings = to_settings(
        _stt(
            provider="whisper_cpp",
            api_key="",
            model_name=str(model),
            base_url=None,
            config={"language": "zh", "threads": 2},
        )
    )
    cues, language = transcribe_whisper_cpp_cli_sync(settings, str(audio))
    assert language == "zh"
    assert cues[0].text == "命令行"
    assert seen["cmd"][0] == "/bin/whisper-cli"
    assert "-m" in seen["cmd"] and str(model) in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("-l") + 1] == "zh"
    assert "-t" in seen["cmd"]


class _QuietHandler(BaseHTTPRequestHandler):
    body = b""
    path_seen = ""
    auth_seen = ""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        type(self).path_seen = self.path
        type(self).auth_seen = self.headers.get("Authorization") or ""
        payload = type(self).body
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        payload = b'{"data":[]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        return


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_local_openai_server_roundtrip(tmp_path):
    class Handler(_QuietHandler):
        body = (
            b'{"language":"zh","segments":[{"start":0.0,"end":1.25,"text":"\xe6\x9c\x8d\xe5\x8a\xa1\xe7\xab\xaf"}]}'
        )

    server, base = _serve(Handler)
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFFxxxx")
    try:
        cues, language = await transcribe_file(
            _stt(
                provider="asr_server",
                api_key="",
                model_name="tiny",
                base_url=f"{base}/v1",
                config={"protocol": "openai", "language": "zh"},
            ),
            str(audio),
        )
    finally:
        server.shutdown()
        server.server_close()
    assert Handler.path_seen.endswith("/audio/transcriptions")
    assert Handler.auth_seen == ""
    assert language == "zh"
    assert cues[0].text == "服务端"
    assert cues[0].end_ms == 1250
    assert parse_srt(format_srt(cues))[0].text == "服务端"


@pytest.mark.asyncio
async def test_whisper_cpp_server_roundtrip(tmp_path):
    class Handler(_QuietHandler):
        body = json.dumps(
            {
                "result": {"language": "en"},
                "transcription": [{"offsets": {"from": 0, "to": 900}, "text": " server"}],
            }
        ).encode()

    server, base = _serve(Handler)
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFFxxxx")
    try:
        cues, language = await transcribe_file(
            _stt(
                provider="asr_server",
                api_key="local-key",
                model_name="base",
                base_url=base,
                config={"protocol": "whisper_cpp"},
            ),
            str(audio),
        )
    finally:
        server.shutdown()
        server.server_close()
    assert Handler.path_seen == "/inference"
    assert Handler.auth_seen == "Bearer local-key"
    assert language == "en"
    assert cues == [Cue(0, 900, "server")]


@pytest.mark.asyncio
async def test_asr_server_requires_endpoint():
    with pytest.raises(TranscribeError, match="endpoint"):
        await transcribe_file(
            _stt(provider="asr_server", api_key="", model_name="tiny", base_url=None),
            "missing.wav",
        )


@pytest.mark.asyncio
async def test_probe_and_admin_local_credential(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr("app.asr.probe.importlib.util.find_spec", lambda _name: None)
    from app.asr.probe import probe_stt

    missing = await probe_stt(provider="faster_whisper", model_name="tiny")
    assert missing["ok"] is False
    assert "faster-whisper" in missing["error"]

    admin = User(phone="13800000771", name="ASR", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    token, _ = create_access_token(admin.id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    denied = await client.post(
        "/api/admin/credentials",
        headers=headers,
        json={"name": "hosted", "provider": "whisper"},
    )
    assert denied.status_code == 400

    created = await client.post(
        "/api/admin/credentials",
        headers=headers,
        json={
            "name": "local-fw",
            "provider": "faster_whisper",
            "modalities": ["speech_to_text"],
            "config": {"language": "zh", "device": "cpu", "model_path": "/models/fw-small"},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["has_api_key"] is False
    assert body["config"]["language"] == "zh"
    cred_id = body["id"]

    model = await client.post(
        "/api/admin/models",
        headers=headers,
        json={
            "name": "small",
            "provider": "faster_whisper",
            "type": "speech_to_text",
            "credential_id": cred_id,
        },
    )
    assert model.status_code == 201, model.text
    model_id = model.json()["id"]
    chosen = await client.put(
        "/api/admin/default-models/stt",
        headers=headers,
        json={"model_id": model_id},
    )
    assert chosen.status_code == 200, chosen.text

    stt = await get_active_stt(db_session)
    assert stt.provider == "faster_whisper"
    assert stt.model_name == "small"
    assert stt.api_key == ""
    assert model_ref(stt) == "/models/fw-small"
    assert backend_kind(stt) == "faster_whisper"

    providers = await client.get("/api/providers")
    listed = {item["name"]: item for item in providers.json()}
    assert listed["whisper"]["requires_api_key"] is True
    assert listed["faster_whisper"]["requires_api_key"] is False
    assert listed["asr_server"]["requires_api_key"] is False


def test_whisper_cpp_filters_non_speech_and_collapses_sustained_loops():
    from app.asr.http_server import parse_http_transcript

    segments = [
        {"start": 0, "end": 1, "text": "开始"},
        {"start": 1, "end": 2, "text": "疑似背景声", "no_speech_prob": 0.8, "avg_logprob": -1.5},
        {"start": 2, "end": 3, "text": "继续"},
        {"start": 3, "end": 4, "text": "继续"},
        *[{"start": n, "end": n + 2, "text": "重复。"} for n in range(4, 16, 2)],
        {"start": 16, "end": 17, "text": "结束", "no_speech_prob": 0.8, "avg_logprob": -0.1},
    ]
    cues, _, timestamped = parse_http_transcript(
        json.dumps({"segments": segments}).encode(), "application/json"
    )
    assert timestamped
    assert cues == [
        Cue(0, 1000, "开始"), Cue(2000, 3000, "继续"), Cue(3000, 4000, "继续"),
        Cue(4000, 6000, "重复。"), Cue(16000, 17000, "结束"),
    ]

    body = json.dumps({"segments": [segments[1]], "text": "疑似背景声"}).encode()
    assert parse_http_transcript(body, "application/json") == ([], None, True)
