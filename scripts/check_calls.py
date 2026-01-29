#!/usr/bin/env python3
"""
Function Call Checker - 静态验证所有函数调用

用法:
    python scripts/check_calls.py [--verbose]
    
功能:
- 扫描所有函数定义
- 验证每个 call/tail_call 引用是否能正确解析
- 验证 loop 约束（只能用 tail_call）
- 报告未找到的函数引用
"""

import sys
import json
from pathlib import Path

# 导入解析器
from resolve_fn import resolve_function, FUNCTIONS_DIR, PROJECT_ROOT
from build_index import scan_functions, extract_calls


def check_loop_constraint(fqn: str, fn_def: dict) -> list:
    """检查 loop 约束：do 只能用 tail_call"""
    errors = []
    on_complete = fn_def.get("on_complete", {})
    
    if on_complete.get("type") == "loop":
        do_block = on_complete.get("do", {})
        if "call" in do_block:
            errors.append(f"[CONSTRAINT] {fqn}: loop.do 只能用 tail_call，不能用 call")
        if "tail_call" not in do_block:
            errors.append(f"[CONSTRAINT] {fqn}: loop.do 必须有 tail_call")
    
    return errors


def check_all_calls(verbose: bool = False) -> tuple:
    """检查所有函数调用"""
    functions, _ = scan_functions()
    
    success_count = 0
    error_count = 0
    constraint_errors = []
    results = []
    
    for fqn, fn_info in sorted(functions.items()):
        # 读取完整函数定义以检查约束
        fn_path = FUNCTIONS_DIR / fn_info["path"]
        with open(fn_path, 'r', encoding='utf-8') as f:
            fn_def = json.load(f)
        
        # 检查 loop 约束
        constraint_errors.extend(check_loop_constraint(fqn, fn_def))
        
        # 检查调用解析
        calls = fn_info.get("calls", [])
        for target_ref in calls:
            result = resolve_function(fqn, target_ref)
            
            if result["success"]:
                success_count += 1
                if verbose:
                    resolved = result.get("fqn", "(builtin)")
                    results.append(f"[OK] {fqn} -> {target_ref} => {resolved}")
            else:
                error_count += 1
                results.append(f"[FAIL] {fqn} -> {target_ref} => NOT FOUND")
                results.append(f"       Error: {result['error']}")
    
    return success_count, error_count, constraint_errors, results


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    print("=" * 60)
    print("Function Call Static Checker")
    print("=" * 60)
    print()
    
    success, errors, constraint_errors, results = check_all_calls(verbose)
    
    # 打印约束错误
    if constraint_errors:
        print("Constraint Violations:")
        for err in constraint_errors:
            print(f"  {err}")
        print()
    
    # 打印解析结果
    for line in results:
        print(line)
    
    print()
    print("=" * 60)
    total_errors = errors + len(constraint_errors)
    print(f"Summary: {success} passed, {errors} resolve errors, {len(constraint_errors)} constraint errors")
    print("=" * 60)
    
    if total_errors > 0:
        print("\n[WARNING] Validation failed!")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All validations passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
