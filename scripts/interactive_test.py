#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式测试脚本 - Agent 友好版本, 测试 Agent 与脚本的实时交互能力

设计原则：
1. 使用基于行的协议：输出以换行符结束
2. Agent 应该发送完整行（带换行符）
3. 提供明确的提示和状态反馈
4. 支持优雅退出

规则：
1. 输出有规律递增的数值序列
2. 让用户输入下一个可能的值
3. 如果猜对则继续
4. 输出剩下2个数值
5. 再让用户输入下一个可能的值
6. 如此循环，直到数值大于某个值
7. 输出任务完成

运行方式：
Bash(PYTHONIOENCODING=utf-8 python scripts/interactive_test.py)


● Task(AI语义理解交互测试)
  ⎿  Backgrounded agent
  ⎿  Prompt:
       你需要与 scripts/interactive_test.py 进行真正的 AI 语义理解交互，而不是用预先写好的逻辑。

       任务要求：
       1. 启动脚本：python scripts/interactive_test.py（设置 PYTHONIOENCODING=utf-8）
       2. 实时读取脚本的输出
       3. 每次脚本要求输入时，通过 AI 语义理解来决定输入什么值，而不是用硬编码的逻辑
       4. 将分析结果写入脚本的 stdin
       5. 持续交互直到脚本完成

       关键约束：
       - 绝对禁止使用像 seq[-1] + 1 这样的预设逻辑
       - 必须基于 AI 对输出的语义理解来决定下一个输入
       - 脚本可能会有不同的序列模式（递增、递减、斐波那契等），AI 需要理解模式

       请完整执行这个交互过程，向我展示每次 AI 是如何理解并决定输入的。
"""

import sys
import signal


class InteractiveTest:
    """Agent 友好的交互测试类"""

    def __init__(self):
        self.current = 1
        self.step = 1
        self.max_value = 55
        self.running = True

        # 设置 Ctrl+C 处理
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """处理中断信号"""
        self.running = False
        print("\n收到中断信号，退出测试。")
        sys.exit(0)

    def flush_output(self):
        """强制刷新输出"""
        sys.stdout.flush()

    def read_line(self):
        """读取一行输入，兼容 Agent 和人类交互"""
        try:
            line = sys.stdin.readline()
            if not line:  # EOF
                print("\n收到 EOF，退出测试。")
                sys.exit(0)
            return line.strip()
        except Exception as e:
            print(f"读取输入时出错: {e}")
            sys.exit(1)

    def output(self, text, flush=True):
        """输出文本，可选择是否立即刷新"""
        print(text, end='', flush=flush)
        if flush:
            self.flush_output()

    def output_line(self, text='', flush=True):
        """输出一行文本"""
        self.output(text + '\n', flush)

    def show_sequence(self):
        """显示当前序列"""
        seq = [self.current, self.current + self.step, self.current + 2 * self.step]
        self.output_line(f"[序列] {seq}")
        self.output(f"[输入] 请输入下一个值: ")

    def check_answer(self, guess):
        """检查答案并返回结果"""
        expected = self.current + 3 * self.step
        correct = guess == expected

        if correct:
            self.output_line(f"[正确] ✓ 下一个值是 {guess}")

            # 输出剩下2个数值
            next_1 = self.current + 3 * self.step
            next_2 = self.current + 4 * self.step
            self.output_line(f"[提示] 后续数值: {next_1}, {next_2}")

            # 更新 current
            self.current = self.current + 5 * self.step
        else:
            self.output_line(f"[错误] ✗ 正确答案是 {expected}")
            self.output_line("[重置] 重新开始...")
            self.current = 1
            self.step = 1

        self.output_line()  # 空行
        return correct

    def run(self):
        """运行交互测试"""
        self.output_line("=" * 50)
        self.output_line("交互式数值猜测测试 (Agent 友好版)")
        self.output_line("=" * 50)
        self.output_line()
        self.output_line("[规则] 我会输出递增的数值序列，请输入下一个可能的值。")
        self.output_line("[规则] 猜对则继续，直到数值大于某个值。")
        #self.output_line("[提示] Agent 发送消息时请确保包含换行符")
        self.output_line()

        while self.current <= self.max_value and self.running:
            self.show_sequence()
            # 需要 AI 交互时必须输出此关键词，供主程序（interactive_wrapper）检测
            self.output_line("<<CC_FN_INPUT_NEEDED>>")

            # 读取用户输入
            user_input = self.read_line()

            # 处理退出命令
            if user_input.lower() in ['exit', 'quit', 'q']:
                self.output_line("[退出] 收到退出命令")
                break

            try:
                guess = int(user_input)
                self.check_answer(guess)
            except ValueError:
                self.output_line(f"[错误] ✗ 无效输入: '{user_input}'")
                self.output_line("[重置] 重新开始...")
                self.output_line()
                self.current = 1
                self.step = 1

        if self.current > self.max_value:
            self.output_line("=" * 50)
            self.output_line("[完成] 任务完成！")
            self.output_line("=" * 50)
            self.output_line(f"[结果] 最终数值: {self.current}")


def main():
    test = InteractiveTest()
    test.run()


if __name__ == "__main__":
    main()