"""
main.py

Orchestrates the coding agent <-> testing agent feedback loop:
1. Coding agent writes a first draft of the solution.
2. Testing agent writes and runs tests against it.
3. If tests fail, the failure details are fed back to the coding agent,
   which revises the code.
4. Repeat until tests pass or max_rounds is reached.
"""

import sys

from agents.coding_agent import generate_code       
from agents.testing_agent import test_candidate      

MAX_ROUNDS = 3


def solve(problem_statement: str, max_rounds: int = MAX_ROUNDS) -> dict:
    """
    Runs the iterative code-generate -> test -> fix loop.

    Returns a dict with the final code, whether it passed, and the full
    round-by-round history (useful for logging/debugging).
    """
    history = []
    feedback = None
    final_code = None
    final_results = None

    for round_num in range(1, max_rounds + 1):
        print(f"\n=== Round {round_num} ===")

        print("Coding agent: generating code...")
        code = generate_code(problem_statement, feedback=feedback)
        final_code = code

        print("Testing agent: generating and running tests...")
        results = test_candidate(problem_statement, code)
        final_results = results

        history.append({
            "round": round_num,
            "code": code,
            "test_code": results.get("generated_test_code", ""),
            "passed": results["passed_count"],
            "failed": results["failed_count"],
            "failed_tests": results.get("failed_tests", []),
            "all_passed": results["all_passed"],
        })

        if results.get("error"):
            print(f"Testing agent hit an error: {results['error']}")

        print(f"Passed: {results['passed_count']} | Failed: {results['failed_count']}")
        for test in results.get("failed_tests", []):
            print(f"  ✗ {test['name']}")

        if results["all_passed"]:
            print("All tests passed! ✅")
            return {
                "success": True,
                "final_code": code,
                "rounds_taken": round_num,
                "history": history,
            }

        # Prepare feedback for the coding agent's next attempt
        feedback = results["failures"]
        print("Some tests failed. Sending feedback to coding agent...")

    print("\nMax rounds reached without all tests passing. ❌")
    return {
        "success": False,
        "final_code": final_code,
        "rounds_taken": max_rounds,
        "history": history,
        "last_failures": final_results["failures"] if final_results else None,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        problem = " ".join(sys.argv[1:])
    else:
        problem = input("Enter the problem statement: ").strip()

    outcome = solve(problem)

    print("\n=== FINAL RESULT ===")
    print(f"Success: {outcome['success']}")
    print(f"Rounds taken: {outcome['rounds_taken']}")
    print("\nFinal code:\n")
    print(outcome["final_code"])

    if not outcome["success"]:
        print("\nRemaining failures:\n")
        print(outcome.get("last_failures", "N/A"))

