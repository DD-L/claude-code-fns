#!/usr/bin/env python3
"""
Stop Hook - Check if function chain needs to continue
Session ID is obtained by calling get_session_id.py (same as fn_execute / fn-controller).

Exit codes:
  0: allow stop
  2 + stderr: block stop, stderr content is fed back to Claude

Optional: --session=<id> or CC_FN_TEST_SESSION env to override (for testing only).
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# 路径配置
SCRIPT_DIR = Path(__file__).parent.resolve()
STATES_DIR = SCRIPT_DIR / "states"
LOG_FILE = STATES_DIR / ".hook_debug.log"


def get_session_id() -> str:
    """Get session ID by calling get_session_id.py (same as fn_execute.py)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "get_session_id.py")],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return (result.stdout or "").strip()
    return "default"


def log(message: str):
    """写入调试日志"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def parse_args():
    """Parse --session= for testing (matches PS1 -TestSession)."""
    p = argparse.ArgumentParser(description="Stop hook - check function chain")
    p.add_argument("--session", "-s", metavar="ID", help="Override WT_SESSION (for testing)")
    return p.parse_known_args()[0]


def main():
    args = parse_args()
    # Session: --session or CC_FN_TEST_SESSION for testing; otherwise call get_session_id.py (same as fn-controller)
    wt_session = args.session or os.environ.get("CC_FN_TEST_SESSION")
    if not wt_session:
        wt_session = get_session_id()

    # 检查 states 目录是否存在
    if not STATES_DIR.exists():
        sys.exit(0)

    log("Stop hook triggered")

    # Only read stdin when redirected (match PS1 [Console]::IsInputRedirected)
    input_json = ""
    if not sys.stdin.isatty():
        try:
            input_json = sys.stdin.read()
        except Exception:
            pass

    log(f"session_id: {wt_session}")
    log(f"Input length: {len(input_json)}")

    # 检查 stop_hook_active 标志
    stop_hook_active = False
    if input_json:
        try:
            input_obj = json.loads(input_json)
            stop_hook_active = input_obj.get("stop_hook_active", False)
            log(f"Parsed stop_hook_active: {stop_hook_active}")
        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}")

    if stop_hook_active:
        log("stop_hook_active=true, allowing stop")
        sys.exit(0)

    # Empty session: get_session_id.py returned nothing -> allow stop (same as PS1 no WT_SESSION)
    if not wt_session:
        log("No session_id (get_session_id.py returned empty), allowing stop")
        sys.exit(0)

    # 检查状态文件
    state_file = STATES_DIR / wt_session / "state.json"
    log(f"Checking state file: {state_file}")
    
    if not state_file.exists():
        log("State file not found, allowing stop")
        sys.exit(0)
    
    # 读取状态
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except Exception as e:
        log(f"Failed to parse state file: {e}")
        sys.exit(0)
    
    # 检查栈
    stack = state.get("stack", [])
    stack_len = len(stack)
    status = state.get("status", "idle")
    
    log(f"State: status={status}, stack_len={stack_len}")
    
    if stack_len > 0:
        top_frame = stack[-1]
        
        # 检测栈泄漏
        if status == "idle":
            log(f"WARNING: Stack leak detected! status=idle but stack_len={stack_len}")
        
        log("Stack NOT empty! Blocking stop.")
        log(f"  Top frame: {top_frame.get('function', '?')}")
        
        # 记录调用链
        if stack_len > 1:
            chain_fns = [frame.get("function", "?") for frame in stack]
            log(f"  Call chain: {' -> '.join(chain_fns)}")
        
        # 构建用户友好的消息
        leak_note = " [LEAK]" if status == "idle" else ""
        msg = f"[!][STOP-HOOK] Cannot stop: Stack not empty{leak_note}"
        msg += f"\n  Session: {wt_session}"
        msg += f"\n  Stack depth: {stack_len}"
        
        # 栈顶帧（带参数）
        top_fn = top_frame.get("function", "?")
        if top_frame.get("args"):
            arg_pairs = [f"{k}={v}" for k, v in top_frame["args"].items()]
            if arg_pairs:
                top_fn += f" ({', '.join(arg_pairs)})"
        msg += f"\n  Top frame: {top_fn}"
        
        # 调用链
        if stack_len >= 1:
            chain_parts = []
            show_count = min(stack_len, 5)
            start_idx = stack_len - show_count
            if start_idx > 0:
                chain_parts.append("...")
            for i in range(start_idx, stack_len):
                chain_parts.append(stack[i].get("function", "?"))
            msg += f"\n  Call chain: {' -> '.join(chain_parts)}"

        msg += "\n"
        msg += "\n[ACTION REQUIRED] Call fn-controller subagent:"
        msg += "\n"
        msg += "\n  operation=continue, task_result=<last task result>"
        msg += "\n"
        msg += "\n  (fn-controller will auto-obtain session_id)"
        log("Prompting for fn-controller continue")
        
        print(msg, file=sys.stderr)
        sys.exit(2)
    
    # 栈空，允许停止
    output_info = ""
    if state.get("output"):
        out_str = str(state["output"])
        if len(out_str) > 100:
            out_str = out_str[:97] + "..."
        output_info = f" | output: {out_str}"
    
    log("Stack empty (stack_len=0), allowing stop")
    
    # 简短的完成消息
    complete_msg = f"[ok] {wt_session} | idle{output_info}"
    print(complete_msg, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
