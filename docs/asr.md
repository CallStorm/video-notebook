# 语音转文字

视频没有平台字幕、也没有内嵌字幕时，media-worker 用后台「默认模型 → 语音转文字」里选中的那条模型转写。转写结果仍是原来的字幕：每行 `start_ms`、`end_ms`、`text`，并落一份 SRT。后面的概览、引用和导出都读这套行，不因换后端而改格式。

默认后端不变：供应商 `whisper` 或 `openai`，走 OpenAI 兼容的 `POST {base_url}/audio/transcriptions`。没改配置时行为与以前相同，公开接口仍把 `large-v3` 这类尺寸名改成 `whisper-1`，并且必须填 API Key。

本地和自建服务是另外三个供应商。在 **设置 → 模型配置** 里添加凭证、手动添加一条「语音转文字」模型，再把它选成「语音转文字」的默认模型。改完之后，新的字幕任务才会用它；已经生成的字幕不会自动重跑。

| 供应商 | 跑在哪里 | API Key | 模型名 |
| --- | --- | --- | --- |
| `whisper` / `openai` | 托管的 OpenAI 兼容接口（默认） | 必填 | 公开 Whisper 用 `whisper-1` |
| `faster_whisper` | media-worker 进程内 | 可空 | `tiny`、`small`、`large-v3`，或本地模型目录 |
| `whisper_cpp` | 本机 `whisper-cli` 或 `pywhispercpp` | 可空 | ggml 模型文件路径 |
| `asr_server` | 你自己的 HTTP 服务 | 可空 | 服务端认的模型名 |

凭证上的通用字段：

| 字段 | 作用 |
| --- | --- |
| Base URL | 托管接口或本地服务地址。进程内模型留空 |
| API Key | 托管接口必填；本地可空。服务若要求鉴权再填 |
| `config.language` | 如 `zh`、`en`。留空或 `auto` 表示自动检测 |
| `config.model_path` | 比模型名更长的本地路径，优先于模型名 |
| `config.protocol` | 只给 `asr_server`：`openai`（默认）或 `whisper_cpp` |

语言、协议、模型路径可以在添加凭证时填写，也可以以后编辑。设备、线程等进阶项写在凭证的 `config` JSON 里，见下面的例子。

## 本地 faster-whisper

在跑 media-worker 的那个 Python 环境里安装（模型不打进默认依赖）：

```bash
cd api
uv sync --extra asr
```

faster-whisper 通过 PyAV 解码音频。第一次转写会按模型名从 Hugging Face 下载，例如 `small`。机器没有 GPU 时建议在凭证 `config` 里指定 CPU：

```json
{
  "language": "zh",
  "device": "cpu",
  "compute_type": "int8"
}
```

已经下好的 CTranslate2 模型目录可以写在模型名或 `config.model_path`，例如 `/models/faster-whisper-small`。可选字段还有 `threads`、`download_root`、`vad_filter`（默认 true）。

后台操作：供应商选 **faster-whisper（本地进程）**，API Key 留空，添加模型名 `small`，把这条模型设为「语音转文字」。

等价的接口调用（需管理员 token）：

```bash
curl -X POST http://127.0.0.1:8000/api/admin/credentials \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"local-fw","provider":"faster_whisper","modalities":["speech_to_text"],"config":{"language":"zh","device":"cpu","compute_type":"int8"}}'

curl -X POST http://127.0.0.1:8000/api/admin/models \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"small","provider":"faster_whisper","type":"speech_to_text","credential_id":1}'

curl -X PUT http://127.0.0.1:8000/api/admin/default-models/stt \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model_id":1}'
```

`credential_id` 和 `model_id` 换成上一步返回的数字。

## 本地 whisper.cpp

二选一：

- 安装 [whisper.cpp](https://github.com/ggml-org/whisper.cpp)，保证 `whisper-cli`（或 `whisper-cpp`）在 PATH 里。
- 或 `pip install pywhispercpp`。两者都安装时优先使用 Python 绑定。`config.engine` 可强制为 `cli` 或 `pywhispercpp`。

下载 ggml 模型后，模型名填文件路径：

```bash
mkdir -p "$HOME/models"
curl -L -o "$HOME/models/ggml-base.bin" \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
```

凭证示例：

```json
{
  "language": "zh",
  "threads": 4,
  "model_path": "/home/me/models/ggml-base.bin"
}
```

模型名可以是短标签（例如 `base`），只要 `model_path` 指向真实文件。

## 本地 ASR 服务

供应商选 **ASR 服务（本地 / 自建）**。Base URL 必填，API Key 可选。

OpenAI 兼容（speaches、faster-whisper-server、LocalAI 等）把地址填到 `/v1`，协议保持 `openai`：

```json
{
  "protocol": "openai",
  "language": "zh"
}
```

Base URL 示例：`http://127.0.0.1:8000/v1`。模型名按该服务的要求填，例如 `Systran/faster-whisper-small`。这里不会把 `large-v3` 改写成 `whisper-1`。

whisper.cpp 自带的 server 支持 Silero VAD。将[兼容的 GGML VAD 模型](https://huggingface.co/ggml-org/whisper-vad)下载到模型目录，然后用以下参数启动。

```bash
whisper-server -m "$HOME/models/ggml-base.bin" --host 127.0.0.1 --port 8080 \
  --vad --vad-model "$HOME/models/ggml-silero-v6.2.0.bin"
```

VAD 会在转写前检测语音。对于带置信度的响应，应用会过滤低置信度且高度疑似非语音的片段，并收敛长时间重复的短句循环。若 whisper.cpp 返回跨越长停顿的异常长字幕，media-worker 会分段复听该区间，并把识别时间映射回原音频。

Base URL 填 `http://127.0.0.1:8080`，协议选 whisper.cpp（`config.protocol` 为 `whisper_cpp`）。请求发到 `POST /inference`。如果 media-worker 与 ASR 分别运行在 NAS 和 Mac 上，请将示例中的回环地址改为两台主机之间可达的私网地址。模型由 server 启动参数决定，后台里的模型名只是一条记录，方便选成默认语音转文字。

## 仍用现在的托管接口

不改默认模型即可。若要换一家 OpenAI 兼容的托管 ASR（例如带自己的 base URL），继续用供应商 `openai` 或 `whisper`：

- Base URL 以 `/v1` 结尾
- API Key 必填
- 需要固定语言时，在凭证 config 里加 `"language": "zh"`；不写则与以前一样不传 language

这条路径仍会按停顿把没有时间轴的结果切开，再摊成字幕行。

凭证 `config.backend` 可以强制改后端，取值 `openai_compat`、`faster_whisper`、`whisper_cpp`、`http_openai`、`http_whisper_cpp`。一般用供应商下拉就够了。
