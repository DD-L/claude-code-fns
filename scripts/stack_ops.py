#!/usr/bin/env python3
"""
Stack Operations Tool - Reliable stack operations with diff feedback

================================================================================
                              OPERATIONS
================================================================================
  Operation     Arguments                              Description
--------------------------------------------------------------------------------
  push          <fqn> [--arg.k=v]... [--step_index=n]  Push new frame (alias: call)
  pop           [--output=<value>]                     Pop top frame
  tail_call     <fqn> [--arg.k=v]...                   Tail call (pop+push, depth unchanged)
  return        [<value>]                              Return (pop + set prev + output)
  update        [--step_index=n] [--prev=v] [--var.k=v] Update top frame properties
  peek                                                 View top frame
  show                                                 Show full state
  init                                                 Initialize/reset state
  clear                                                Clear stack and output
  set_status    idle|running|error                     Set status
  set_output    <value>                                Set session output
  set_agent_id  <agent_id>                             Set controller agent ID (for resume)
  set_var       [--var.k=v]...                         Batch set temp variables
  get_var       <key>                                  Read variable (args/prev/vars)
  del_var       <key>...                               Batch delete temp variables
  assert_empty                                         Assert stack is empty (exit 1 if not)
  get_next_action                                      Get stack state + suggested next action (JSON)
================================================================================

Usage:
    python scripts/stack_ops.py <operation> [options]        # auto-detect session
    python scripts/stack_ops.py <session_id> <operation>     # explicit session (for testing)

Session ID is auto-detected from $WT_SESSION environment variable.

Examples:
    python scripts/stack_ops.py show
    python scripts/stack_ops.py push route_a --arg.n=5 --arg.from=main
    python scripts/stack_ops.py tail_call route_b --arg.n=4
    python scripts/stack_ops.py return "completed"

Output:
    BEFORE/AFTER summary + detailed DIFF for reviewing operation results
"""

import os
import sys
import json
import copy
from pathlib import Path
from typing import Optional, Any, Dict, List

# 路径配置
SCRIPT_DIR = Path(__file__).parent.resolve()
STATES_DIR = SCRIPT_DIR / "states"

# 确保目录存在
STATES_DIR.mkdir(parents=True, exist_ok=True)


def parse_kv_args(args: list) -> tuple:
    """
    解析 --arg.key=value 格式的参数
    
    返回: (frame_args, remaining_args)
    """
    frame_args = {}
    remaining = []
    
    for arg in args:
        if arg.startswith("--arg."):
            # --arg.key=value 格式
            rest = arg[6:]  # 去掉 "--arg."
            if "=" in rest:
                key, value = rest.split("=", 1)
                # 尝试解析为数字或布尔值
                if value.lower() == "true":
                    frame_args[key] = True
                elif value.lower() == "false":
                    frame_args[key] = False
                elif value.lstrip("-").isdigit():
                    frame_args[key] = int(value)
                elif value.replace(".", "", 1).lstrip("-").isdigit():
                    frame_args[key] = float(value)
                else:
                    frame_args[key] = value
        else:
            remaining.append(arg)
    
    return frame_args, remaining


def get_state_file(session_id: str) -> Path:
    """获取状态文件路径: scripts/states/<session_id>/state.json"""
    session_dir = STATES_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "state.json"


def load_state(session_id: str, must_exist: bool = False) -> dict:
    """加载状态文件，不存在则返回空状态或报错"""
    state_file = get_state_file(session_id)
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"status": "idle", "stack": [], "output": None}
    
    if must_exist:
        print(f"\n[ERROR] Session file not found: {state_file}")
        print("Possible causes:")
        print("  1. Session ID typo (check your $SID variable)")
        print("  2. Session not initialized (run push first)")
        print("  3. Wrong terminal session")
        print("")
        print("Available sessions:")
        sessions = [d.name for d in STATES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if sessions:
            for s in sessions:
                print(f"  - {s}")
        else:
            print("  (none)")
        sys.exit(1)
    
    return {"status": "idle", "stack": [], "output": None}


def save_state(session_id: str, state: dict) -> None:
    """保存状态文件，包含读回验证"""
    from datetime import datetime
    
    state_file = get_state_file(session_id)
    
    # Expected stack length before save
    expected_len = len(state.get("stack", []))
    
    # Update last_updated timestamp (ISO8601 format)
    state["last_updated"] = datetime.now().isoformat()
    
    # Atomic write
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # Read-back verification
    try:
        with open(state_file, 'r', encoding='utf-8-sig') as f:
            verified = json.load(f)
        verified_len = len(verified.get("stack", []))
        if verified_len != expected_len:
            raise AssertionError(f"Stack length mismatch after save: expected {expected_len}, got {verified_len}")
    except Exception as e:
        print(f"[WARN] State verification failed: {e}", file=sys.stderr)


def format_stack_frame(frame: dict, index: int) -> str:
    """格式化单个栈帧"""
    fn = frame.get("function", "?")
    args = frame.get("args", {})
    step_idx = frame.get("step_index")
    prev = frame.get("prev")
    vars_dict = frame.get("vars", {})
    
    parts = [f"  [{index}] {fn}"]
    if args:
        args_str = ", ".join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in args.items())
        parts.append(f"args={{{args_str}}}")
    if step_idx is not None:
        parts.append(f"step={step_idx}")
    if prev is not None:
        prev_preview = str(prev)[:20]
        if len(str(prev)) > 20:
            prev_preview += "..."
        parts.append(f"prev={json.dumps(prev_preview, ensure_ascii=False)}")
    if vars_dict:
        vars_str = ", ".join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in vars_dict.items())
        parts.append(f"vars={{{vars_str}}}")
    
    return " ".join(parts)


def format_stack(stack: list) -> str:
    """格式化整个栈"""
    if not stack:
        return "  (empty)"
    lines = []
    for i, frame in enumerate(stack):
        lines.append(format_stack_frame(frame, i))
    return "\n".join(lines)


def format_state_summary(state: dict) -> str:
    """
    超紧凑摘要格式：一行显示核心信息
    格式: status=X depth=N top=<fn> [has_agent_id] [has_output]
    """
    status = state.get("status", "idle")
    stack = state.get("stack", [])
    output = state.get("output")
    agent_id = state.get("controller_agent_id")
    
    parts = [f"status={status}", f"depth={len(stack)}"]
    
    if stack:
        top_fn = stack[-1].get("function", "?")
        # 截断过长的函数名
        if len(top_fn) > 30:
            top_fn = "..." + top_fn[-27:]
        parts.append(f"top={top_fn}")
    
    if agent_id:
        parts.append("[has_agent_id]")
    if output is not None:
        parts.append("[has_output]")
    
    return " | ".join(parts)


def format_state_compact(state: dict, max_frames: int = 3) -> str:
    """
    紧凑格式化状态，限制显示的栈帧数量
    
    Args:
        state: 状态字典
        max_frames: 最多显示的栈帧数 (从栈顶开始)
    """
    status = state.get("status", "idle")
    stack = state.get("stack", [])
    output = state.get("output")
    
    lines = [f"status: {status}", f"stack: [{len(stack)}]"]
    
    if stack:
        # 只显示栈顶附近的帧
        if len(stack) <= max_frames:
            lines.append(format_stack(stack))
        else:
            # 显示省略信息和栈顶帧
            lines.append(f"  ... ({len(stack) - max_frames} frames omitted)")
            for i in range(len(stack) - max_frames, len(stack)):
                lines.append(format_stack_frame(stack[i], i))
    else:
        lines.append("  (empty)")
    
    if output is not None:
        output_preview = str(output)[:50]
        if len(str(output)) > 50:
            output_preview += "..."
        lines.append(f"output: {output_preview}")
    
    return "\n".join(lines)


def compute_diff(before: dict, after: dict) -> List[str]:
    """
    计算状态差异，返回 diff 行列表
    
    符号约定:
      +  新增
      -  删除
      ~  修改
      >  替换 (tail_call: 同位置函数变化)
    """
    diff_lines = []
    
    # 状态变化
    if before.get("status") != after.get("status"):
        diff_lines.append(f"  status: {before.get('status', 'idle')} -> {after.get('status', 'idle')}")
    
    # 栈变化
    before_stack = before.get("stack", [])
    after_stack = after.get("stack", [])
    
    len_before = len(before_stack)
    len_after = len(after_stack)
    
    if len_after > len_before:
        # 压栈
        for i in range(len_before, len_after):
            frame = after_stack[i]
            args_str = _format_args_brief(frame.get("args"))
            diff_lines.append(f"+ stack[{i}]: {frame.get('function', '?')}{args_str}")
    elif len_after < len_before:
        # 出栈
        for i in range(len_after, len_before):
            frame = before_stack[i]
            diff_lines.append(f"- stack[{i}]: {frame.get('function', '?')}")
    
    # 栈帧变化 (同位置)
    for i in range(min(len_before, len_after)):
        bf = before_stack[i]
        af = after_stack[i]
        
        # 函数替换 (tail_call)
        if bf.get("function") != af.get("function"):
            args_str = _format_args_brief(af.get("args"))
            diff_lines.append(f"> stack[{i}]: {bf.get('function')} -> {af.get('function')}{args_str}")
            continue  # 函数都换了，其它属性变化不必再报
        
        if bf.get("step_index") != af.get("step_index"):
            diff_lines.append(f"~ stack[{i}].step_index: {bf.get('step_index')} -> {af.get('step_index')}")
        
        if bf.get("args") != af.get("args"):
            diff_lines.append(f"~ stack[{i}].args: updated")
        
        if bf.get("output") != af.get("output"):
            diff_lines.append(f"~ stack[{i}].output: updated")
        
        # prev 字段变化
        if bf.get("prev") != af.get("prev"):
            if bf.get("prev") is None and af.get("prev") is not None:
                prev_preview = str(af.get("prev"))[:30]
                if len(str(af.get("prev"))) > 30:
                    prev_preview += "..."
                diff_lines.append(f"+ stack[{i}].prev: {prev_preview}")
            elif bf.get("prev") is not None and af.get("prev") is None:
                diff_lines.append(f"- stack[{i}].prev: cleared")
            else:
                diff_lines.append(f"~ stack[{i}].prev: updated")
        
        # vars 字段变化
        bf_vars = bf.get("vars", {})
        af_vars = af.get("vars", {})
        if bf_vars != af_vars:
            added = set(af_vars.keys()) - set(bf_vars.keys())
            removed = set(bf_vars.keys()) - set(af_vars.keys())
            changed = {k for k in bf_vars.keys() & af_vars.keys() if bf_vars[k] != af_vars[k]}
            
            for k in added:
                diff_lines.append(f"+ stack[{i}].vars.{k}: {af_vars[k]}")
            for k in removed:
                diff_lines.append(f"- stack[{i}].vars.{k}")
            for k in changed:
                diff_lines.append(f"~ stack[{i}].vars.{k}: {bf_vars[k]} -> {af_vars[k]}")
    
    # 输出变化
    if before.get("output") != after.get("output"):
        before_out = before.get("output")
        after_out = after.get("output")
        if before_out is None and after_out is not None:
            diff_lines.append(f"+ output: set")
        elif before_out is not None and after_out is None:
            diff_lines.append(f"- output: cleared")
        else:
            diff_lines.append(f"~ output: changed")
    
    # controller_agent_id 变化
    before_agent = before.get("controller_agent_id")
    after_agent = after.get("controller_agent_id")
    if before_agent != after_agent:
        if before_agent is None and after_agent is not None:
            agent_preview = after_agent[:20] + "..." if len(after_agent) > 20 else after_agent
            diff_lines.append(f"+ controller_agent_id: {agent_preview}")
        elif before_agent is not None and after_agent is None:
            diff_lines.append(f"- controller_agent_id: cleared")
        else:
            diff_lines.append(f"~ controller_agent_id: changed")
    
    return diff_lines


def _format_args_brief(args: dict) -> str:
    """简短格式化参数，用于 diff 显示"""
    if not args:
        return ""
    items = [f"{k}={v}" for k, v in args.items()]
    brief = ", ".join(items)
    if len(brief) > 40:
        brief = brief[:37] + "..."
    return f" ({brief})"


def print_operation_result(session_id: str, operation: str, before: dict, after: dict, error: str = None):
    """
    打印操作结果：紧凑摘要 + 详细 DIFF
    
    设计原则：
    - BEFORE/AFTER 只显示一行摘要，避免深栈刷屏
    - DIFF 详细显示所有变化，这是 Agent 审视的关键
    - 不输出时间戳（对执行可靠性无帮助）
    """
    print(f"\n[{operation.upper()}] session={session_id}")
    
    if error:
        print(f"[ERROR] {error}")
        print(f"STATE: {format_state_summary(before)}")
        return
    
    # 紧凑摘要
    print(f"BEFORE: {format_state_summary(before)}")
    print(f"AFTER:  {format_state_summary(after)}")
    
    # 详细 DIFF（核心信息）
    diff_lines = compute_diff(before, after)
    if diff_lines:
        print("DIFF:")
        for line in diff_lines:
            print(line)
    else:
        print("DIFF: (no changes)")
    
    print(f"[OK]")


# ============== 操作函数 ==============

def op_init(session_id: str, args: list) -> tuple:
    """初始化会话状态"""
    before = load_state(session_id)
    after = {"status": "idle", "stack": [], "output": None}
    save_state(session_id, after)
    return before, after, None


def validate_function_name(fqn: str) -> str:
    """验证函数名，返回错误信息或 None"""
    if fqn.startswith('-'):
        return f"Invalid function name '{fqn}': cannot start with '-' (likely argument format error)"
    if not fqn or fqn.isspace():
        return "Function name cannot be empty"
    return None


def op_push(session_id: str, args: list) -> tuple:
    """压栈操作"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <fqn>\nUsage: stack_ops.py {session_id} push <fqn> [--arg.k=v]"
    
    function_fqn = args[0]
    
    # 验证函数名
    if err := validate_function_name(function_fqn):
        before = load_state(session_id)
        return before, before, err
    frame_args = {}
    step_index = None
    
    # 先解析 --arg.key=value 格式
    kv_args, remaining = parse_kv_args(args[1:])
    frame_args.update(kv_args)
    
    # 解析其它参数
    for arg in remaining:
        if arg.startswith("--args="):
            try:
                json_args = json.loads(arg.split("=", 1)[1])
                frame_args.update(json_args)
            except json.JSONDecodeError as e:
                before = load_state(session_id)
                return before, before, f"Invalid JSON for args: {e}"
        elif arg.startswith("--step_index="):
            try:
                step_index = int(arg.split("=", 1)[1])
            except ValueError:
                before = load_state(session_id)
                return before, before, "step_index must be an integer"
    
    before = load_state(session_id)
    after = copy.deepcopy(before)
    
    # 创建新栈帧
    new_frame = {"function": function_fqn}
    if frame_args:
        new_frame["args"] = frame_args
    if step_index is not None:
        new_frame["step_index"] = step_index
    
    after["stack"].append(new_frame)
    after["status"] = "running"
    
    save_state(session_id, after)
    return before, after, None


def op_pop(session_id: str, args: list) -> tuple:
    """出栈操作"""
    before = load_state(session_id, must_exist=True)
    
    if not before.get("stack"):
        return before, before, "Cannot pop: stack is empty"
    
    after = copy.deepcopy(before)
    popped_frame = after["stack"].pop()
    
    # 解析可选参数
    frame_output = None
    for arg in args:
        if arg.startswith("--output="):
            frame_output = arg.split("=", 1)[1]
    
    # 如果提供了输出，追加到会话输出
    if frame_output:
        current_output = after.get("output") or ""
        if current_output:
            after["output"] = current_output + "\n" + frame_output
        else:
            after["output"] = frame_output
    
    # 栈空则变为 idle
    if not after["stack"]:
        after["status"] = "idle"
    
    save_state(session_id, after)
    return before, after, None


def op_peek(session_id: str, args: list) -> tuple:
    """查看栈顶"""
    state = load_state(session_id, must_exist=True)
    
    print(f"\n[PEEK] session={session_id}")
    print(f"STATE: {format_state_summary(state)}")
    
    if not state.get("stack"):
        print("TOP: (empty)")
    else:
        top_frame = state["stack"][-1]
        idx = len(state['stack']) - 1
        print(f"TOP[{idx}]: {top_frame.get('function', '?')}")
        if top_frame.get("args"):
            print(f"  args: {json.dumps(top_frame['args'], ensure_ascii=False)}")
        if top_frame.get("step_index") is not None:
            print(f"  step_index: {top_frame['step_index']}")
        if top_frame.get("prev") is not None:
            print(f"  prev: {json.dumps(top_frame['prev'], ensure_ascii=False)}")
        if top_frame.get("vars"):
            print(f"  vars: {json.dumps(top_frame['vars'], ensure_ascii=False)}")
    
    return None, None, None  # 特殊：不调用 print_operation_result


def op_update(session_id: str, args: list) -> tuple:
    """更新栈顶帧：支持 step_index, prev, output, args, vars
    
    step_index 更新规则（防止 sequence 跳步 bug）：
    - 必须连续递增：new_step_index == current_step_index + 1
    - 或者初始设置：current_step_index 不存在 且 new_step_index == 0
    - 使用 --force-step-index 可跳过验证（仅用于测试/恢复）
    """
    before = load_state(session_id, must_exist=True)
    
    if not before.get("stack"):
        return before, before, "Cannot update: stack is empty"
    
    after = copy.deepcopy(before)
    top_frame = after["stack"][-1]
    
    # 检查是否强制跳过 step_index 验证
    force_step_index = "--force-step-index" in args
    
    # 解析参数
    for arg in args:
        if arg.startswith("--step_index="):
            try:
                new_step_index = int(arg.split("=", 1)[1])
            except ValueError:
                return before, before, "step_index must be an integer"
            
            # step_index 连续性验证（防止 sequence 跳步 bug）
            current_step_index = top_frame.get("step_index")
            
            if not force_step_index:
                if current_step_index is None:
                    # First time setting step_index
                    if new_step_index != 0 and new_step_index != 1:
                        # Allow 0 (initial) or 1 (first update)
                        print(f"[WARN] step_index first set to {new_step_index}, expected 0 or 1", file=sys.stderr)
                else:
                    # Already has step_index, must increment continuously
                    expected = current_step_index + 1
                    if new_step_index != expected:
                        error_msg = (
                            f"step_index not continuous! current={current_step_index}, new={new_step_index}, expected={expected}\n"
                            f"This may cause sequence to skip steps!\n"
                            f"Use --force-step-index to bypass validation"
                        )
                        return before, before, error_msg
            
            top_frame["step_index"] = new_step_index
            
        elif arg.startswith("--prev="):
            top_frame["prev"] = arg.split("=", 1)[1]
        elif arg.startswith("--output="):
            top_frame["output"] = arg.split("=", 1)[1]
        elif arg.startswith("--args="):
            try:
                top_frame["args"] = json.loads(arg.split("=", 1)[1])
            except json.JSONDecodeError as e:
                return before, before, f"Invalid JSON for args: {e}"
        elif arg.startswith("--var."):
            # --var.key=value 格式：设置临时变量
            rest = arg[6:]  # 去掉 "--var."
            if "=" in rest:
                key, value = rest.split("=", 1)
                if "vars" not in top_frame:
                    top_frame["vars"] = {}
                top_frame["vars"][key] = _parse_value(value)
    
    save_state(session_id, after)
    return before, after, None


def op_set_status(session_id: str, args: list) -> tuple:
    """设置状态"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <idle|running|error>\nUsage: stack_ops.py {session_id} set_status idle"
    
    status = args[0]
    if status not in ("idle", "running", "error"):
        before = load_state(session_id)
        return before, before, f"Invalid status: {status}\nUsage: stack_ops.py {session_id} set_status <idle|running|error>"
    
    before = load_state(session_id)
    after = copy.deepcopy(before)
    after["status"] = status
    
    save_state(session_id, after)
    return before, after, None


def op_set_output(session_id: str, args: list) -> tuple:
    """设置会话输出"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <value>\nUsage: stack_ops.py {session_id} set_output \"your output\""
    
    output = " ".join(args)  # 支持空格
    
    before = load_state(session_id)
    after = copy.deepcopy(before)
    after["output"] = output
    
    save_state(session_id, after)
    return before, after, None


def op_set_agent_id(session_id: str, args: list) -> tuple:
    """设置 controller agent ID (用于 resume)"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <agent_id>\nUsage: stack_ops.py {session_id} set_agent_id \"agent-uuid\""
    
    agent_id = args[0]
    
    before = load_state(session_id)
    after = copy.deepcopy(before)
    after["controller_agent_id"] = agent_id
    
    save_state(session_id, after)
    return before, after, None


def op_clear(session_id: str, args: list) -> tuple:
    """清空栈，重置状态"""
    before = load_state(session_id)
    after = {"status": "idle", "stack": [], "output": None}
    save_state(session_id, after)
    return before, after, None


def op_show(session_id: str, args: list) -> tuple:
    """显示完整状态 (show 是唯一会显示完整栈的命令)"""
    state = load_state(session_id, must_exist=True)
    
    print(f"\n[SHOW] session={session_id}")
    print(f"file: {get_state_file(session_id)}")
    print(f"status: {state.get('status', 'idle')}")
    
    # 显示 controller_agent_id（如果存在）
    if state.get("controller_agent_id"):
        print(f"controller_agent_id: {state['controller_agent_id']}")
    
    # 显示栈
    stack = state.get("stack", [])
    print(f"stack: [{len(stack)}]")
    if stack:
        for i, frame in enumerate(stack):
            print(format_stack_frame(frame, i))
    else:
        print("  (empty)")
    
    if state.get("output"):
        print(f"\noutput:")
        print(state["output"])
    
    return None, None, None  # 特殊：不调用 print_operation_result


def op_tail_call(session_id: str, args: list) -> tuple:
    """尾调用：先 pop 再 push，栈深度不变"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <fqn>\nUsage: stack_ops.py {session_id} tail_call <fqn> [--arg.k=v]"
    
    # 解析新帧参数
    function_fqn = args[0]
    
    # 验证函数名
    if err := validate_function_name(function_fqn):
        before = load_state(session_id)
        return before, before, err
    
    before = load_state(session_id, must_exist=True)
    
    if not before.get("stack"):
        return before, before, "Cannot tail_call: stack is empty"
    
    after = copy.deepcopy(before)
    
    # 弹出当前帧
    after["stack"].pop()
    frame_args = {}
    step_index = None
    
    # 先解析 --arg.key=value 格式
    kv_args, remaining = parse_kv_args(args[1:])
    frame_args.update(kv_args)
    
    for arg in remaining:
        if arg.startswith("--args="):
            try:
                json_args = json.loads(arg.split("=", 1)[1])
                frame_args.update(json_args)
            except json.JSONDecodeError as e:
                return before, before, f"Invalid JSON for args: {e}"
        elif arg.startswith("--step_index="):
            try:
                step_index = int(arg.split("=", 1)[1])
            except ValueError:
                return before, before, "step_index must be an integer"
    
    # 创建新栈帧
    new_frame = {"function": function_fqn}
    if frame_args:
        new_frame["args"] = frame_args
    if step_index is not None:
        new_frame["step_index"] = step_index
    
    after["stack"].append(new_frame)
    # status 保持 running
    
    save_state(session_id, after)
    return before, after, None


def op_return(session_id: str, args: list) -> tuple:
    """返回操作：pop 当前栈帧，返回值写入父帧 prev + 会话输出"""
    before = load_state(session_id, must_exist=True)
    
    if not before.get("stack"):
        return before, before, "Cannot return: stack is empty"
    
    after = copy.deepcopy(before)
    popped_frame = after["stack"].pop()
    
    # 返回值
    return_value = " ".join(args) if args else None
    
    # 如果提供了返回值
    if return_value:
        # 1. 写入父帧的 prev 字段 (用于 sequence 中的 $prev 引用)
        if after["stack"]:
            after["stack"][-1]["prev"] = return_value
        
        # 2. 追加到会话输出
        current_output = after.get("output") or ""
        if current_output:
            after["output"] = current_output + "\n" + return_value
        else:
            after["output"] = return_value
    
    # 栈空则变为 idle
    if not after["stack"]:
        after["status"] = "idle"
    
    save_state(session_id, after)
    return before, after, None


def op_call(session_id: str, args: list) -> tuple:
    """调用操作：push 新栈帧 (call 是 push 的别名，语义更清晰)"""
    return op_push(session_id, args)


def _parse_value(value: str):
    """解析字符串值为合适的类型"""
    if value.lower() == "true":
        return True
    elif value.lower() == "false":
        return False
    elif value.lstrip("-").isdigit():
        return int(value)
    elif value.replace(".", "", 1).lstrip("-").isdigit():
        return float(value)
    else:
        return value


def op_set_var(session_id: str, args: list) -> tuple:
    """批量设置栈顶帧的临时变量 (支持 --var.k=v 格式)"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing --var.k=v\nUsage: stack_ops.py {session_id} set_var --var.x=1 --var.name=test"
    
    before = load_state(session_id, must_exist=True)
    
    if not before.get("stack"):
        return before, before, "Cannot set_var: stack is empty"
    
    # 解析 --var.key=value 格式
    vars_to_set = {}
    for arg in args:
        if arg.startswith("--var."):
            rest = arg[6:]  # 去掉 "--var."
            if "=" in rest:
                key, value = rest.split("=", 1)
                vars_to_set[key] = _parse_value(value)
        elif "=" in arg:
            # 也支持简单的 key=value 格式
            key, value = arg.split("=", 1)
            vars_to_set[key] = _parse_value(value)
    
    if not vars_to_set:
        return before, before, "No valid --var.key=value arguments provided"
    
    after = copy.deepcopy(before)
    top_frame = after["stack"][-1]
    
    # 初始化 vars 字典
    if "vars" not in top_frame:
        top_frame["vars"] = {}
    
    # 批量设置
    for key, value in vars_to_set.items():
        top_frame["vars"][key] = value
    
    save_state(session_id, after)
    return before, after, None


def op_get_var(session_id: str, args: list) -> tuple:
    """读取栈顶帧的变量 (优先级: vars > args > prev)"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <key>\nUsage: stack_ops.py {session_id} get_var <key>"
    
    state = load_state(session_id, must_exist=True)
    
    if not state.get("stack"):
        print(f"\n[GET_VAR] session={session_id}")
        print("[ERROR] Cannot get_var: stack is empty")
        return None, None, None
    
    top_frame = state["stack"][-1]
    key = args[0]
    
    # 查找顺序: vars > args > prev (特殊键)
    value = None
    source = None
    
    if "vars" in top_frame and key in top_frame["vars"]:
        value = top_frame["vars"][key]
        source = "vars"
    elif "args" in top_frame and key in top_frame["args"]:
        value = top_frame["args"][key]
        source = "args"
    elif key == "prev" and "prev" in top_frame:
        value = top_frame["prev"]
        source = "prev"
    
    print(f"\n[GET_VAR] session={session_id}")
    if value is not None:
        print(f"KEY: {key}")
        print(f"VALUE: {json.dumps(value, ensure_ascii=False)}")
        print(f"SOURCE: {source}")
    else:
        print(f"KEY: {key}")
        print(f"VALUE: (not found)")
    
    return None, None, None  # 特殊：不调用 print_operation_result


def op_del_var(session_id: str, args: list) -> tuple:
    """批量删除栈顶帧的临时变量"""
    if not args:
        before = load_state(session_id)
        return before, before, f"Missing <key>...\nUsage: stack_ops.py {session_id} del_var <key1> [key2 ...]"
    
    before = load_state(session_id, must_exist=True)
    
    if not before.get("stack"):
        return before, before, "Cannot del_var: stack is empty"
    
    after = copy.deepcopy(before)
    top_frame = after["stack"][-1]
    
    if "vars" not in top_frame:
        return before, before, "No vars to delete (vars is empty)"
    
    # 检查哪些 key 存在
    not_found = [k for k in args if k not in top_frame["vars"]]
    if not_found:
        return before, before, f"Variable(s) not found in vars: {', '.join(not_found)}"
    
    # 批量删除
    for key in args:
        del top_frame["vars"][key]
    
    # 如果 vars 为空，移除整个字段
    if not top_frame["vars"]:
        del top_frame["vars"]
    
    save_state(session_id, after)
    return before, after, None


def op_assert_empty(session_id: str, args: list) -> tuple:
    """断言栈为空（返回 complete 前必须调用）"""
    state = load_state(session_id, must_exist=True)
    stack = state.get("stack", [])
    
    print(f"\n[ASSERT_EMPTY] session={session_id}")
    
    if not stack:
        print("[OK] Stack is empty (depth=0)")
        print("Safe to return complete.")
        sys.exit(0)
    else:
        print("[FAIL] Stack NOT empty!")
        print(f"  depth: {len(stack)}")
        print(f"  status: {state.get('status', 'idle')}")
        print("  stack:")
        for i, frame in enumerate(stack):
            line = f"    [{i}] {frame.get('function', '?')}"
            if frame.get("args"):
                line += f" args={json.dumps(frame['args'], ensure_ascii=False)}"
            if frame.get("prev"):
                line += " [has prev]"
            if frame.get("step_index") is not None:
                line += f" step={frame['step_index']}"
            print(line)
        print("")
        print("[ACTION] Do NOT return complete!")
        print("  Continue processing the top frame's on_complete.")
        sys.exit(1)


def op_get_next_action(session_id: str, args: list) -> tuple:
    """获取栈状态和下一步建议操作（JSON 输出）"""
    state = load_state(session_id, must_exist=True)
    stack = state.get("stack", [])
    
    result = {
        "status": state.get("status", "idle"),
        "depth": len(stack),
        "next_action": None,
        "top_frame": None
    }
    
    if not stack:
        result["next_action"] = "complete"
    else:
        result["next_action"] = "continue"
        top = stack[-1]
        result["top_frame"] = {
            "function": top.get("function")
        }
        if top.get("args"):
            result["top_frame"]["args"] = top["args"]
        if top.get("step_index") is not None:
            result["top_frame"]["step_index"] = top["step_index"]
        if top.get("prev") is not None:
            result["top_frame"]["has_prev"] = True
    
    # 输出纯 JSON
    print(json.dumps(result, ensure_ascii=False))
    return None, None, None


# ============== 主入口 ==============

OPERATIONS = {
    "init": op_init,
    "push": op_push,
    "pop": op_pop,
    "peek": op_peek,
    "update": op_update,
    "set_status": op_set_status,
    "set_output": op_set_output,
    "set_agent_id": op_set_agent_id,
    "clear": op_clear,
    "show": op_show,
    "tail_call": op_tail_call,
    "return": op_return,
    "call": op_call,
    "set_var": op_set_var,
    "get_var": op_get_var,
    "del_var": op_del_var,
    "assert_empty": op_assert_empty,
    "get_next_action": op_get_next_action,
}


def print_help():
    """打印帮助信息"""
    print(__doc__)
    print("\nAvailable operations:", ", ".join(OPERATIONS.keys()))


def get_auto_session_id() -> str:
    """从 WT_SESSION 环境变量自动获取 session_id"""
    wt_session = os.environ.get("WT_SESSION", "")
    if not wt_session:
        print("[ERROR] Cannot auto-detect session: WT_SESSION environment variable not set")
        print("  - In PowerShell: $env:WT_SESSION should be set by Windows Terminal")
        print("  - In Git Bash: WT_SESSION should be inherited from parent")
        print("")
        print("Make sure you are running from Windows Terminal.")
        sys.exit(1)
    return wt_session


def main():
    # 支持 --help / -h / help
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        print_help()
        sys.exit(0)
    
    first_arg = sys.argv[1].lower()
    
    # 判断第一个参数是 operation 还是 session_id
    # 如果第一个参数是已知操作，则自动检测 session_id
    # 否则视为 session_id（支持显式传入，用于测试）
    if first_arg in OPERATIONS:
        # 自动检测 session_id
        session_id = get_auto_session_id()
        operation = first_arg
        op_args = sys.argv[2:]
    else:
        # 显式 session_id（用于测试）
        if len(sys.argv) < 3:
            print_help()
            sys.exit(1)
        session_id = sys.argv[1]
        operation = sys.argv[2].lower()
        op_args = sys.argv[3:]
    
    if operation not in OPERATIONS:
        print(f"[ERROR] Unknown operation: {operation}")
        print("Available operations:", ", ".join(OPERATIONS.keys()))
        sys.exit(1)
    
    # 执行操作
    op_func = OPERATIONS[operation]
    before, after, error = op_func(session_id, op_args)
    
    # peek, show, get_var, assert_empty, get_next_action 自己处理输出
    if operation in ("peek", "show", "get_var", "assert_empty", "get_next_action") and before is None:
        sys.exit(0 if error is None else 1)
    
    # 打印结果
    print_operation_result(session_id, operation, before, after, error)
    
    if error:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
