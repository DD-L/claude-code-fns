#!/usr/bin/env python3
"""
Automated Test Suite for stack_ops.py and check_chain.py

Run: python scripts/test_stack_ops.py

All test sessions use "_test_" prefix and are cleaned up after tests.
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# 路径配置
SCRIPT_DIR = Path(__file__).parent.resolve()
STATES_DIR = SCRIPT_DIR / "states"
STACK_OPS = SCRIPT_DIR / "stack_ops.py"
CHECK_CHAIN = SCRIPT_DIR / "check_chain.py"

# 测试 session 前缀（便于清理）
TEST_PREFIX = "_test_"

# 统计
passed = 0
failed = 0
errors = []


def run_stack_ops(session: str, op: str, *args) -> tuple:
    """运行 stack_ops.py，返回 (exit_code, stdout, stderr)"""
    cmd = [sys.executable, str(STACK_OPS), session, op] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def run_check_chain(session: str) -> tuple:
    """运行 check_chain.py，设置 WT_SESSION 环境变量"""
    env = os.environ.copy()
    env["WT_SESSION"] = session
    cmd = [sys.executable, str(CHECK_CHAIN)]
    # 使用空 stdin 避免阻塞
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, 
                           input="", timeout=10)
    return result.returncode, result.stdout, result.stderr


def load_state(session: str) -> dict:
    """直接读取状态文件"""
    state_file = STATES_DIR / f"{session}.json"
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def cleanup_test_sessions():
    """清理所有测试 session"""
    if STATES_DIR.exists():
        for f in STATES_DIR.glob(f"{TEST_PREFIX}*.json"):
            try:
                f.unlink()
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

def test_basic_operations():
    """测试基本操作：init, push, pop, show, peek, clear"""
    test_section("Basic Operations")
    session = f"{TEST_PREFIX}basic"
    
    # init
    code, out, err = run_stack_ops(session, "init")
    test("init returns 0", code == 0)
    state = load_state(session)
    test("init creates idle state", state and state.get("status") == "idle")
    test("init creates empty stack", state and state.get("stack") == [])
    
    # push
    code, out, err = run_stack_ops(session, "push", "route_a", "--arg.n=5", "--arg.from=main")
    test("push returns 0", code == 0)
    state = load_state(session)
    test("push sets status=running", state.get("status") == "running")
    test("push adds frame", len(state.get("stack", [])) == 1)
    test("push sets function name", state["stack"][0]["function"] == "route_a")
    test("push sets args", state["stack"][0]["args"] == {"n": 5, "from": "main"})
    
    # peek
    code, out, err = run_stack_ops(session, "peek")
    test("peek returns 0", code == 0)
    test("peek shows function", "route_a" in out)
    
    # show
    code, out, err = run_stack_ops(session, "show")
    test("show returns 0", code == 0)
    test("show displays status", "status: running" in out)
    test("show displays stack", "route_a" in out)
    
    # pop
    code, out, err = run_stack_ops(session, "pop")
    test("pop returns 0", code == 0)
    state = load_state(session)
    test("pop removes frame", len(state.get("stack", [])) == 0)
    test("pop sets status=idle when empty", state.get("status") == "idle")
    
    # clear
    run_stack_ops(session, "push", "test_fn")
    code, out, err = run_stack_ops(session, "clear")
    test("clear returns 0", code == 0)
    state = load_state(session)
    test("clear empties stack", state.get("stack") == [])
    test("clear sets idle", state.get("status") == "idle")


def test_tail_call_and_return():
    """测试 tail_call 和 return 操作"""
    test_section("Tail Call and Return")
    session = f"{TEST_PREFIX}tailcall"
    
    run_stack_ops(session, "init")
    run_stack_ops(session, "push", "route_a", "--arg.n=3")
    
    # tail_call
    code, out, err = run_stack_ops(session, "tail_call", "route_b", "--arg.n=2")
    test("tail_call returns 0", code == 0)
    state = load_state(session)
    test("tail_call keeps depth=1", len(state.get("stack", [])) == 1)
    test("tail_call replaces function", state["stack"][0]["function"] == "route_b")
    test("tail_call updates args", state["stack"][0]["args"]["n"] == 2)
    
    # return with value
    code, out, err = run_stack_ops(session, "return", "result_value")
    test("return returns 0", code == 0)
    state = load_state(session)
    test("return pops stack", len(state.get("stack", [])) == 0)
    test("return sets output", state.get("output") == "result_value")
    test("return sets idle", state.get("status") == "idle")


def test_nested_calls():
    """测试嵌套调用和 prev 传递"""
    test_section("Nested Calls and $prev")
    session = f"{TEST_PREFIX}nested"
    
    run_stack_ops(session, "init")
    run_stack_ops(session, "push", "parent")
    run_stack_ops(session, "push", "child")
    
    state = load_state(session)
    test("nested push creates depth=2", len(state.get("stack", [])) == 2)
    
    # return with value - should set parent's prev
    code, out, err = run_stack_ops(session, "return", "child_result")
    state = load_state(session)
    test("return pops to depth=1", len(state.get("stack", [])) == 1)
    test("return sets parent.prev", state["stack"][0].get("prev") == "child_result")


def test_status_operations():
    """测试状态操作：set_status (包括 error)"""
    test_section("Status Operations")
    session = f"{TEST_PREFIX}status"
    
    run_stack_ops(session, "init")
    
    # set_status running
    code, out, err = run_stack_ops(session, "set_status", "running")
    test("set_status running returns 0", code == 0)
    state = load_state(session)
    test("set_status running works", state.get("status") == "running")
    
    # set_status error (新功能)
    code, out, err = run_stack_ops(session, "set_status", "error")
    test("set_status error returns 0", code == 0)
    state = load_state(session)
    test("set_status error works", state.get("status") == "error")
    
    # set_status idle
    code, out, err = run_stack_ops(session, "set_status", "idle")
    test("set_status idle works", load_state(session).get("status") == "idle")
    
    # invalid status
    code, out, err = run_stack_ops(session, "set_status", "invalid")
    test("set_status invalid fails", code != 0)


def test_agent_id():
    """测试 controller_agent_id 功能"""
    test_section("Controller Agent ID")
    session = f"{TEST_PREFIX}agent"
    
    run_stack_ops(session, "init")
    
    # set_agent_id
    code, out, err = run_stack_ops(session, "set_agent_id", "abc-123-def-456")
    test("set_agent_id returns 0", code == 0)
    state = load_state(session)
    test("set_agent_id stores value", state.get("controller_agent_id") == "abc-123-def-456")
    
    # show displays agent_id
    code, out, err = run_stack_ops(session, "show")
    test("show displays agent_id", "controller_agent_id" in out)
    
    # diff shows agent_id change
    test("diff shows + controller_agent_id", "+ controller_agent_id" in out or "abc-123" in out)
    
    # clear removes agent_id
    run_stack_ops(session, "clear")
    state = load_state(session)
    test("clear removes agent_id", state.get("controller_agent_id") is None)


def test_last_updated():
    """测试 last_updated 自动更新"""
    test_section("Last Updated Timestamp")
    session = f"{TEST_PREFIX}timestamp"
    
    run_stack_ops(session, "init")
    state1 = load_state(session)
    test("init sets last_updated", "last_updated" in state1)
    
    import time
    time.sleep(0.1)  # 确保时间差
    
    run_stack_ops(session, "push", "test_fn")
    state2 = load_state(session)
    test("push updates last_updated", state2.get("last_updated") != state1.get("last_updated"))
    
    # 验证 ISO8601 格式
    try:
        datetime.fromisoformat(state2["last_updated"])
        test("last_updated is ISO8601 format", True)
    except:
        test("last_updated is ISO8601 format", False, state2.get("last_updated"))


def test_output_operations():
    """测试输出操作"""
    test_section("Output Operations")
    session = f"{TEST_PREFIX}output"
    
    run_stack_ops(session, "init")
    
    # set_output
    code, out, err = run_stack_ops(session, "set_output", "hello world")
    test("set_output returns 0", code == 0)
    state = load_state(session)
    test("set_output stores value", state.get("output") == "hello world")


def test_variable_operations():
    """测试变量操作：set_var, get_var, del_var"""
    test_section("Variable Operations")
    session = f"{TEST_PREFIX}vars"
    
    run_stack_ops(session, "init")
    run_stack_ops(session, "push", "test_fn")
    
    # set_var
    code, out, err = run_stack_ops(session, "set_var", "--var.x=100", "--var.name=test")
    test("set_var returns 0", code == 0)
    state = load_state(session)
    test("set_var stores x", state["stack"][0].get("vars", {}).get("x") == 100)
    test("set_var stores name", state["stack"][0].get("vars", {}).get("name") == "test")
    
    # get_var
    code, out, err = run_stack_ops(session, "get_var", "x")
    test("get_var returns 0", code == 0)
    test("get_var shows value", "100" in out)
    test("get_var shows source", "vars" in out)
    
    # del_var
    code, out, err = run_stack_ops(session, "del_var", "x")
    test("del_var returns 0", code == 0)
    state = load_state(session)
    test("del_var removes x", "x" not in state["stack"][0].get("vars", {}))


def test_update_operation():
    """测试 update 操作"""
    test_section("Update Operation")
    session = f"{TEST_PREFIX}update"
    
    run_stack_ops(session, "init")
    run_stack_ops(session, "push", "test_fn")
    
    # update step_index
    code, out, err = run_stack_ops(session, "update", "--step_index=2")
    test("update step_index returns 0", code == 0)
    state = load_state(session)
    test("update sets step_index", state["stack"][0].get("step_index") == 2)
    
    # update prev
    code, out, err = run_stack_ops(session, "update", "--prev=previous_value")
    test("update prev returns 0", code == 0)
    state = load_state(session)
    test("update sets prev", state["stack"][0].get("prev") == "previous_value")


def test_check_chain():
    """测试 check_chain.py (stop-hook)"""
    test_section("Check Chain (Stop Hook)")
    session = f"{TEST_PREFIX}hook"
    
    # 空栈应允许停止
    run_stack_ops(session, "init")
    code, out, err = run_check_chain(session)
    test("empty stack allows stop (exit 0)", code == 0)
    test("empty stack outputs [ok]", "[ok]" in err)
    
    # 非空栈应阻止停止
    run_stack_ops(session, "push", "route_a", "--arg.n=3")
    code, out, err = run_check_chain(session)
    test("non-empty stack blocks stop (exit 2)", code == 2)
    test("non-empty outputs STOP-HOOK", "STOP-HOOK" in err)
    test("non-empty shows stack depth", "Stack depth:" in err)
    
    # 非空栈显示 continue 指令
    test("shows operation=continue", "operation=continue" in err)
    test("shows fn-controller prompt", "fn-controller" in err)


def test_get_next_action():
    """测试 get_next_action 操作"""
    test_section("Get Next Action")
    session = f"{TEST_PREFIX}nextaction"
    
    # 空栈应返回 complete
    run_stack_ops(session, "init")
    code, out, err = run_stack_ops(session, "get_next_action")
    test("get_next_action returns 0 (empty)", code == 0)
    test("get_next_action outputs JSON", "{" in out)
    
    # 解析 JSON 输出
    try:
        result = json.loads(out.strip())
        test("empty stack returns next_action=complete", result.get("next_action") == "complete")
        test("empty stack has depth=0", result.get("depth") == 0)
        test("empty stack has status", "status" in result)
    except json.JSONDecodeError:
        test("get_next_action returns valid JSON", False, out)
    
    # 非空栈应返回 continue
    run_stack_ops(session, "push", "route_a", "--arg.n=5", "--arg.from=main")
    code, out, err = run_stack_ops(session, "get_next_action")
    test("get_next_action returns 0 (non-empty)", code == 0)
    
    try:
        result = json.loads(out.strip())
        test("non-empty returns next_action=continue", result.get("next_action") == "continue")
        test("non-empty has depth=1", result.get("depth") == 1)
        test("non-empty has top_frame", "top_frame" in result)
        test("top_frame has function", result.get("top_frame", {}).get("function") == "route_a")
        test("top_frame has args", "args" in result.get("top_frame", {}))
    except json.JSONDecodeError:
        test("get_next_action returns valid JSON (non-empty)", False, out)
    
    # 有 prev 时应显示 has_prev
    run_stack_ops(session, "push", "child")
    run_stack_ops(session, "return", "child_result")
    code, out, err = run_stack_ops(session, "get_next_action")
    
    try:
        result = json.loads(out.strip())
        test("has_prev shows when prev exists", result.get("top_frame", {}).get("has_prev") == True)
    except json.JSONDecodeError:
        test("get_next_action returns valid JSON (with prev)", False, out)
    
    # 栈空后应返回 complete
    run_stack_ops(session, "return")
    code, out, err = run_stack_ops(session, "get_next_action")
    
    try:
        result = json.loads(out.strip())
        test("after return empty returns complete", result.get("next_action") == "complete")
    except json.JSONDecodeError:
        test("get_next_action returns valid JSON (after return)", False, out)


def test_error_handling():
    """测试错误处理"""
    test_section("Error Handling")
    session = f"{TEST_PREFIX}errors"
    
    run_stack_ops(session, "init")
    
    # pop 空栈
    code, out, err = run_stack_ops(session, "pop")
    test("pop empty stack fails", code != 0)
    test("pop empty shows error", "empty" in out.lower())
    
    # tail_call 空栈
    code, out, err = run_stack_ops(session, "tail_call", "route_a")
    test("tail_call empty stack fails", code != 0)
    
    # return 空栈
    code, out, err = run_stack_ops(session, "return")
    test("return empty stack fails", code != 0)
    
    # 缺少参数
    code, out, err = run_stack_ops(session, "push")
    test("push without fqn fails", code != 0)
    
    code, out, err = run_stack_ops(session, "set_agent_id")
    test("set_agent_id without value fails", code != 0)


def test_call_alias():
    """测试 call 作为 push 的别名"""
    test_section("Call Alias")
    session = f"{TEST_PREFIX}call"
    
    run_stack_ops(session, "init")
    code, out, err = run_stack_ops(session, "call", "route_a", "--arg.n=1")
    test("call returns 0", code == 0)
    state = load_state(session)
    test("call adds frame", len(state.get("stack", [])) == 1)
    test("call sets function", state["stack"][0]["function"] == "route_a")


def test_step_index_continuity():
    """测试 step_index 必须连续递增"""
    test_section("Step Index Continuity")
    session = f"{TEST_PREFIX}stepindex"
    
    # 初始化
    run_stack_ops(session, "clear")
    run_stack_ops(session, "push", "test/sequence_func")
    
    # 首次更新: 设置 step_index=1 (有效 - 首次更新)
    code, out, err = run_stack_ops(session, "update", "--step_index=1")
    test("step_index=1 (first update) succeeds", code == 0)
    state = load_state(session)
    test("step_index is set to 1", state["stack"][0].get("step_index") == 1)
    
    # 连续更新: step_index=2 (有效 - 连续递增)
    code, out, err = run_stack_ops(session, "update", "--step_index=2")
    test("step_index=2 (continuous) succeeds", code == 0)
    state = load_state(session)
    test("step_index is set to 2", state["stack"][0].get("step_index") == 2)
    
    # 跳步更新: step_index=4 (应该失败)
    code, out, err = run_stack_ops(session, "update", "--step_index=4")
    test("step_index=4 (skip) fails", code != 0)
    test("skip error mentions step_index", "step_index" in out.lower() or "not continuous" in out.lower())
    state = load_state(session)
    test("step_index unchanged after skip failure", state["stack"][0].get("step_index") == 2)
    
    # 使用 --force-step-index 跳过验证 (应该成功)
    code, out, err = run_stack_ops(session, "update", "--step_index=4", "--force-step-index")
    test("step_index=4 with --force-step-index succeeds", code == 0)
    state = load_state(session)
    test("step_index is set to 4 with force", state["stack"][0].get("step_index") == 4)
    
    # 清理
    run_stack_ops(session, "clear")


def test_sequence_simulation():
    """模拟 4 步 sequence 执行并验证所有步骤"""
    test_section("4-Step Sequence Simulation")
    session = f"{TEST_PREFIX}seqsim"
    
    # 清理并初始化
    run_stack_ops(session, "clear")
    
    # 模拟: push 主函数 (带 sequence)
    run_stack_ops(session, "push", "tests/test_sequence_4steps", "--arg.input=hello")
    
    # Step 0: 执行 step[0] (call seq_step1)
    run_stack_ops(session, "update", "--step_index=1")  # 更新为下一步
    run_stack_ops(session, "push", "tests/seq_step1", "--arg.data=hello")
    
    # seq_step1 返回
    run_stack_ops(session, "return", "step1_hello")
    
    # 验证父帧有 prev
    state = load_state(session)
    test("step 0: stack depth=1", len(state.get("stack", [])) == 1)
    test("step 0: parent has prev", state["stack"][0].get("prev") == "step1_hello")
    test("step 0: step_index is 1", state["stack"][0].get("step_index") == 1)
    
    # Step 1: 执行 step[1] (call seq_step2)
    run_stack_ops(session, "update", "--step_index=2")
    run_stack_ops(session, "push", "tests/seq_step2", "--arg.data=step1_hello")
    
    # seq_step2 返回
    run_stack_ops(session, "return", "step1_hello_step2")
    
    state = load_state(session)
    test("step 1: prev updated", state["stack"][0].get("prev") == "step1_hello_step2")
    test("step 1: step_index is 2", state["stack"][0].get("step_index") == 2)
    
    # Step 2: 执行 step[2] (call seq_step3)
    run_stack_ops(session, "update", "--step_index=3")
    run_stack_ops(session, "push", "tests/seq_step3", "--arg.data=step1_hello_step2")
    
    # seq_step3 返回
    run_stack_ops(session, "return", "COMPLETED_step1_hello_step2")
    
    state = load_state(session)
    test("step 2: prev updated", state["stack"][0].get("prev") == "COMPLETED_step1_hello_step2")
    test("step 2: step_index is 3", state["stack"][0].get("step_index") == 3)
    
    # Step 3: 执行 step[3] (tail_call seq_step4)
    run_stack_ops(session, "tail_call", "tests/seq_step4", "--arg.data=COMPLETED_step1_hello_step2")
    
    state = load_state(session)
    test("step 3: tail_called to seq_step4", state["stack"][0].get("function") == "tests/seq_step4")
    
    # seq_step4 返回 (最终步骤)
    run_stack_ops(session, "return", "FINAL_COMPLETED_step1_hello_step2")
    
    state = load_state(session)
    test("sequence complete: stack empty", len(state.get("stack", [])) == 0)
    test("sequence complete: status idle", state.get("status") == "idle")
    
    # 清理
    run_stack_ops(session, "clear")


def test_step_skip_detection():
    """测试跳步检测"""
    test_section("Step Skip Detection")
    session = f"{TEST_PREFIX}skipdetect"
    
    # 清理并初始化
    run_stack_ops(session, "clear")
    run_stack_ops(session, "push", "tests/test_sequence", "--arg.input=test")
    run_stack_ops(session, "update", "--step_index=1")  # step 0 完成
    
    # 尝试跳到 step_index=3 (应该失败)
    code, out, err = run_stack_ops(session, "update", "--step_index=3")
    test("skip 1->3 rejected", code != 0)
    test("skip error message present", "step_index" in out.lower() or "[error]" in out.lower())
    
    # 正确递增到 2 应该成功
    code, out, err = run_stack_ops(session, "update", "--step_index=2")
    test("proper increment 1->2 succeeds", code == 0)
    
    state = load_state(session)
    test("step_index is now 2", state["stack"][0].get("step_index") == 2)
    
    # 清理
    run_stack_ops(session, "clear")


# ============== 主入口 ==============

def main():
    global passed, failed, errors
    
    print("\n" + "="*60)
    print("  Stack Operations Test Suite")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    # 确保 states 目录存在
    STATES_DIR.mkdir(parents=True, exist_ok=True)
    
    # 清理之前的测试残留
    cleanup_test_sessions()
    
    try:
        # 运行所有测试
        test_basic_operations()
        test_tail_call_and_return()
        test_nested_calls()
        test_status_operations()
        test_agent_id()
        test_last_updated()
        test_output_operations()
        test_variable_operations()
        test_update_operation()
        test_check_chain()
        test_get_next_action()
        test_error_handling()
        test_call_alias()
        
        # Sequence step tests (防止跳步 bug)
        test_step_index_continuity()
        test_sequence_simulation()
        test_step_skip_detection()
        
    finally:
        # 清理测试 session
        print(f"\n{'='*60}")
        print("  Cleanup")
        print(f"{'='*60}")
        cleanup_test_sessions()
        print("  [OK] Test sessions cleaned up")
    
    # 汇总
    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(e)
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
