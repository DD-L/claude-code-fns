#!/usr/bin/env python3
"""
Function Resolver - 静态函数分发解析器

用法:
    python scripts/resolve_fn.py <target_ref> [--caller=<caller_fqn>]
    
示例:
    python scripts/resolve_fn.py validate
    python scripts/resolve_fn.py validate --caller=tests/test_sequence
    python scripts/resolve_fn.py examples/validate
    python scripts/resolve_fn.py ./seq_step1 --caller=tests/test_sequence
    python scripts/resolve_fn.py ../route_a --caller=examples/pipeline

返回值:
    成功: 输出解析后的 FQN 和路径，exit 0
    失败: 输出错误信息，exit 1
"""

import os
import sys
import json
from pathlib import Path

# 项目根目录
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
FUNCTIONS_DIR = PROJECT_ROOT / "functions"


def normalize_path(path: str) -> str:
    """规范化路径，处理 .. 和 ."""
    parts = []
    for part in path.replace('\\', '/').split('/'):
        if part == '..':
            if parts:
                parts.pop()
        elif part and part != '.':
            parts.append(part)
    return '/'.join(parts)


def resolve_function(caller_fqn: str, target_ref: str) -> dict:
    """
    解析函数引用
    
    Args:
        caller_fqn: 调用者的全限定名 (e.g., "tests/test_sequence")
        target_ref: 目标函数引用 (e.g., "validate", "examples/validate", "./step1")
    
    Returns:
        dict: {
            "success": bool,
            "fqn": str,          # 解析后的全限定名
            "path": str,         # 文件路径
            "error": str         # 错误信息 (仅失败时)
        }
    """
    
    # 处理内置函数 (以 _ 开头)
    BUILTINS = {"_return", "_compact", "_clear"}
    if target_ref in BUILTINS:
        return {
            "success": True,
            "fqn": target_ref,
            "path": None,
            "builtin": True
        }
    
    # 获取调用者所在目录
    caller_dir = ""
    if caller_fqn and '/' in caller_fqn:
        caller_dir = '/'.join(caller_fqn.split('/')[:-1])
    elif caller_fqn:
        caller_dir = ""  # 调用者在根目录
    
    # 1. 显式相对路径 (./ 或 ../)
    if target_ref.startswith('./') or target_ref.startswith('../'):
        if caller_dir:
            resolved = normalize_path(caller_dir + '/' + target_ref)
        else:
            resolved = normalize_path(target_ref)
        
        path = FUNCTIONS_DIR / (resolved + ".json")
        if path.exists():
            return {
                "success": True,
                "fqn": resolved,
                "path": str(path.relative_to(PROJECT_ROOT))
            }
        else:
            return {
                "success": False,
                "error": f"Function not found: {target_ref} (resolved to {resolved}, from {caller_fqn or 'root'})"
            }
    
    # 2. 绝对路径 (包含 / 但不以 . 开头)
    if '/' in target_ref:
        path = FUNCTIONS_DIR / (target_ref + ".json")
        if path.exists():
            return {
                "success": True,
                "fqn": target_ref,
                "path": str(path.relative_to(PROJECT_ROOT))
            }
        else:
            return {
                "success": False,
                "error": f"Function not found: {target_ref} (absolute path)"
            }
    
    # 3. 短名就近查找 (向上冒泡)
    search_dirs = []
    current_dir = caller_dir
    
    # 构建搜索路径列表
    while current_dir:
        search_dirs.append(current_dir)
        if '/' in current_dir:
            current_dir = '/'.join(current_dir.split('/')[:-1])
        else:
            current_dir = ""
    search_dirs.append("")  # 添加根目录
    
    # 按顺序搜索
    for dir in search_dirs:
        if dir:
            fqn = f"{dir}/{target_ref}"
            path = FUNCTIONS_DIR / dir / (target_ref + ".json")
        else:
            fqn = target_ref
            path = FUNCTIONS_DIR / (target_ref + ".json")
        
        if path.exists():
            return {
                "success": True,
                "fqn": fqn,
                "path": str(path.relative_to(PROJECT_ROOT))
            }
    
    # 未找到
    search_path = " -> ".join([d if d else "(root)" for d in search_dirs])
    return {
        "success": False,
        "error": f"Function not found: {target_ref} (searched: {search_path})"
    }


def get_function_fqn_from_path(file_path: str) -> str:
    """从文件路径获取函数 FQN"""
    path = Path(file_path).resolve()
    try:
        rel = path.relative_to(FUNCTIONS_DIR)
        # 移除 .json 后缀
        fqn = str(rel.with_suffix('')).replace('\\', '/')
        return fqn
    except ValueError:
        return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    target_ref = sys.argv[1]
    caller_fqn = ""
    
    # 解析参数
    for arg in sys.argv[2:]:
        if arg.startswith("--caller="):
            caller_fqn = arg.split("=", 1)[1]
    
    result = resolve_function(caller_fqn, target_ref)
    
    # 输出 JSON 结果
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result["success"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
