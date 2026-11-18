"""语音转文字后端。

字幕流水线使用 settings.backend_kind 选择实现：
默认 OpenAI 兼容接口，另外可以是 faster-whisper、whisper.cpp，或本地 HTTP 服务。
"""
