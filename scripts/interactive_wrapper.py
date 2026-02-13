#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/interactive_wrapper.py - 交互式脚本包装器

功能：
1. 启动指定的交互式脚本
2. 管理与 AI 的通信（单文件方案）
3. 支持参数转发
4. 支持多实例并行（基于 WT_SESSION）

用法：
    python scripts/interactive_wrapper.py <script> [args...]

环境变量：
    WT_SESSION - 会话 ID，用于隔离多实例运行
"""

import subprocess
import os
import sys
import time
from pathlib import Path


def get_session_id() -> str:
    """获取会话 ID（调用 scripts/get_session_id.py）"""
    wrapper_dir = Path(__file__).parent
    get_session_script = wrapper_dir / 'get_session_id.py'

    result = subprocess.run(
        [sys.executable, str(get_session_script), '--format', 'raw'],
        capture_output=True,
        text=True
    )
    return result.stdout.strip() or 'default'


def get_session_dir(session_id: str) -> Path:
    """获取会话目录：scripts/states/<session_id>"""
    base_dir = Path(__file__).parent / 'states' / session_id
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


# 输入结束标记（AI 写入答案时必须以此结尾）
INPUT_END_MARKER = '<<CC_FN_INPUT_END>>'


def is_input_complete(input_file: Path) -> bool:
    """检查输入文件是否完整（包含结束标记）"""
    if not input_file.exists():
        return False
    try:
        content = input_file.read_text(encoding='utf-8-sig')
        return INPUT_END_MARKER in content
    except Exception:
        return False

def main():
    # 获取参数
    if len(sys.argv) < 2:
        print("用法: python interactive_wrapper.py <script> [args...]", file=sys.stderr)
        sys.exit(1)

    script_path = sys.argv[1]
    script_args = sys.argv[2:]

    # 获取会话 ID（调用 get_session_id.py）
    session_id = get_session_id()

    # 创建会话目录
    session_dir = get_session_dir(session_id)
    output_file = session_dir / 'agent_output.txt'
    input_file = session_dir / 'agent_input.txt'

    # 环境变量
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'

    # 启动脚本
    proc = subprocess.Popen(
        [sys.executable, '-u', script_path] + script_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        env=env
    )

    output_buffer = ''
    turn = 0
    exit_code = None

    try:
        while True:
            char = proc.stdout.read(1)
            if not char:
                exit_code = proc.wait()
                break
            output_buffer += char

            # 检测输入提示：被调用脚本需在需要 AI 交互时输出 <<CC_FN_INPUT_NEEDED>>
            if '<<CC_FN_INPUT_NEEDED>>' in output_buffer:
                turn += 1

                # 整块在内存拼好再一次性写入，避免 wait_for_status 在 grep 命中时读到半写入内容（缺换行等）
                block = (
                    f'=== CC_FN_TURN {turn} ===\n'
                    f'STATUS: CC_FN_WAITING_FOR_INPUT\n'
                    f'{output_buffer}'
                )
                if block and block[-1] != '\n':
                    block += '\n'
                output_file.write_text(block, encoding='utf-8')

                # 等待 AI 答案（必须包含结束标记 <<CC_FN_INPUT_END>>）
                while not is_input_complete(input_file):
                    if proc.poll() is not None:
                        exit_code = proc.returncode
                        break
                    time.sleep(0.5)

                if exit_code is not None:
                    break

                # 读取答案并发送（utf-8-sig 去掉 BOM，移除结束标记）
                with open(input_file, 'r', encoding='utf-8-sig') as f:
                    answer = f.read().replace(INPUT_END_MARKER, '').strip()

                proc.stdin.write(answer + '\n')
                proc.stdin.flush()
                # 删除答案文件（Windows 可能有文件锁，忽略错误）
                try:
                    input_file.unlink()
                except PermissionError:
                    pass  # Windows file lock, ignore
                output_buffer = ''

    finally:
        if exit_code is None:
            exit_code = proc.wait()

        # 写入完成标记和输出内容
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f'=== CC_FN_COMPLETE ===\n')
            f.write(f'EXIT_CODE: {exit_code}\n')
            if output_buffer:
                f.write(f'\n{output_buffer}')

    sys.exit(exit_code)

if __name__ == '__main__':
    main()