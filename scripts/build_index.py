#!/usr/bin/env python3
"""
Function Index Builder - 构建函数索引

用法:
    python scripts/build_index.py [--output=<path>]
    
生成 functions/_index.json 包含:
- 所有函数的 FQN 和路径映射
- 短名到 FQN 列表的映射 (用于冲突检测)
- 每个函数的依赖关系
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# 项目根目录
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
FUNCTIONS_DIR = PROJECT_ROOT / "functions"


def scan_functions() -> dict:
    """扫描所有函数定义文件"""
    functions = {}
    by_short_name = defaultdict(list)
    
    for json_file in FUNCTIONS_DIR.rglob("*.json"):
        # 跳过特殊文件
        if json_file.name.startswith("_"):
            continue
        
        try:
            rel_path = json_file.relative_to(FUNCTIONS_DIR)
            # FQN = 相对路径去掉 .json
            fqn = str(rel_path.with_suffix('')).replace('\\', '/')
            short_name = json_file.stem
            
            # 读取函数定义
            with open(json_file, 'r', encoding='utf-8') as f:
                fn_def = json.load(f)
            
            # 提取调用依赖
            calls = extract_calls(fn_def)
            
            functions[fqn] = {
                "path": str(rel_path).replace('\\', '/'),
                "fqn": fqn,
                "name": fn_def.get("name", short_name),
                "description": fn_def.get("description", ""),
                "params": fn_def.get("params", []),
                "calls": calls
            }
            
            by_short_name[short_name].append(fqn)
            
        except Exception as e:
            print(f"Warning: Failed to parse {json_file}: {e}", file=sys.stderr)
    
    return functions, dict(by_short_name)


def extract_calls(fn_def: dict) -> list:
    """提取函数定义中的所有调用引用"""
    calls = []
    
    on_complete = fn_def.get("on_complete", {})
    if not on_complete:
        return calls
    
    # 直接调用
    if "target" in on_complete:
        calls.append(on_complete["target"])
    
    # switch 条件分支
    for cond in on_complete.get("conditions", []):
        if "call" in cond:
            calls.append(cond["call"])
        if "tail_call" in cond:
            calls.append(cond["tail_call"])
    
    # default
    if "default" in on_complete and on_complete["default"] != "_return":
        calls.append(on_complete["default"])
    
    # sequence steps
    for step in on_complete.get("steps", []):
        if "call" in step:
            calls.append(step["call"])
        if "tail_call" in step:
            calls.append(step["tail_call"])
    
    # loop do (只允许 tail_call)
    do_block = on_complete.get("do", {})
    if "tail_call" in do_block:
        calls.append(do_block["tail_call"])
    
    # 过滤内置函数
    calls = [c for c in calls if c and c != "_return"]
    
    return list(set(calls))


def build_index(output_path: str = None):
    """构建完整索引"""
    functions, by_short_name = scan_functions()
    
    index = {
        "_generated": datetime.now().isoformat(),
        "_version": "1.0",
        "functions": functions,
        "by_short_name": by_short_name,
        "stats": {
            "total_functions": len(functions),
            "namespaces": list(set(
                '/'.join(fqn.split('/')[:-1]) 
                for fqn in functions.keys() 
                if '/' in fqn
            )),
            "conflicts": {
                name: fqns 
                for name, fqns in by_short_name.items() 
                if len(fqns) > 1
            }
        }
    }
    
    if output_path is None:
        output_path = FUNCTIONS_DIR / "_index.json"
    else:
        output_path = Path(output_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"Index built: {output_path}")
    print(f"  Total functions: {index['stats']['total_functions']}")
    print(f"  Namespaces: {', '.join(index['stats']['namespaces']) or '(root only)'}")
    
    if index['stats']['conflicts']:
        print(f"  Conflicts detected:")
        for name, fqns in index['stats']['conflicts'].items():
            print(f"    - {name}: {', '.join(fqns)}")
    
    return index


def main():
    output_path = None
    
    for arg in sys.argv[1:]:
        if arg.startswith("--output="):
            output_path = arg.split("=", 1)[1]
    
    build_index(output_path)


if __name__ == "__main__":
    main()
