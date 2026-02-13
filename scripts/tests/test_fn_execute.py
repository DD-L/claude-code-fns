#!/usr/bin/env python3
"""
Test Suite for fn_execute.py - Control Flow Tests

Run: python scripts/tests/test_fn_execute.py

Note: These tests require WT_SESSION environment variable to be set.
If running in Cursor Agent, you may need to set it manually:
    $env:WT_SESSION = "test_fn_execute"
    python scripts/tests/test_fn_execute.py
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

# 路径配置
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
STATES_DIR = SCRIPT_DIR / "states"

# 添加 scripts 目录到路径
sys.path.insert(0, str(SCRIPT_DIR))

# 测试 session 前缀（便于清理）
TEST_PREFIX = "_test_fn_"

# 统计
passed = 0
failed = 0
errors = []


def run_fn_execute(session: str, cmd: str, *args) -> tuple:
    """运行 fn_execute.py，返回 (exit_code, stdout, stderr)"""
    env = os.environ.copy()
    env["WT_SESSION"] = session
    env["PYTHONIOENCODING"] = "utf-8"
    
    cmd_args = [sys.executable, str(SCRIPT_DIR / "fn_execute.py"), cmd] + list(args)
    result = subprocess.run(cmd_args, capture_output=True, text=True, env=env, encoding='utf-8', errors='replace')
    return result.returncode, result.stdout or "", result.stderr or ""


def load_state(session: str) -> dict:
    """直接读取状态文件"""
    state_file = STATES_DIR / session / "state.json"
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def cleanup_test_sessions():
    """清理所有测试 session 目录"""
    if STATES_DIR.exists():
        for d in STATES_DIR.glob(f"{TEST_PREFIX}*"):
            if d.is_dir():
                try:
                    shutil.rmtree(d)
                except:
                    pass


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

def test_start_simple():
    """测试简单的 start 命令"""
    test_section("Start Command - Simple")
    session = f"{TEST_PREFIX}start_simple"
    
    # 启动一个简单函数
    code, out, err = run_fn_execute(session, "start", "tests/test_loop", "count=0", "max=3")
    
    test("exit_code_0", code == 0, f"got {code}, stderr: {err}")
    test("has_task", "[TASK]" in out, f"output: {out}")
    test("has_prompt", "prompt:" in out)
    test("has_stack_depth", "stack_depth: 1" in out)
    test("has_resume_next", "resume_next:" in out)
    
    # 检查状态
    state = load_state(session)
    test("state_exists", state is not None)
    if state:
        test("stack_len_1", len(state.get("stack", [])) == 1)
        test("status_running", state.get("status") == "running")


def test_start_with_args():
    """测试带参数的 start 命令"""
    test_section("Start Command - With Args")
    session = f"{TEST_PREFIX}start_args"
    
    code, out, err = run_fn_execute(session, "start", "tests/test_branch", "mode=A")
    
    test("exit_code_0", code == 0)
    test("has_task", "[TASK]" in out)
    
    state = load_state(session)
    if state:
        frame = state["stack"][0]
        test("arg_mode", frame["args"].get("mode") == "A", f"got {frame['args']}")


def test_start_invalid_function():
    """测试无效函数名"""
    test_section("Start Command - Invalid Function")
    session = f"{TEST_PREFIX}start_invalid"
    
    code, out, err = run_fn_execute(session, "start", "nonexistent_function")
    
    test("has_error", "[ERROR]" in out or code != 0, f"output: {out}")


def test_continue_loop():
    """测试 continue 命令（循环场景）"""
    test_section("Continue Command - Loop")
    session = f"{TEST_PREFIX}continue_loop"
    
    # 先 start
    code, out, err = run_fn_execute(session, "start", "tests/test_loop", "count=0", "max=2")
    test("start_ok", code == 0 and "[TASK]" in out)
    
    # 第一次 continue
    code, out, err = run_fn_execute(session, "continue", 'task_result=iteration 0 done')
    test("continue1_ok", code == 0, f"stderr: {err}")
    test("continue1_has_task", "[TASK]" in out, f"output: {out}")
    
    # 检查状态 - count 应该增加
    state = load_state(session)
    if state and state.get("stack"):
        frame = state["stack"][-1]
        test("count_incremented", frame["args"].get("count") == 1, f"got {frame['args']}")


def test_continue_to_complete():
    """测试 continue 直到完成"""
    test_section("Continue to Complete")
    session = f"{TEST_PREFIX}continue_complete"
    
    # 使用 max=1 的循环，应该很快完成
    code, out, err = run_fn_execute(session, "start", "tests/test_loop", "count=0", "max=1")
    test("start_ok", code == 0)
    
    # 第一次 continue
    code, out, err = run_fn_execute(session, "continue", 'task_result=done')
    # 循环条件: count < max, 新 count=1, 1 < 1 = false, 应该返回
    test("continue_ok", code == 0)
    test("has_complete", "[COMPLETE]" in out or "[TASK]" in out, f"output: {out}")


def test_switch_branch():
    """测试 switch 分支"""
    test_section("Switch Branch")
    session = f"{TEST_PREFIX}switch"
    
    # mode=A 应该 call branch_handler_a
    code, out, err = run_fn_execute(session, "start", "tests/test_branch", "mode=A")
    test("start_ok", code == 0)
    
    # continue 后应该进入 branch_handler_a
    code, out, err = run_fn_execute(session, "continue", 'task_result=done')
    test("continue_ok", code == 0)
    
    state = load_state(session)
    if state and state.get("stack"):
        # 应该有 branch_handler_a 在栈上
        functions = [f["function"] for f in state["stack"]]
        test("called_handler_a", any("branch_handler_a" in f for f in functions), f"stack: {functions}")


def test_switch_default():
    """测试 switch 默认分支"""
    test_section("Switch Default")
    session = f"{TEST_PREFIX}switch_default"
    
    # mode=X 不匹配任何分支，应该走 default
    code, out, err = run_fn_execute(session, "start", "tests/test_branch", "mode=X")
    test("start_ok", code == 0)
    
    code, out, err = run_fn_execute(session, "continue", 'task_result=done')
    # default 是 return，应该完成
    test("continue_ok", code == 0)


def test_sequence():
    """测试 sequence"""
    test_section("Sequence")
    session = f"{TEST_PREFIX}sequence"
    
    code, out, err = run_fn_execute(session, "start", "tests/test_sequence", "input=hello")
    test("start_ok", code == 0)
    
    # 检查状态
    state = load_state(session)
    if state and state.get("stack"):
        frame = state["stack"][-1]
        test("step_index_0", frame.get("step_index") == 0, f"got {frame}")


def test_controller_state():
    """测试 controller 状态管理"""
    test_section("Controller State")
    session = f"{TEST_PREFIX}controller"
    
    code, out, err = run_fn_execute(session, "start", "tests/test_loop", "count=0", "max=3")
    
    state = load_state(session)
    test("has_controller", "controller" in state, f"state keys: {state.keys() if state else None}")
    
    if state and "controller" in state:
        controller = state["controller"]
        test("has_resume_count", "resume_count" in controller)
        test("has_max_resume", "max_resume_before_refresh" in controller)


def test_resume_next():
    """测试 resume_next 输出"""
    test_section("Resume Next")
    session = f"{TEST_PREFIX}resume_next"
    
    code, out, err = run_fn_execute(session, "start", "tests/test_loop", "count=0", "max=3")
    
    test("has_resume_next", "resume_next:" in out, f"output: {out}")
    
    # 检查输出中的 resume_next 值
    if "resume_next: true" in out:
        test("resume_next_true", True)
    elif "resume_next: false" in out:
        test("resume_next_false", True)
    else:
        test("resume_next_value", False, "Could not find resume_next value")


def test_semantic_eval_trigger():
    """测试语义评估触发（脚本会挂起等待，这里只验证触发）"""
    session = "_test_fn_semantic_eval"
    test_section("Semantic Eval Trigger")
    
    # 启动需要语义评估的函数
    code, out, _ = run_fn_execute(session, "start", "tests/test_semantic_eval", "input=hello")
    test("start_ok", code == 0)
    test("has_task", "[TASK]" in out)
    
    # Note: 完整的语义评估测试需要 interactive_wrapper.py 配合
    # 这里只验证 start 命令正常工作


def test_triggers():
    """测试 triggers (NFA 多分支) 控制流"""
    session = "_test_fn_triggers"
    test_section("Triggers (NFA Multi-Branch)")
    
    # 启动 triggers 函数，2 个条件匹配
    code, out, _ = run_fn_execute(session, "start", "tests/test_triggers", 
                                   "has_error=true", "needs_cleanup=true", "should_notify=false")
    test("start_ok", code == 0)
    test("has_task", "[TASK]" in out)
    
    # Continue 1 - 应该执行第一个匹配的 trigger (log_error)
    code, out, _ = run_fn_execute(session, "continue", "task_result=done")
    test("continue1_ok", code == 0)
    test("trigger1_log_error", "trigger_log_error" in out)
    
    # Continue 2 - 应该执行第二个匹配的 trigger (cleanup)
    code, out, _ = run_fn_execute(session, "continue", "task_result=done")
    test("continue2_ok", code == 0)
    test("trigger2_cleanup", "trigger_cleanup" in out)
    
    # Continue 3 - 应该完成
    code, out, _ = run_fn_execute(session, "continue", "task_result=done")
    test("complete", "[COMPLETE]" in out)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  fn_execute.py Test Suite")
    print("="*60)
    
    # 清理旧的测试 session
    cleanup_test_sessions()
    
    try:
        test_start_simple()
        test_start_with_args()
        test_start_invalid_function()
        test_continue_loop()
        test_continue_to_complete()
        test_switch_branch()
        test_switch_default()
        test_sequence()
        test_controller_state()
        test_resume_next()
        test_semantic_eval_trigger()
        test_triggers()
    finally:
        # 清理测试 session
        cleanup_test_sessions()
    
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
