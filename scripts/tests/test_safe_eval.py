#!/usr/bin/env python3
"""
Test Suite for safe_eval.py

Run: python scripts/tests/test_safe_eval.py
Or:  python -m pytest scripts/tests/test_safe_eval.py -v
"""

import sys
from pathlib import Path

# 添加 scripts 目录到路径
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from safe_eval import safe_eval, try_eval, try_eval_with_info, SafeEvalError

# 统计
passed = 0
failed = 0
errors = []


def test(name: str, condition: bool, msg: str = ""):
    """测试断言"""
    global passed, failed, errors
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        error_msg = f"  [FAIL] {name}" + (f": {msg}" if msg else "")
        print(error_msg)
        errors.append(error_msg)


def test_section(name: str):
    """打印测试分组"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# ============== 测试用例 ==============

def test_arithmetic():
    """测试算术运算"""
    test_section("Arithmetic Operations")
    
    test("add", safe_eval("5 + 3") == 8)
    test("subtract", safe_eval("10 - 4") == 6)
    test("multiply", safe_eval("6 * 7") == 42)
    test("divide", safe_eval("20 / 4") == 5.0)
    test("floor_divide", safe_eval("7 // 2") == 3)
    test("modulo", safe_eval("17 % 5") == 2)
    test("power", safe_eval("2 ** 3") == 8)
    test("negative", safe_eval("-5") == -5)
    test("complex", safe_eval("(3 + 4) * 2") == 14)


def test_comparison():
    """测试比较运算"""
    test_section("Comparison Operations")
    
    test("eq_true", safe_eval("5 == 5") == True)
    test("eq_false", safe_eval("5 == 6") == False)
    test("ne_true", safe_eval("5 != 6") == True)
    test("lt_true", safe_eval("3 < 5") == True)
    test("lt_false", safe_eval("5 < 3") == False)
    test("le_true", safe_eval("5 <= 5") == True)
    test("gt_true", safe_eval("7 > 3") == True)
    test("ge_true", safe_eval("5 >= 5") == True)
    test("chain", safe_eval("1 < 2 < 3") == True)
    test("chain_false", safe_eval("1 < 3 < 2") == False)


def test_string():
    """测试字符串操作"""
    test_section("String Operations")
    
    test("eq_string", safe_eval("'A' == 'A'") == True)
    test("ne_string", safe_eval("'A' != 'B'") == True)
    test("double_quotes", safe_eval('"hello" == "hello"') == True)


def test_boolean():
    """测试布尔运算"""
    test_section("Boolean Operations")
    
    test("and_true", safe_eval("True and True") == True)
    test("and_false", safe_eval("True and False") == False)
    test("or_true", safe_eval("False or True") == True)
    test("or_false", safe_eval("False or False") == False)
    test("not_true", safe_eval("not False") == True)
    test("not_false", safe_eval("not True") == False)
    test("complex", safe_eval("True and (False or True)") == True)


def test_membership():
    """测试成员测试"""
    test_section("Membership Operations")
    
    test("in_list", safe_eval("3 in [1, 2, 3]") == True)
    test("not_in_list", safe_eval("4 not in [1, 2, 3]") == True)
    test("in_string", safe_eval("'a' in 'abc'") == True)


def test_null():
    """测试 null/None 处理"""
    test_section("Null Handling")
    
    test("None", safe_eval("None") == None)
    test("null", safe_eval("null") == None)
    test("eq_None", safe_eval("None == None") == True)
    test("eq_null", safe_eval("null == null") == True)
    test("None_eq_null", safe_eval("None == null") == True)


def test_literals():
    """测试字面量"""
    test_section("Literals")
    
    test("int", safe_eval("42") == 42)
    test("float", safe_eval("3.14") == 3.14)
    test("string", safe_eval("'hello'") == "hello")
    test("list", safe_eval("[1, 2, 3]") == [1, 2, 3])
    test("tuple", safe_eval("(1, 2)") == (1, 2))
    test("True", safe_eval("True") == True)
    test("False", safe_eval("False") == False)


def test_conditional():
    """测试条件表达式"""
    test_section("Conditional Expressions")
    
    test("if_true", safe_eval("1 if True else 2") == 1)
    test("if_false", safe_eval("1 if False else 2") == 2)
    test("nested", safe_eval("'a' if 1 > 0 else 'b'") == 'a')


def test_try_eval():
    """测试 try_eval 函数"""
    test_section("try_eval Function")
    
    test("success", try_eval("5 + 3") == 8)
    test("fail_returns_none", try_eval("unknown_var") is None)
    test("fail_semantic", try_eval("$result indicates success") is None)
    test("fail_chinese", try_eval("结果表示成功") is None)


def test_try_eval_with_info():
    """测试 try_eval_with_info 函数"""
    test_section("try_eval_with_info Function")
    
    result = try_eval_with_info("5 + 3")
    test("success_true", result["success"] == True)
    test("success_value", result["value"] == 8)
    test("success_no_error", result["error"] is None)
    test("success_no_ai", result["needs_ai"] == False)
    
    result = try_eval_with_info("unknown_var")
    test("fail_false", result["success"] == False)
    test("fail_value", result["value"] is None)
    test("fail_has_error", result["error"] is not None)
    test("fail_needs_ai", result["needs_ai"] == True)


def test_errors():
    """测试错误处理"""
    test_section("Error Handling")
    
    # 未知变量
    try:
        safe_eval("unknown_var")
        test("unknown_var_raises", False, "Should have raised SafeEvalError")
    except SafeEvalError:
        test("unknown_var_raises", True)
    
    # 函数调用
    try:
        safe_eval("len([1,2,3])")
        test("function_call_raises", False, "Should have raised SafeEvalError")
    except SafeEvalError:
        test("function_call_raises", True)
    
    # 语法错误
    try:
        safe_eval("5 +")
        test("syntax_error_raises", False, "Should have raised SafeEvalError")
    except SafeEvalError:
        test("syntax_error_raises", True)
    
    # 空表达式
    try:
        safe_eval("")
        test("empty_raises", False, "Should have raised SafeEvalError")
    except SafeEvalError:
        test("empty_raises", True)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  safe_eval.py Test Suite")
    print("="*60)
    
    test_arithmetic()
    test_comparison()
    test_string()
    test_boolean()
    test_membership()
    test_null()
    test_literals()
    test_conditional()
    test_try_eval()
    test_try_eval_with_info()
    test_errors()
    
    # 总结
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    if errors:
        print("\nFailed tests:")
        for err in errors:
            print(err)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
