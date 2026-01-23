#!/usr/bin/env python3
"""
Function Chain Driver - 使用 Claude Agent SDK 确保调用链完整执行

用法:
    python scripts/run_chain.py <function_name> [input]
    
示例:
    python scripts/run_chain.py code_review "test_data/sample_code.py security"
"""

import asyncio
import sys
import json
import os

try:
    from anthropic_claude_agent_sdk import query, ClaudeAgentOptions
except ImportError:
    # 如果没有安装 SDK，使用备用方案
    query = None
    ClaudeAgentOptions = None


async def run_with_sdk(function_name: str, input_text: str):
    """使用 Agent SDK 执行 function 调用链"""
    prompt = f"/fn {function_name} {input_text}"
    
    print(f"🚀 启动 function 调用链: {function_name}")
    print(f"📝 输入: {input_text}")
    print("=" * 50)
    
    options = ClaudeAgentOptions(
        max_turns=20,  # 允许足够多的轮次完成调用链
        setting_sources=["project"],  # 加载项目 settings
    )
    
    async for message in query(prompt=prompt, options=options):
        if message.type == "text":
            print(message.text)
        elif message.type == "tool_use":
            print(f"🔧 使用工具: {message.name}")
        elif message.type == "result":
            print("=" * 50)
            print("✅ 调用链完成")
            return message.result
        elif message.type == "error":
            print(f"❌ 错误: {message.error}")
            return None
    
    return None


def run_with_headless(function_name: str, input_text: str):
    """使用 headless 模式作为备用方案"""
    import subprocess
    
    state_file = "scripts/state.json"
    max_iterations = 20
    
    print(f"🚀 启动 function 调用链: {function_name}")
    print(f"📝 输入: {input_text}")
    print("=" * 50)
    
    # 初始命令
    prompt = f"/fn {function_name} {input_text}"
    
    for i in range(max_iterations):
        print(f"\n--- 迭代 {i + 1} ---")
        
        # 使用 headless 模式执行
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode != 0:
            print(f"❌ 执行失败: {result.stderr}")
            break
        
        # 检查状态
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            if state.get("status") == "completed":
                print("=" * 50)
                print("✅ 调用链完成")
                print(f"执行路径: {' → '.join(state.get('completed_functions', []))}")
                break
            elif state.get("status") == "running" and state.get("current_function"):
                # 继续执行
                prompt = f"继续执行 function 调用链，当前: {state['current_function']}"
                print(f"🔄 继续: {state['current_function']}")
            else:
                print("⚠️ 状态异常，停止执行")
                break
        except Exception as e:
            print(f"⚠️ 无法读取状态: {e}")
            break
    else:
        print("⚠️ 达到最大迭代次数")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    function_name = sys.argv[1]
    input_text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    
    if query is not None:
        # 使用 Agent SDK
        asyncio.run(run_with_sdk(function_name, input_text))
    else:
        print("⚠️ Agent SDK 未安装，使用 headless 备用方案")
        print("   安装: pip install anthropic-claude-agent-sdk")
        print()
        run_with_headless(function_name, input_text)


if __name__ == "__main__":
    main()
