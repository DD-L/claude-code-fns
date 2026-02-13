# /fn 测试用例执行清单

基于项目内 **test_all_functions.ps1**、**test_chain.ps1**、**QUICK_START_TEST.md**、**functions/tests/README.md** 及 Cursor/Claude 历史会话中使用的评估 cases 整理。用于在 Cursor 或 Claude Code 中逐条执行并勾选记录。

**使用方式**：在聊天框输入对应命令，执行后在清单中勾选 `[ ]` → `[x]`，必要时填写「执行结果」列。

---

## 一、业务 Function（test_all_functions.ps1 正式用例）

### 1. task_orchestrator

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 1 | [ ] | `/fn task_orchestrator 请审查 test_data/sample_code.py 的安全性` | 路由到 code_review | |
| 2 | [ ] | `/fn task_orchestrator 修复 test_data 中的代码问题` | 路由到 fix_issues | |
| 3 | [ ] | `/fn task_orchestrator 运行测试验证代码` | 路由到 run_tests | |
| 4 | [ ] | `/fn task_orchestrator 这是一个普通任务` | 默认 _return | |

### 2. code_review

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 5 | [ ] | `/fn code_review test_data/sample_code.py security` | 安全审查，发现问题可触发 fix_issues | |
| 6 | [ ] | `/fn code_review test_data/sample_code.js performance` | 性能审查 | |
| 7 | [ ] | `/fn code_review test_data/ quality` | 质量审查整个目录 | |

### 3. fix_issues

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 8 | [ ] | `/fn fix_issues test_data/sample_code.py 中存在安全问题：使用 eval() 函数，应该替换为安全的解析方法` | 修复后可能触发 run_tests | |
| 9 | [ ] | `/fn fix_issues test_data/sample_code.js 中存在性能问题：应该使用 reduce 方法优化循环` | 修复性能问题 | |

### 4. run_tests

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 10 | [ ] | `/fn run_tests test_data/test_sample.py` | 运行 Python 测试 | |
| 11 | [ ] | `/fn run_tests test_data/test_sample.js` | 运行 JavaScript 测试 | |
| 12 | [ ] | `/fn run_tests test_data/` | 运行整个测试目录 | |

---

## 二、调用链 / 链式测试（test_chain.ps1）

用于验证 code_review → fix_issues → run_tests 完整链路。

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 13 | [ ] | `/fn code_review test_data/sample_code.py security` | 主链入口，应触发 fix_issues → run_tests | |
| 14 | [ ] | `/fn fix_issues test_data/sample_code.py 中存在安全问题：使用 eval() 函数，需要修复并运行测试验证` | 直接触发 fix_issues → run_tests | |
| 15 | [ ] | `/fn task_orchestrator 请审查 test_data/sample_code.py 的安全性，如果发现问题请修复并运行测试` | 经编排器路由到 code_review 并走完整链 | |

---

## 三、控制流 / 框架测试（functions/tests）

用于验证 switch、sequence、loop、recursion、tail_recursion 等行为；可选 `--session=<id>` 做并发或隔离。

### 3.1 分支 (test_branch)

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 16 | [ ] | `/fn tests/test_branch A --session=s1` | 分支 A，call 调用，栈增后返回 | |
| 17 | [ ] | `/fn tests/test_branch B --session=s2` | 分支 B，tail_call，栈深保持 1 | |
| 18 | [ ] | `/fn tests/test_branch C --session=s3` | 分支 C，直接返回 | |
| 19 | [ ] | `/fn tests/test_branch D --session=s4` | 默认分支，直接返回 | |

### 3.2 序列 (test_sequence)

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 20 | [ ] | `/fn tests/test_sequence hello` | seq_step1 → step2 → step3，$prev 传递 | |

### 3.3 循环 (test_loop)

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 21 | [ ] | `/fn tests/test_loop count=0 max=5` | 迭代 0–5，栈深恒为 1 | |

### 3.4 递归与尾递归

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 22 | [ ] | `/fn tests/test_recursion 5` | 栈深度增至 6 再返回 | |
| 23 | [ ] | `/fn tests/test_tail_recursion 5` | 栈深恒为 1（尾递归优化） | |

### 3.5 综合 (test_combined)

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 24 | [ ] | `/fn tests/test_combined mode=sequence count=3` | 序列模式 | |
| 25 | [ ] | `/fn tests/test_combined mode=loop count=5` | 循环模式 | |
| 26 | [ ] | `/fn tests/test_combined mode=recursion count=3` | 递归模式 | |
| 27 | [ ] | `/fn tests/test_combined mode=tail count=5` | 尾递归模式 | |

### 3.6 长任务

| 序号 | 执行 | 命令 | 预期 | 执行结果 |
|------|------|------|------|----------|
| 28 | [ ] | `/fn long_task n=0 total=20` | 长任务迭代，可测 stop hook / 续跑 | |

---

## 四、其他参考命令

| 序号 | 执行 | 命令 | 说明 |
|------|------|------|------|
| 29 | [ ] | `/fn route_a --n=3 --from=A` | fn.md 示例，路由/参数 | |
| 30 | [ ] | `/fn task_orchestrator 请审查 test_data/ 目录的代码质量` | 编排器审查整目录 | |

---

## 五、执行与审计说明

- **执行环境**：在 Cursor 或 Claude Code 聊天框直接输入上述命令；如需会话隔离，对 tests 用例使用 `--session=s1` 等。
- **中断续跑**：执行中断时可发送「继续」或使用 `/fn_continue`（见 .claude/commands/fn_continue.md）。
- **状态与日志**：
  - 会话栈：`scripts/states/<SessionID>.json`
  - Hook 调试：`scripts/states/.hook_debug.log`
- **审计维度**（与 thoughts/review_functions_execution.txt 一致）：功能正确性、栈与状态、是否走捷径、stop hook、工具调用、性能、是否符合 functions/* 定义。

**清单来源**：test_all_functions.ps1（$TestCases）、test_chain.ps1、QUICK_START_TEST.md、README_TEST.md、functions/tests/README.md、.claude/commands/fn.md。
