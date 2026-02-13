#!/usr/bin/env python3
"""
Function Executor - 交互式函数执行器

基于 AI 语义理解交互模式框架，实现函数调用栈的控制流管理。
确定性逻辑 100% 脚本化，AI 仅负责语义评估（当 safe_eval 失败时兜底）。

用法：
    # 启动函数执行
    python scripts/fn_execute.py start <function> [arg1=val1 ...]
    
    # 继续执行（task 完成后）
    python scripts/fn_execute.py continue task_result="..."

输出格式：
    [TASK] - 需要主会话执行的任务
    [EVAL] - 需要 AI 语义评估
    [COMPLETE] - 执行完成

与 interactive_wrapper.py 配合使用实现交互式执行。
"""

import os
import sys
import json
import subprocess
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# 路径配置
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
FUNCTIONS_DIR = PROJECT_ROOT / "functions"

# 导入 safe_eval
sys.path.insert(0, str(SCRIPT_DIR))
from safe_eval import safe_eval, try_eval, SafeEvalError


# ============================================================================
# 工具函数
# ============================================================================

def get_session_id() -> str:
    """获取会话 ID"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "get_session_id.py")],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "default"


def call_stack_ops(session_id: str, op: str, *args) -> Tuple[int, str, str]:
    """调用 stack_ops.py"""
    cmd = [sys.executable, str(SCRIPT_DIR / "stack_ops.py"), session_id, op] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def call_resolve_fn(target: str, caller_fqn: str = "") -> Dict[str, Any]:
    """调用 resolve_fn.py 解析函数名"""
    cmd = [sys.executable, str(SCRIPT_DIR / "resolve_fn.py"), target]
    if caller_fqn:
        cmd.append(f"--caller={caller_fqn}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON from resolve_fn"}
    return {"success": False, "error": result.stderr}


def read_function(fqn: str) -> Optional[Dict[str, Any]]:
    """读取函数定义"""
    # 内置函数
    if fqn.startswith("_"):
        return {"name": fqn, "builtin": True}
    
    # 构建路径
    fn_path = FUNCTIONS_DIR / f"{fqn}.json"
    if not fn_path.exists():
        return None
    
    try:
        with open(fn_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_state(session_id: str) -> Dict[str, Any]:
    """加载状态"""
    state_file = SCRIPT_DIR / "states" / session_id / "state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"status": "idle", "stack": [], "output": None}


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    """保存状态"""
    state_dir = SCRIPT_DIR / "states" / session_id
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ============================================================================
# 变量替换
# ============================================================================

def substitute_value(value: Any) -> str:
    """将值转换为表达式中可用的字符串（保持类型）"""
    if value is None:
        return "None"
    elif isinstance(value, bool):
        return "True" if value else "False"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        return json.dumps(value)  # 加引号并转义
    else:
        return json.dumps(value, ensure_ascii=False)


def substitute_vars(expr: str, context: Dict[str, Any], prev: Any = None) -> str:
    """
    变量替换：将 $var 替换为对应的值
    
    支持：
    - $param_name - 参数值
    - $prev - 上一步返回值
    - $output - 当前输出
    """
    if not expr or not isinstance(expr, str):
        return expr
    
    result = expr
    
    # 替换 $prev
    if prev is not None and "$prev" in result:
        result = result.replace("$prev", substitute_value(prev))
    
    # 替换 $param_name
    for key, value in context.items():
        pattern = f"${key}"
        if pattern in result:
            result = result.replace(pattern, substitute_value(value))
    
    return result


def substitute_args(args: Dict[str, Any], context: Dict[str, Any], prev: Any = None) -> Dict[str, Any]:
    """替换参数字典中的变量"""
    if not args:
        return {}
    
    result = {}
    for key, value in args.items():
        if isinstance(value, str):
            # 先替换变量
            substituted = substitute_vars(value, context, prev)
            # 尝试评估（支持 $n - 1 这种表达式）
            eval_result = try_eval(substituted)
            if eval_result is not None:
                result[key] = eval_result
            else:
                # eval 失败，保持原值（可能是语义表达式）
                result[key] = substituted
        else:
            result[key] = value
    return result


# ============================================================================
# 控制流处理器
# ============================================================================

class Executor:
    """函数执行器"""
    
    # 默认阈值：达到此次数后建议启动新子代理
    DEFAULT_MAX_RESUME = 5
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = load_state(session_id)
        self.max_ai_retries = 3
        self.ai_retry_count = 0
        
        # 初始化 controller 状态
        if "controller" not in self.state:
            self.state["controller"] = {
                "resume_count": 0,
                "max_resume_before_refresh": self.DEFAULT_MAX_RESUME
            }
    
    def save(self):
        """保存状态"""
        save_state(self.session_id, self.state)
    
    def increment_resume_count(self) -> bool:
        """
        增加 resume 计数，返回是否建议下次复用
        
        Returns:
            resume_next: True 表示下次应复用当前子代理，False 表示应启动新子代理
        """
        controller = self.state.get("controller", {})
        controller["resume_count"] = controller.get("resume_count", 0) + 1
        max_resume = controller.get("max_resume_before_refresh", self.DEFAULT_MAX_RESUME)
        
        resume_next = controller["resume_count"] < max_resume
        
        if not resume_next:
            # 达到阈值，重置计数器（下次新实例从 0 开始）
            controller["resume_count"] = 0
        
        self.state["controller"] = controller
        return resume_next
    
    def get_stack(self) -> List[Dict]:
        """获取栈"""
        return self.state.get("stack", [])
    
    def get_top_frame(self) -> Optional[Dict]:
        """获取栈顶帧"""
        stack = self.get_stack()
        return stack[-1] if stack else None
    
    def push_frame(self, fqn: str, args: Dict[str, Any]) -> None:
        """压栈"""
        frame = {
            "function": fqn,
            "args": args,
            "step_index": 0
        }
        self.state.setdefault("stack", []).append(frame)
        self.state["status"] = "running"
    
    def pop_frame(self) -> Optional[Dict]:
        """弹栈"""
        stack = self.get_stack()
        if stack:
            return stack.pop()
        return None
    
    def update_frame(self, **updates) -> None:
        """更新栈顶帧"""
        frame = self.get_top_frame()
        if frame:
            frame.update(updates)
    
    def tail_call(self, fqn: str, args: Dict[str, Any]) -> None:
        """尾调用（替换栈顶）"""
        stack = self.get_stack()
        if stack:
            stack[-1] = {
                "function": fqn,
                "args": args,
                "step_index": 0
            }
        else:
            self.push_frame(fqn, args)
    
    def set_prev(self, value: Any) -> None:
        """设置 $prev"""
        frame = self.get_top_frame()
        if frame:
            frame["prev"] = value
    
    # ========================================================================
    # 主入口
    # ========================================================================
    
    def handle_start(self, function: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理 start 指令"""
        # start 命令开始新的执行，清空旧状态
        self.state["stack"] = []
        self.state["status"] = "idle"
        self.state["output"] = None
        
        # 解析函数
        resolved = call_resolve_fn(function)
        if not resolved.get("success"):
            return {"action": "error", "error": resolved.get("error", "Failed to resolve function")}
        
        fqn = resolved["fqn"]
        
        # 读取函数定义
        fn_def = read_function(fqn)
        if not fn_def:
            return {"action": "error", "error": f"Function not found: {fqn}"}
        
        # 内置函数
        if fn_def.get("builtin"):
            return self._handle_builtin(fqn, args)
        
        # 检查 loop 前置条件
        on_complete = fn_def.get("on_complete", {})
        if on_complete.get("type") == "loop":
            while_cond = on_complete.get("while", "")
            if while_cond:
                substituted = substitute_vars(while_cond, args)
                result = try_eval(substituted)
                if result is False:
                    # 循环条件一开始就不满足，直接返回
                    return {"action": "complete", "result": None}
                elif result is None:
                    # 需要 AI 评估
                    return self._request_ai_eval(
                        f"条件：{substituted}\n\n请回答 true 或 false",
                        "loop_while_initial",
                        {"function": function, "args": args, "phase": "start_loop_check"}
                    )
        
        # 压栈
        self.push_frame(fqn, args)
        self.save()
        
        # 返回 task
        return self._output_task(fn_def, args)
    
    def handle_continue(self, task_result: str = None) -> Dict[str, Any]:
        """处理 continue 指令"""
        frame = self.get_top_frame()
        if not frame:
            return {"action": "complete", "result": self.state.get("output")}
        
        fqn = frame["function"]
        args = frame.get("args", {})
        prev = frame.get("prev")
        
        # 读取函数定义
        fn_def = read_function(fqn)
        if not fn_def:
            return {"action": "error", "error": f"Function not found: {fqn}"}
        
        on_complete = fn_def.get("on_complete", {"type": "return"})
        oc_type = on_complete.get("type", "return")
        
        # 检查 has_prev（子函数刚返回）
        if frame.get("has_prev"):
            # 清除标志
            frame["has_prev"] = False
            self.save()
            
            # 检查是否有 triggers 隐式 sequence 在执行
            if frame.get("triggers_steps"):
                return self._handle_triggers_next(args, prev)
            elif oc_type == "sequence":
                # sequence：继续下一步
                return self._handle_sequence(on_complete, args, prev)
            else:
                # switch/call/其他：子函数返回后，执行隐式 return
                return self._handle_return({"type": "return"}, args, prev)
        
        # 正常处理 on_complete
        return self._route_on_complete(on_complete, args, prev, task_result)
    
    # ========================================================================
    # on_complete 路由
    # ========================================================================
    
    def _route_on_complete(self, on_complete: Dict, args: Dict, prev: Any, task_result: str = None) -> Dict[str, Any]:
        """路由 on_complete 处理"""
        oc_type = on_complete.get("type", "return")
        
        if oc_type == "return":
            return self._handle_return(on_complete, args, prev)
        elif oc_type == "call":
            return self._handle_call(on_complete, args, prev)
        elif oc_type == "tail_call":
            return self._handle_tail_call(on_complete, args, prev)
        elif oc_type == "switch":
            return self._handle_switch(on_complete, args, prev)
        elif oc_type == "sequence":
            return self._handle_sequence(on_complete, args, prev)
        elif oc_type == "loop":
            return self._handle_loop(on_complete, args, prev)
        elif oc_type == "triggers":
            return self._handle_triggers(on_complete, args, prev)
        else:
            return {"action": "error", "error": f"Unknown on_complete type: {oc_type}"}
    
    def _handle_return(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 return"""
        value = on_complete.get("value")
        if value is not None and isinstance(value, str):
            # 字符串值需要变量替换和求值
            value = substitute_vars(value, args, prev)
            eval_result = try_eval(value)
            # eval_result 可能是 False/0/空字符串等 falsy 值，需要区分 None
            if eval_result is not None:
                value = eval_result
        
        # 弹栈
        self.pop_frame()
        
        # 检查是否还有父帧
        parent_frame = self.get_top_frame()
        if parent_frame:
            # 设置 prev
            self.set_prev(value)
            parent_frame["has_prev"] = True
            self.save()
            # 继续处理父帧
            return self.handle_continue()
        else:
            # 栈空，完成
            self.state["status"] = "idle"
            self.state["output"] = value
            self.save()
            return {"action": "complete", "result": value}
    
    def _handle_call(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 call"""
        target = on_complete.get("target") or on_complete.get("call")
        if not target:
            return {"action": "error", "error": "call: missing target"}
        
        # 获取当前帧 FQN 用于相对路径解析
        current_frame = self.get_top_frame()
        caller_fqn = current_frame["function"] if current_frame else ""
        
        # 解析目标函数
        resolved = call_resolve_fn(target, caller_fqn)
        if not resolved.get("success"):
            return {"action": "error", "error": resolved.get("error")}
        
        target_fqn = resolved["fqn"]
        
        # 内置函数
        if target_fqn.startswith("_"):
            return self._handle_builtin(target_fqn, on_complete.get("args", {}))
        
        # 替换参数
        call_args = substitute_args(on_complete.get("args", {}), args, prev)
        
        # 读取目标函数
        fn_def = read_function(target_fqn)
        if not fn_def:
            return {"action": "error", "error": f"Function not found: {target_fqn}"}
        
        # 压栈
        self.push_frame(target_fqn, call_args)
        self.save()
        
        # 返回 task
        return self._output_task(fn_def, call_args)
    
    def _handle_tail_call(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 tail_call"""
        target = on_complete.get("target") or on_complete.get("tail_call")
        if not target:
            return {"action": "error", "error": "tail_call: missing target"}
        
        # 获取当前帧 FQN
        current_frame = self.get_top_frame()
        caller_fqn = current_frame["function"] if current_frame else ""
        
        # 解析目标函数
        resolved = call_resolve_fn(target, caller_fqn)
        if not resolved.get("success"):
            return {"action": "error", "error": resolved.get("error")}
        
        target_fqn = resolved["fqn"]
        
        # 内置函数
        if target_fqn.startswith("_"):
            return self._handle_builtin(target_fqn, on_complete.get("args", {}))
        
        # 替换参数
        call_args = substitute_args(on_complete.get("args", {}), args, prev)
        
        # 读取目标函数
        fn_def = read_function(target_fqn)
        if not fn_def:
            return {"action": "error", "error": f"Function not found: {target_fqn}"}
        
        # 尾调用（替换栈顶）
        self.tail_call(target_fqn, call_args)
        self.save()
        
        # 返回 task
        return self._output_task(fn_def, call_args)
    
    def _handle_switch(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 switch（DFA 单分支）"""
        cases = on_complete.get("cases", [])
        
        # 逐个评估 case 条件
        pending_evals = []
        for i, case_item in enumerate(cases):
            if "default" in case_item:
                continue  # default 最后处理
            
            condition = case_item.get("case", "")
            substituted = substitute_vars(condition, args, prev)
            result = try_eval(substituted)
            
            if result is True:
                # 确定性命中，执行 then
                return self._execute_action(case_item.get("then", {}), args, prev)
            elif result is None:
                # eval 失败，记录待评估
                pending_evals.append((i, substituted, case_item))
        
        # 有待评估的条件，请求 AI 选择
        if pending_evals:
            question = "请根据以下情况选择分支：\n\n"
            question += f"当前状态：{json.dumps(args, ensure_ascii=False)}\n\n"
            question += "分支选项：\n"
            for idx, (i, cond, _) in enumerate(pending_evals):
                question += f"  {idx}: {cond}\n"
            question += f"  {len(pending_evals)}: 默认（无匹配）\n\n"
            question += "请回答分支编号（整数）"
            
            return self._request_ai_eval(
                question,
                "switch_branch",
                {"cases": cases, "pending": pending_evals, "args": args, "prev": prev}
            )
        
        # 无命中，执行 default
        default_action = on_complete.get("default", {"type": "return"})
        if isinstance(default_action, str):
            # 旧格式兼容：default 是函数名
            if default_action == "_return":
                default_action = {"type": "return"}
            else:
                default_action = {"call": default_action, "args": on_complete.get("default_args", {})}
        
        return self._execute_action(default_action, args, prev)
    
    def _handle_sequence(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 sequence"""
        steps = on_complete.get("steps", [])
        frame = self.get_top_frame()
        step_index = frame.get("step_index", 0)
        frame_prev = frame.get("prev", prev)
        
        if step_index >= len(steps):
            # sequence 完成，返回最后的 prev
            return self._handle_return({"value": frame_prev}, args, frame_prev)
        
        step = steps[step_index]
        
        # 更新 step_index
        self.update_frame(step_index=step_index + 1)
        self.save()
        
        # 执行当前步骤
        return self._execute_action(step, args, frame_prev)
    
    def _handle_loop(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 loop"""
        while_cond = on_complete.get("while", "")
        do_action = on_complete.get("do", {})
        
        # 计算新参数
        new_args = substitute_args(do_action.get("args", {}), args, prev)
        
        # 用新参数评估 while 条件
        substituted = substitute_vars(while_cond, new_args, prev)
        result = try_eval(substituted)
        
        if result is False:
            # 循环结束
            return self._handle_return({"type": "return"}, args, prev)
        elif result is None:
            # 需要 AI 评估
            return self._request_ai_eval(
                f"条件：{substituted}\n\n请回答 true 或 false",
                "loop_while",
                {"do_action": do_action, "new_args": new_args, "args": args, "prev": prev}
            )
        else:
            # result is True，继续循环
            return self._execute_action(
                {"tail_call": do_action.get("tail_call"), "args": new_args},
                args, prev
            )
    
    def _handle_triggers(self, on_complete: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 triggers（NFA 多分支语义：所有匹配的规则都执行）"""
        rules = on_complete.get("rules", [])
        on_none = on_complete.get("on_none", {"type": "return"})
        
        # 第一遍：评估所有条件
        eval_results = {}
        pending_evals = []
        
        for i, rule in enumerate(rules):
            condition = rule.get("when", "")
            substituted = substitute_vars(condition, args, prev)
            result = try_eval(substituted)
            
            if result is None:
                # eval 失败，需要 AI 评估
                pending_evals.append((i, substituted, rule))
            else:
                eval_results[i] = result
        
        # 有待评估的条件，请求 AI 批量评估
        if pending_evals:
            question = "请评估以下条件（可能有多个为 true）：\n\n"
            question += f"当前状态：{json.dumps(args, ensure_ascii=False)}\n\n"
            question += "条件列表：\n"
            for idx, (i, cond, _) in enumerate(pending_evals):
                question += f"  {idx}: {cond}\n"
            question += "\n请回答所有为 true 的条件编号，用逗号分隔（如：0,1）。如果都不为 true，请回答 none"
            
            return self._request_ai_eval(
                question,
                "triggers_batch",
                {"rules": rules, "pending": pending_evals, "eval_results": eval_results, 
                 "args": args, "prev": prev, "on_none": on_none}
            )
        
        # 收集所有匹配的规则索引（按定义顺序）
        matched_indices = sorted([i for i, r in eval_results.items() if r is True])
        
        if not matched_indices:
            # 无匹配，执行 on_none
            return self._execute_action(on_none, args, prev)
        
        # 脚本内部处理隐式 sequence（设计要点：triggers 的隐式 sequence 由脚本内部处理）
        # 将匹配的规则转换为 sequence 格式存储，然后像 sequence 一样处理
        matched_rules = [rules[i] for i in matched_indices]
        implicit_steps = [{"call": rule["do"].get("call"), 
                          "tail_call": rule["do"].get("tail_call"),
                          "args": rule["do"].get("args", {})} 
                         if "call" in rule["do"] or "tail_call" in rule["do"]
                         else rule["do"]
                         for rule in matched_rules]
        
        # 使用 triggers_sequence 标记来区分普通 sequence
        # 最后一个用 tail_call（如果原本不是 return），其他用 call
        if len(implicit_steps) == 1:
            # 只有一个匹配，直接执行
            return self._execute_action(matched_rules[0]["do"], args, prev)
        
        # 多个匹配，构建隐式 sequence 并处理
        # 保存当前帧的 triggers_steps 和 triggers_index
        frame = self.get_top_frame()
        frame["triggers_steps"] = implicit_steps
        frame["triggers_index"] = 0
        self.save()
        
        return self._handle_triggers_next(args, prev)
    
    def _handle_triggers_next(self, args: Dict, prev: Any) -> Dict[str, Any]:
        """处理 triggers 的下一个步骤"""
        frame = self.get_top_frame()
        steps = frame.get("triggers_steps", [])
        index = frame.get("triggers_index", 0)
        
        if index >= len(steps):
            # 所有触发器执行完毕
            del frame["triggers_steps"]
            del frame["triggers_index"]
            self.save()
            return self._handle_return({"type": "return"}, args, prev)
        
        step = steps[index]
        frame["triggers_index"] = index + 1
        self.save()
        
        return self._execute_action(step, args, prev)
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _execute_action(self, action: Dict, args: Dict, prev: Any) -> Dict[str, Any]:
        """执行动作（call/tail_call/return）"""
        if not action:
            return self._handle_return({}, args, prev)
        
        if action.get("type") == "return":
            return self._handle_return(action, args, prev)
        elif "call" in action:
            return self._handle_call({"target": action["call"], "args": action.get("args", {})}, args, prev)
        elif "tail_call" in action:
            return self._handle_tail_call({"target": action["tail_call"], "args": action.get("args", {})}, args, prev)
        else:
            return self._handle_return({}, args, prev)
    
    def _handle_builtin(self, name: str, args: Dict) -> Dict[str, Any]:
        """处理内置函数"""
        if name == "_return":
            self.pop_frame()
            parent = self.get_top_frame()
            if parent:
                self.set_prev(args.get("value"))
                parent["has_prev"] = True
                self.save()
                return self.handle_continue()
            else:
                self.state["status"] = "idle"
                self.state["output"] = args.get("value")
                self.save()
                return {"action": "complete", "result": args.get("value")}
        elif name == "_compact":
            return {"action": "compact", "message": "Context compaction requested"}
        elif name == "_clear":
            self.state = {"status": "idle", "stack": [], "output": None}
            self.save()
            return {"action": "complete", "result": None}
        else:
            return {"action": "error", "error": f"Unknown builtin: {name}"}
    
    def _output_task(self, fn_def: Dict, args: Dict) -> Dict[str, Any]:
        """输出 task"""
        task = fn_def.get("task", "")
        
        # 处理 task 对象格式
        if isinstance(task, dict):
            prompt = task.get("prompt", "")
            execute_in = task.get("execute_in", "main")
        else:
            prompt = str(task)
            execute_in = "main"
        
        # 替换变量
        prompt = substitute_vars(prompt, args)
        
        frame = self.get_top_frame()
        stack_depth = len(self.get_stack())
        
        return {
            "action": "task",
            "prompt": prompt,
            "execute_in": execute_in,
            "stack_depth": stack_depth,
            "function": frame["function"] if frame else ""
        }
    
    def _request_ai_eval(self, question: str, eval_type: str, context: Dict) -> Dict[str, Any]:
        """请求 AI 评估 - 交互式模式
        
        输出问题后挂起等待，由 interactive_wrapper.py 处理与 AI 的交互。
        """
        self.save()
        
        # 输出问题并挂起等待（由 interactive_wrapper.py 检测 <<CC_FN_INPUT_NEEDED>>）
        print(f"[EVAL] {question}")
        print("<<CC_FN_INPUT_NEEDED>>", flush=True)
        
        # 挂起等待 AI 答案（由 wrapper 从 agent_input.txt 读取后传入 stdin）
        retry_count = 0
        while retry_count < self.max_ai_retries:
            try:
                answer = input().strip()
            except EOFError:
                return {"action": "error", "error": "EOF while waiting for AI evaluation"}
            
            # 解析答案
            parsed = self._parse_eval_answer(answer, eval_type)
            if parsed is not None:
                # 答案有效，继续执行
                return self._continue_after_eval(parsed, context)
            
            # 答案无效，请求重试
            retry_count += 1
            if retry_count < self.max_ai_retries:
                print(f"[EVAL] 你上次回答了 '{answer}'，格式不正确。\n\n{question}")
                print("<<CC_FN_INPUT_NEEDED>>", flush=True)
        
        return {"action": "error", "error": f"Max retries ({self.max_ai_retries}) exceeded for evaluation"}
    
    def _parse_eval_answer(self, answer: str, eval_type: str) -> Any:
        """解析 AI 评估答案"""
        answer = answer.strip().lower()
        
        if eval_type in ("loop_while", "loop_while_initial"):
            if answer in ("true", "yes", "1"):
                return True
            elif answer in ("false", "no", "0"):
                return False
            return None
        
        elif eval_type == "switch_branch":
            try:
                return int(answer)
            except ValueError:
                return None
        
        return answer
    
    def _continue_after_eval(self, parsed: Any, context: Dict) -> Dict[str, Any]:
        """评估完成后继续执行"""
        eval_type = context.get("phase") or self.state.get("pending_eval", {}).get("type", "")
        
        if eval_type == "start_loop_check" or context.get("phase") == "start_loop_check":
            # loop 初始条件检查
            if parsed is False:
                return {"action": "complete", "result": None}
            else:
                # 继续 start 流程
                return self.handle_start(context["function"], context["args"])
        
        elif "do_action" in context:
            # loop while 评估
            if parsed is False:
                return self._handle_return({"type": "return"}, context["args"], context["prev"])
            else:
                do_action = context["do_action"]
                return self._execute_action(
                    {"tail_call": do_action.get("tail_call"), "args": context["new_args"]},
                    context["args"], context["prev"]
                )
        
        elif eval_type == "triggers_batch":
            # triggers 批量评估
            pending = context["pending"]
            eval_results = context.get("eval_results", {})
            rules = context["rules"]
            on_none = context.get("on_none", {"type": "return"})
            
            # parsed 是 AI 返回的匹配编号列表
            # 格式：逗号分隔的数字(如 "0,1")、单个数字、"none"、"all"
            matched_from_ai = set()
            if isinstance(parsed, str):
                parsed_lower = parsed.lower().strip()
                if not parsed_lower or parsed_lower == "none":
                    # 空字符串或 "none" 表示无匹配
                    pass
                elif parsed_lower == "all":
                    # "all" 表示全部匹配
                    for idx in range(len(pending)):
                        original_idx, _, _ = pending[idx]
                        matched_from_ai.add(original_idx)
                else:
                    # 逗号分隔的数字
                    for part in parsed.split(","):
                        part = part.strip()
                        if not part:
                            continue
                        try:
                            idx = int(part)
                            if 0 <= idx < len(pending):
                                original_idx, _, _ = pending[idx]
                                matched_from_ai.add(original_idx)
                        except ValueError:
                            # 非法格式静默忽略，继续处理其他部分
                            pass
            elif isinstance(parsed, int):
                if 0 <= parsed < len(pending):
                    original_idx, _, _ = pending[parsed]
                    matched_from_ai.add(original_idx)
            elif isinstance(parsed, list):
                for p in parsed:
                    if isinstance(p, int) and 0 <= p < len(pending):
                        original_idx, _, _ = pending[p]
                        matched_from_ai.add(original_idx)
            
            # 合并 eval_results 和 AI 评估结果
            all_matched = set(i for i, r in eval_results.items() if r is True)
            all_matched.update(matched_from_ai)
            
            matched_indices = sorted(list(all_matched))
            
            if not matched_indices:
                # 无匹配，执行 on_none
                return self._execute_action(on_none, context["args"], context["prev"])
            
            # 构建隐式 sequence
            matched_rules = [rules[i] for i in matched_indices]
            if len(matched_rules) == 1:
                return self._execute_action(matched_rules[0]["do"], context["args"], context["prev"])
            
            # 多个匹配，设置 triggers_steps
            implicit_steps = [rule["do"] for rule in matched_rules]
            frame = self.get_top_frame()
            frame["triggers_steps"] = implicit_steps
            frame["triggers_index"] = 0
            self.save()
            
            return self._handle_triggers_next(context["args"], context["prev"])
        
        elif "pending" in context:
            # switch 分支选择
            pending = context["pending"]
            if isinstance(parsed, int) and 0 <= parsed < len(pending):
                _, _, case_item = pending[parsed]
                return self._execute_action(case_item.get("then", {}), context["args"], context["prev"])
            else:
                # 选择 default
                cases = context["cases"]
                default_item = next((c for c in cases if "default" in c), None)
                if default_item:
                    return self._execute_action(default_item["default"], context["args"], context["prev"])
                return self._handle_return({}, context["args"], context["prev"])
        
        return {"action": "error", "error": "Unknown eval context"}


# ============================================================================
# 输出格式化
# ============================================================================

def format_output(result: Dict[str, Any], resume_next: bool = True) -> str:
    """格式化输出"""
    action = result.get("action")
    
    if action == "task":
        lines = ["[TASK]"]
        lines.append(f"prompt: {result.get('prompt', '')}")
        lines.append(f"execute_in: {result.get('execute_in', 'main')}")
        lines.append(f"stack_depth: {result.get('stack_depth', 0)}")
        lines.append(f"function: {result.get('function', '')}")
        lines.append(f"resume_next: {str(resume_next).lower()}")
        lines.append("")
        lines.append("Next: Call subagent fn-controller with continue, pass task_result.")
        return "\n".join(lines)
    
    elif action == "eval":
        lines = [f"[EVAL] {result.get('question', '')}"]
        lines.append("<<CC_FN_INPUT_NEEDED>>")
        return "\n".join(lines)
    
    elif action == "complete":
        lines = ["[COMPLETE]"]
        lines.append(f"result: {result.get('result', '')}")
        lines.append(f"resume_next: false")  # 完成后不需要复用
        return "\n".join(lines)
    
    elif action == "error":
        lines = ["[ERROR]"]
        lines.append(f"error: {result.get('error', '')}")
        return "\n".join(lines)
    
    elif action == "compact":
        return f"[COMPACT] {result.get('message', '')}"
    
    else:
        return json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================================
# 命令行入口
# ============================================================================

def parse_args(args: List[str]) -> Tuple[str, Dict[str, Any]]:
    """解析命令行参数"""
    if not args:
        return "", {}
    
    cmd = args[0]
    params = {}
    remaining = []
    
    for arg in args[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            # 类型推断
            if value.lower() == "true":
                params[key] = True
            elif value.lower() == "false":
                params[key] = False
            elif value.lstrip("-").isdigit():
                params[key] = int(value)
            elif value.replace(".", "", 1).lstrip("-").isdigit():
                params[key] = float(value)
            elif value.startswith('"') and value.endswith('"'):
                params[key] = value[1:-1]
            else:
                params[key] = value
        else:
            remaining.append(arg)
    
    # 第一个非 key=value 参数作为函数名（对于 start 命令）
    if remaining and cmd == "start":
        params["_function"] = remaining[0]
        remaining = remaining[1:]
    
    return cmd, params


def main():
    """主入口
    
    Note: 语义评估通过 interactive_wrapper.py 处理，脚本会挂起等待 AI 答案。
    """
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fn_execute.py start <function> [arg1=val1 ...]")
        print("  python fn_execute.py continue [task_result=...]")
        print("")
        print("For semantic evaluation, run via interactive_wrapper.py:")
        print("  python interactive_wrapper.py fn_execute.py start <function> [args...]")
        sys.exit(1)
    
    cmd, params = parse_args(sys.argv[1:])
    session_id = get_session_id()
    executor = Executor(session_id)
    
    if cmd == "start":
        function = params.pop("_function", None)
        if not function:
            print("[ERROR] Missing function name")
            sys.exit(1)
        result = executor.handle_start(function, params)
    
    elif cmd == "continue":
        task_result = params.get("task_result")
        result = executor.handle_continue(task_result)
    
    else:
        print(f"[ERROR] Unknown command: {cmd}")
        sys.exit(1)
    
    # 计算 resume_next（仅对 task 和 complete 有意义）
    resume_next = True
    action = result.get("action")
    if action in ("task", "complete"):
        resume_next = executor.increment_resume_count()
        executor.save()
    
    # 输出结果
    output = format_output(result, resume_next)
    print(output)
    
    # 根据结果设置退出码
    if action == "error":
        sys.exit(1)
    elif action == "eval":
        # eval 需要等待输入，由 wrapper 处理
        pass


if __name__ == "__main__":
    main()
