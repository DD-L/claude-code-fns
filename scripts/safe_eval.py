#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safe Expression Evaluator - 安全的表达式求值

支持：
- 算术运算: + - * / // %
- 比较运算: == != < > <= >=
- 逻辑运算: and or not
- 成员测试: in, not in
- 字面量: 数值、字符串、布尔值、列表、None/null

不支持（抛出异常，交给 AI 处理）：
- 函数调用
- 属性访问
- 未知变量名

用法：
    from safe_eval import safe_eval, try_eval
    
    # 直接求值（失败抛异常）
    result = safe_eval("5 + 3")  # 8
    result = safe_eval("'A' == 'A'")  # True
    
    # 尝试求值（失败返回 None）
    result = try_eval("$x + 1")  # None（未知变量）
"""

import ast
import operator
from typing import Any, Optional, Dict


# 支持的二元运算符
SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# 支持的比较运算符
SAFE_CMPOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 允许的名称（统一 null 处理）
SAFE_NAMES = {
    'True': True,
    'False': False,
    'true': True,   # JSON true → Python True
    'false': False, # JSON false → Python False
    'None': None,
    'null': None,   # JSON null → Python None
}


class SafeEvalError(Exception):
    """安全求值失败，需要 AI 介入"""
    pass


def _eval_node(node: ast.AST) -> Any:
    """递归求值 AST 节点"""
    
    # 字面量（数值、字符串等）
    if isinstance(node, ast.Constant):
        return node.value
    
    # 列表
    if isinstance(node, ast.List):
        return [_eval_node(el) for el in node.elts]
    
    # 元组
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(el) for el in node.elts)
    
    # 集合
    if isinstance(node, ast.Set):
        return {_eval_node(el) for el in node.elts}
    
    # 字典
    if isinstance(node, ast.Dict):
        keys = [_eval_node(k) if k is not None else None for k in node.keys]
        values = [_eval_node(v) for v in node.values]
        return dict(zip(keys, values))
    
    # 名称（True/False/None/null）
    if isinstance(node, ast.Name):
        if node.id in SAFE_NAMES:
            return SAFE_NAMES[node.id]
        raise SafeEvalError(f"Unknown name: {node.id}")
    
    # 一元运算符
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.Invert):
            return ~operand
        raise SafeEvalError(f"Unsupported unary op: {type(node.op).__name__}")
    
    # 二元运算符
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op_func = SAFE_BINOPS.get(type(node.op))
        if op_func:
            return op_func(left, right)
        raise SafeEvalError(f"Unsupported binary op: {type(node.op).__name__}")
    
    # 比较运算
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator)
            op_func = SAFE_CMPOPS.get(type(op))
            if not op_func:
                raise SafeEvalError(f"Unsupported compare op: {type(op).__name__}")
            if not op_func(left, right):
                return False
            left = right
        return True
    
    # 布尔运算（and/or）
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not _eval_node(value):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for value in node.values:
                if _eval_node(value):
                    return True
            return False
        raise SafeEvalError(f"Unsupported bool op: {type(node.op).__name__}")
    
    # 条件表达式 (a if cond else b)
    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test)
        if test:
            return _eval_node(node.body)
        else:
            return _eval_node(node.orelse)
    
    # 不支持的节点类型
    raise SafeEvalError(f"Unsupported expression: {type(node).__name__}")


def safe_eval(expr: str) -> Any:
    """
    安全的表达式求值
    
    支持：算术、比较、逻辑、成员测试、字面量、null/None
    不支持（抛出 SafeEvalError）：函数调用、属性访问、未知变量
    
    Args:
        expr: 表达式字符串
        
    Returns:
        求值结果
        
    Raises:
        SafeEvalError: 表达式不支持或求值失败
    """
    if not expr or not expr.strip():
        raise SafeEvalError("Empty expression")
    
    try:
        tree = ast.parse(expr.strip(), mode='eval')
        return _eval_node(tree.body)
    except SyntaxError as e:
        raise SafeEvalError(f"Syntax error: {e}")
    except SafeEvalError:
        raise
    except Exception as e:
        raise SafeEvalError(f"Evaluation error: {e}")


def try_eval(expr: str) -> Optional[Any]:
    """
    尝试求值表达式，失败返回 None
    
    用于条件判断：能 eval 就 eval，不能就交给 AI
    
    Args:
        expr: 表达式字符串
        
    Returns:
        成功时返回求值结果，失败时返回 None
    """
    try:
        return safe_eval(expr)
    except SafeEvalError:
        return None
    except Exception:
        return None


def try_eval_with_info(expr: str) -> Dict[str, Any]:
    """
    尝试求值表达式，返回详细信息
    
    Args:
        expr: 表达式字符串
        
    Returns:
        {
            "success": bool,
            "value": Any,  # 成功时的结果
            "error": str,  # 失败时的错误信息
            "needs_ai": bool  # 是否需要 AI 介入
        }
    """
    try:
        result = safe_eval(expr)
        return {
            "success": True,
            "value": result,
            "error": None,
            "needs_ai": False
        }
    except SafeEvalError as e:
        return {
            "success": False,
            "value": None,
            "error": str(e),
            "needs_ai": True
        }
    except Exception as e:
        return {
            "success": False,
            "value": None,
            "error": str(e),
            "needs_ai": True
        }


# 命令行接口
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python safe_eval.py <expression>")
        print("Example: python safe_eval.py \"5 + 3\"")
        sys.exit(1)
    
    expr = " ".join(sys.argv[1:])
    result = try_eval_with_info(expr)
    
    # 输出 JSON 格式结果
    print(json.dumps(result, ensure_ascii=False, default=str))
    
    sys.exit(0 if result["success"] else 1)
