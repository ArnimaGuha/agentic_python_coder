"""
coding_agent.py

Responsible for generating (and revising) a single Python solution string
for the coding <-> testing agent loop driven by main.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()
HF_TOKEN = os.environ.get("HF_TOKEN")
MODEL_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct"

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
CODING_PROMPT_PATH = PROMPTS_DIR / "coding_prompt.txt"

_client = InferenceClient(model=MODEL_NAME, token=HF_TOKEN)


def _extract_code_block(text: str) -> str:
    import re
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _build_prompt(problem_statement: str, feedback: str | None) -> str:
    if CODING_PROMPT_PATH.exists():
        template = CODING_PROMPT_PATH.read_text(encoding="utf-8")
        base = template.format(problem=problem_statement)
    else:
        base = (
            "Write a single Python solution for the following problem. "
            "Return ONLY a python code block, no explanation.\n\n"
            f"Problem:\n{problem_statement}"
        )

    if feedback:
        base += (
            "\n\nYour previous attempt failed these tests:\n"
            f"{feedback}\n\nFix the code so all tests pass."
        )
    return base


def generate_code(problem_statement: str, feedback: str | None = None) -> str:
    """Generate (or revise) a Python solution. Returns raw code as a string."""
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set in environment")

    prompt = _build_prompt(problem_statement, feedback)
    response = _client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.2,
    )
    raw_text = response.choices[0].message.content
    return _extract_code_block(raw_text)