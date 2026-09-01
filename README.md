# Agentic Python Coder

A small self-correcting coding pipeline: a **coding agent** writes a Python solution to a problem statement, a **testing agent** writes and runs pytest tests against it, and any failures are fed back to the coding agent for another attempt — up to a fixed number of rounds.

```
You → problem statement → Coding Agent → code
                                            ↓
                                     Testing Agent → pytest results
                                            ↓
                              pass? → done : feed failures back → retry
```

## How it works

1. **`main.py`** orchestrates the loop (`solve()`), calling the coding agent and testing agent in turn for up to `MAX_ROUNDS` rounds (default 3).
2. **`agents/coding_agent.py`** calls an LLM via the Hugging Face `InferenceClient` to generate a single Python solution as a string, using `prompts/coding_prompt.txt` as the system prompt. On retries, it's given the previous round's test failures as feedback.
3. **`agents/testing_agent.py`** calls an LLM to generate a pytest test suite for the candidate solution (using `prompts/testing_prompt.txt`), writes both the solution and the tests to a temporary directory, and runs `pytest` against them in a subprocess with a timeout. It returns a structured result (pass/fail counts, per-test failure details, raw output).
4. If all tests pass, `main.py` reports success and prints the final code. If not, and rounds run out, it prints the last known failures.

## Project structure

```
agentic_python_coder/
├── main.py                      # Orchestrates the coding <-> testing loop
├── agents/
│   ├── coding_agent.py          # Generates/revises the candidate solution
│   └── testing_agent.py         # Generates + runs pytest tests against the solution
├── prompts/
│   ├── coding_prompt.txt        # System prompt for the coding agent
│   └── testing_prompt.txt       # System prompt for the testing agent
├── .env                         # HF_TOKEN (not committed)
└── README.md
```

## Requirements

- Python 3.11+
- A [Hugging Face account](https://huggingface.co/join) and access token with **"Make calls to Inference Providers"** permission enabled

### Dependencies

```bash
pip install huggingface_hub python-dotenv pytest
```

> **Note:** Use a single Python interpreter (ideally a virtual environment) for both installing dependencies and running the project. Mixing multiple Python installs on the same machine (e.g. one from `python.org`, one bundled elsewhere) is a common source of confusing `ModuleNotFoundError` / `No module named pytest` errors, since packages installed for one interpreter aren't visible to another.

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install huggingface_hub python-dotenv pytest
```

## Setup

1. Get a Hugging Face access token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), with the Inference Providers permission checked.
2. Create a `.env` file in the project root:
   ```
   HF_TOKEN=hf_your_token_here
   ```
   Both `coding_agent.py` and `testing_agent.py` read this same variable — you only need to set it once.

   **Never commit `.env` or paste your token anywhere public.** Add `.env` to `.gitignore`.

## Usage

Run with a problem statement as a command-line argument:

```bash
python main.py "Add two integers"
```

Or run it interactively and get prompted:

```bash
python main.py
Enter the problem statement: Add two integers
```

Example output:

```
=== Round 1 ===
Coding agent: generating code...
Testing agent: generating and running tests...
Passed: 5 | Failed: 0
All tests passed! ✅

=== FINAL RESULT ===
Success: True
Rounds taken: 1

Final code:

def add_two_integers(a, b):
    """Return the sum of two integers."""
    return a + b
```

## Configuration

| Setting | Location | Default | Notes |
|---|---|---|---|
| `MODEL_NAME` (coding/testing) | top of each agent file | `Qwen/Qwen2.5-Coder-32B-Instruct` | Swap for a smaller model (e.g. `-7B-Instruct`) if you hit rate limits |
| `MAX_ROUNDS` | `main.py` | `3` | Number of generate→test→fix cycles before giving up |
| `TEST_TIMEOUT_SECONDS` | `testing_agent.py` | `15` | Kills the pytest subprocess if candidate code hangs (e.g. infinite loop) |

## Design notes / known limitations

- **Single-file solutions only.** The coding agent returns one code string, written to `solution.py`. Multi-file solutions aren't supported.
- **No sandboxing beyond a subprocess + temp dir + timeout.** Generated code runs with the same permissions as your user account. Don't run this against untrusted or adversarial problem statements.
- **Test scope is prompt-controlled.** `testing_prompt.txt` explicitly instructs the testing agent to only test what the problem statement asks for, to avoid the coding agent chasing invented requirements (e.g. type-validation tests for a problem that never mentioned invalid input).
- **LLM output isn't always well-formed.** Both agents strip markdown code fences defensively (`_extract_code_block`), and the testing agent auto-inserts `import pytest` if the model forgets it, as a safety net against occasional prompt non-compliance.

## Troubleshooting

- **`401 Unauthorized` from `router.huggingface.co`** — your `HF_TOKEN` is invalid, expired, or missing the Inference Providers scope. Generate a new token with that permission checked.
- **`No module named pytest`** — pytest isn't installed in the same Python interpreter that's running `main.py`. Check with `python -c "import sys; print(sys.executable)"` and install into that same interpreter, or use a virtual environment.
- **`Passed: 0 | Failed: 0` with a failure still reported** — this indicated a pytest collection error (bad import, syntax error) that wasn't being surfaced; the testing agent now checks pytest's `ERRORS` section (not just `FAILURES`) and falls back to raw output if it can't parse a structured failure, so this should now show a real error message instead of silence.
