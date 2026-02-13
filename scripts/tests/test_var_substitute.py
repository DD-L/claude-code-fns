#!/usr/bin/env python3
"""
Test Suite for variable substitution in fn_execute.py

Run: python scripts/tests/test_var_substitute.py
"""

import sys
from pathlib import Path

# 添加 scripts 目录到路径
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from fn_execute import substitute_value, substitute_vars, substitute_args

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

def test_substitute_value():
    """测试 substitute_value 函数"""
    test_section("substitute_value")
    
    # None
    test("None", substitute_value(None) == "None")
    
    # bool
    test("True", substitute_value(True) == "True")
    test("False", substitute_value(False) == "False")
    
    # 数值
    test("int", substitute_value(5) == "5")
    test("float", substitute_value(3.14) == "3.14")
    test("negative", substitute_value(-10) == "-10")
    
    # 字符串（加引号）
    result = substitute_value("hello")
    test("string", result == '"hello"', f"got {result}")
    
    # 带特殊字符的字符串
    result = substitute_value('say "hi"')
    test("string_escape", '"say \\"hi\\""' in result or result == '"say \\"hi\\""', f"got {result}")
    
    # 列表
    result = substitute_value([1, 2, 3])
    test("list", result == "[1, 2, 3]", f"got {result}")


def test_substitute_vars():
    """测试 substitute_vars 函数"""
    test_section("substitute_vars")
    
    context = {"count": 5, "max": 10, "name": "test"}
    
    # 简单替换
    result = substitute_vars("$count < $max", context)
    test("simple", result == "5 < 10", f"got {result}")
    
    # 字符串变量（带引号）
    result = substitute_vars("$name == 'test'", context)
    test("string_var", '"test"' in result, f"got {result}")
    
    # 算术表达式
    result = substitute_vars("$count + 1", context)
    test("arithmetic", result == "5 + 1", f"got {result}")
    
    # $prev
    result = substitute_vars("$prev is good", {}, prev="result")
    test("prev", '"result"' in result, f"got {result}")
    
    # 无变量
    result = substitute_vars("5 + 3", context)
    test("no_vars", result == "5 + 3", f"got {result}")
    
    # None 输入
    result = substitute_vars(None, context)
    test("none_input", result is None)
    
    # 空字符串
    result = substitute_vars("", context)
    test("empty_input", result == "")


def test_substitute_args():
    """测试 substitute_args 函数"""
    test_section("substitute_args")
    
    context = {"n": 5, "name": "test"}
    
    # 简单替换
    args = {"x": "$n - 1"}
    result = substitute_args(args, context)
    test("eval_arithmetic", result["x"] == 4, f"got {result}")
    
    # 直接值（非字符串）
    args = {"x": 10}
    result = substitute_args(args, context)
    test("direct_value", result["x"] == 10)
    
    # 多个参数
    args = {"a": "$n", "b": "$n + 1"}
    result = substitute_args(args, context)
    test("multi_a", result["a"] == 5)
    test("multi_b", result["b"] == 6)
    
    # 带 prev
    args = {"data": "$prev"}
    result = substitute_args(args, context, prev="previous")
    test("with_prev", result["data"] == "previous", f"got {result}")
    
    # 空参数
    result = substitute_args({}, context)
    test("empty", result == {})
    
    result = substitute_args(None, context)
    test("none", result == {})


def test_type_preservation():
    """测试类型保持"""
    test_section("Type Preservation")
    
    # 数值运算结果保持数值类型
    args = {"count": "$n + 1"}
    result = substitute_args(args, {"n": 5})
    test("int_result", isinstance(result["count"], int), f"got {type(result['count'])}")
    
    # 布尔值
    args = {"flag": "True"}
    result = substitute_args(args, {})
    test("bool_true", result["flag"] == True)
    
    args = {"flag": "False"}
    result = substitute_args(args, {})
    test("bool_false", result["flag"] == False)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  Variable Substitution Test Suite")
    print("="*60)
    
    test_substitute_value()
    test_substitute_vars()
    test_substitute_args()
    test_type_preservation()
    
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
