"""
testing_agent.py

Responsible for:
1. Asking an LLM (via Hugging Face Inference Providers router) to write test
   cases for a candidate solution.
2. Actually executing those tests against the candidate code in an isolated
   subprocess.
3. Returning a structured result dict that main.py can feed back to the
   coding agent.
"""

import os
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv


from huggingface_hub import InferenceClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()
HF_TOKEN = os.environ.get("HF_TOKEN")
MODEL_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct"  # swap for -7B-Instruct if rate limited
TEST_TIMEOUT_SECONDS = 15

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
TESTING_PROMPT_PATH = PROMPTS_DIR / "testing_prompt.txt"

_client = InferenceClient(model=MODEL_NAME, token=HF_TOKEN)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompt_template() -> str:
    return TESTING_PROMPT_PATH.read_text(encoding="utf-8")


def _build_prompt(problem_statement: str, code: str) -> str:
    template = _load_prompt_template()
    return template.format(problem=problem_statement, code=code)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _extract_code_block(text: str) -> str:
    """Strip markdown fences if the model added them despite instructions."""
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def generate_tests(problem_statement: str, code: str) -> str:
    prompt = _build_prompt(problem_statement, code)
    response = _client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.2,
    )
    raw_text = response.choices[0].message.content
    test_code = _extract_code_block(raw_text)
    if "import pytest" not in test_code:
        test_code = "import pytest\n" + test_code
    return test_code


# ---------------------------------------------------------------------------
# Test execution (sandboxed-ish via subprocess + temp dir + timeout)
# ---------------------------------------------------------------------------

def run_tests(code: str, test_code: str) -> dict:
    """
    Writes `code` to solution.py and `test_code` to test_solution.py inside a
    temp directory, then runs pytest against them in a subprocess.

    Returns:
        {
            "all_passed": bool,
            "passed_count": int,
            "failed_count": int,
            "failures": str,      # human-readable failure details for the coding agent
            "raw_output": str,    # full pytest stdout+stderr
            "error": str | None,  # set if something crashed outside of normal test failures
        }
    """
    tmp_dir = tempfile.mkdtemp(prefix="agentic_test_")
    try:
        solution_path = Path(tmp_dir) / "solution.py"
        test_path = Path(tmp_dir) / "test_solution.py"

        solution_path.write_text(code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "all_passed": False,
                "passed_count": 0,
                "failed_count": 0,
                "failed_tests": [],
                "failures": "Test run timed out — possible infinite loop in candidate code.",
                "raw_output": "",
                "error": "timeout",
            }

        output = result.stdout + "\n" + result.stderr
        passed_count, failed_count = _parse_pytest_summary(output)
        all_passed = result.returncode == 0

        failed_tests = []
        if not all_passed:
            failed_tests = _extract_failed_tests(output)
            if not failed_tests:
                # Parser couldn't find a structured block — dump raw output
                # so the coding agent still gets a real signal instead of nothing.
                failed_tests = [{
                    "name": "collection_or_unknown_error",
                    "detail": output.strip() or "pytest exited non-zero with no captured output.",
                }]

        return {
            "all_passed": all_passed,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "failed_tests": failed_tests,          # structured: [{"name":..., "detail":...}, ...]
            "failures": _format_failures_for_feedback(failed_tests),  # human-readable string for the coding agent
            "raw_output": output,
            "error": None,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _parse_pytest_summary(output: str) -> tuple[int, int]:
    passed = 0
    failed = 0
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) error", output)
    if passed_match:
        passed = int(passed_match.group(1))
    if failed_match:
        failed = int(failed_match.group(1))
    if error_match:
        # Collection errors (bad imports, syntax errors, etc.) count as failures too
        failed += int(error_match.group(1))
    return passed, failed


def _extract_failed_tests(output: str) -> list[dict]:
    """
    Parses pytest's "FAILURES" and/or "ERRORS" sections into individual
    failing tests. Collection errors (e.g. ImportError from a bad test file)
    show up under "ERRORS", not "FAILURES" — both must be checked.
    """
    failed_tests = []
    for header in ("ERRORS", "FAILURES"):
        if header not in output:
            continue
        section = output.split(header, 1)[1]
        section = section.split("short test summary info", 1)[0]
        blocks = re.split(r"_{5,}\s+(.*?)\s+_{5,}", section)
        for i in range(1, len(blocks) - 1, 2):
            name = blocks[i].strip()
            detail = blocks[i + 1].strip()
            failed_tests.append({"name": name, "detail": detail})

    return failed_tests


def _format_failures_for_feedback(failed_tests: list[dict]) -> str:
    """
    Turns the structured failed-tests list into a readable block of text
    the coding agent can use to understand exactly what to fix.
    """
    if not failed_tests:
        return ""

    parts = []
    for i, test in enumerate(failed_tests, start=1):
        parts.append(f"{i}. Test: {test['name']}\n   Details:\n   {test['detail']}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# High-level entry point used by main.py
# ---------------------------------------------------------------------------

def test_candidate(problem_statement: str, code: str) -> dict:
    """Generate tests, run them, and return results in one call."""
    test_code = generate_tests(problem_statement, code)
    results = run_tests(code, test_code)
    results["generated_test_code"] = test_code
    return results


if __name__ == "__main__":
    # quick manual smoke test
    sample_problem = "Write a function `add(a, b)` that returns the sum of two numbers."
    sample_code = "def add(a, b):\n    return a + b\n"
    results = test_candidate(sample_problem, sample_code)
    print(results["raw_output"])
    print("ALL PASSED:", results["all_passed"])