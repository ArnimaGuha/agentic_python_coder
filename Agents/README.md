# 🤖 Code-Writer Agent

**Part 1 of a dual-agent architecture** — an AI-powered code generation service backed by [Qwen2.5-Coder-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) via the Hugging Face Inference API.

```
┌─────────────┐     POST /generate     ┌──────────────────┐     Chat Completion     ┌─────────────────┐
│   Client /   │ ─────────────────────► │  Code-Writer     │ ──────────────────────► │  HF Inference   │
│   Checker    │ ◄───────────────────── │  Agent (FastAPI) │ ◄────────────────────── │  API (Qwen2.5)  │
│   Agent      │     CodeResponse       │                  │     Generated Code      │                 │
└─────────────┘                         └──────────────────┘                         └─────────────────┘
```

## Quick Start

### 1. Clone & Install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your Hugging Face token
# Get one at: https://huggingface.co/settings/tokens
```

### 3. Run

```bash
python main.py
```

The server starts at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Endpoints

### `POST /generate` — Generate Code

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Write a Python function that implements binary search on a sorted list. Include type hints and handle edge cases.",
    "language": "python"
  }'
```

**Request body:**

| Field         | Type     | Required | Description                              |
|---------------|----------|----------|------------------------------------------|
| `task`        | string   | ✅       | Natural-language coding task             |
| `language`    | string   | ❌       | Target language (auto-detected if omitted)|
| `context`     | string   | ❌       | Existing code or architectural context   |
| `constraints` | string   | ❌       | Constraints ("no deps", "async", etc.)   |

**Response:**

```json
{
  "files": [
    {
      "filename": "binary_search.py",
      "language": "python",
      "content": "def binary_search(arr: list[int], target: int) -> int:\n    ..."
    }
  ],
  "explanation": "Implemented iterative binary search with O(log n) complexity...",
  "metadata": {
    "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "temperature": 0.2,
    "max_tokens": 4096,
    "latency_ms": 2340.5
  }
}
```

### `GET /health` — Health Check

```bash
curl http://localhost:8000/health
```

### `GET /models` — Model Info

```bash
curl http://localhost:8000/models
```

## Configuration

All settings can be overridden via environment variables or `.env` file:

| Variable      | Default                              | Description              |
|---------------|--------------------------------------|--------------------------|
| `HF_TOKEN`    | *(required)*                         | Hugging Face API token   |
| `MODEL_NAME`  | `Qwen/Qwen2.5-Coder-32B-Instruct`   | Model to use             |
| `MAX_TOKENS`  | `4096`                               | Max output tokens        |
| `TEMPERATURE` | `0.2`                                | Generation temperature   |
| `TOP_P`       | `0.95`                               | Nucleus sampling         |
| `HOST`        | `0.0.0.0`                            | Server bind address      |
| `PORT`        | `8000`                               | Server port              |
| `MAX_RETRIES` | `3`                                  | API call retry attempts  |
| `RETRY_DELAY` | `1.0`                                | Base retry delay (secs)  |

## Project Structure

```
ASCII/
├── main.py              # Server entrypoint
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── README.md
└── agent/
    ├── __init__.py
    ├── api.py           # FastAPI endpoints
    ├── config.py        # Configuration & env loading
    ├── llm_client.py    # HF InferenceClient wrapper + retry logic
    ├── models.py        # Pydantic request/response models
    ├── parser.py        # LLM output → structured code extraction
    └── prompts.py       # System prompt engineering
```

## Dual-Agent Architecture

This is **Part 1** (Writer). Part 2 (Checker) will:
- Accept a `CodeResponse` from this agent
- Analyze each `CodeFile` for bugs, security issues, and style problems
- Return a review with fix suggestions

The structured `CodeResponse` format is designed specifically to make this handoff seamless.
