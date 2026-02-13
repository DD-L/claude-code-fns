#!/usr/bin/env python3
"""
Run all test suites

Usage:
    python scripts/tests/run_all_tests.py
    
    # Or run individual tests:
    python scripts/tests/test_safe_eval.py
    python scripts/tests/test_var_substitute.py
    python scripts/tests/test_fn_execute.py
"""

import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

def run_test(test_file: str) -> bool:
    """运行单个测试文件"""
    print(f"\n{'#'*60}")
    print(f"# Running: {test_file}")
    print(f"{'#'*60}\n")
    
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / test_file)],
        cwd=SCRIPT_DIR.parent.parent
    )
    return result.returncode == 0


def main():
    """运行所有测试"""
    print("="*60)
    print("  CC_FUNCTION TEST SUITE")
    print("="*60)
    
    tests = [
        "test_safe_eval.py",
        "test_var_substitute.py",
        "test_fn_execute.py",
    ]
    
    results = {}
    for test in tests:
        results[test] = run_test(test)
    
    # 总结
    print("\n" + "="*60)
    print("  FINAL SUMMARY")
    print("="*60)
    
    all_passed = True
    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
