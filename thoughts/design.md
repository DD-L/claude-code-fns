我想在 claude code 中实现利用其 skill 实现任务的递归性，以便实现更复杂的决策图。

任务被拆解后，每一步暴露的内容都刚好合适。

比如：

可以是一个 skill 里有多个复杂步骤（决策图）， 也可以是 skill 递归的调用另外一个 skill 驱动整个任务进行。

我倾向 一个 skill 里有多个复杂步骤（决策图）。


一个方案别实践后效果不如意。

skills 中的 一个  SKILL.md 中有，一堆 md 的索引的形式


SKILL.md：
```
---
skills header
---

1.md ：<子流程描述>
2.md : <子流程描述>
3.md : <子流程描述>
...
```

1.md
```
- <定义当前步骤>
- <定义下一步骤>
```


2.md
```
- <定义当前步骤>
- <定义下一步骤>
```

...

以上方案被实践后，不容易，注意是当 子步骤或子技能 数量和复杂度达到一定程度后，它将不能按预期正确工作，而且总是提前终止。
-------------


我还有两个思路：


## 思路一：

Skill 是可以调用脚本的，将 md 的提示词用脚本包装下

SKILL.md：
```
---
skills header
---

1.sh ：<什么条件下调用此脚本, 支持传参>
2.sh : <什么条件下调用此脚本，支持传参>
3.sh : <什么条件下调用此脚本，支持传参>
...
```

每个脚本中，都至少这些内容， 比如

1.sh

```
# 上一步的状态
# 当前子任务的定义
# 什么条件下调用下一个脚本
#
```

这个方案中 脚本支持传参和输出，传参可以是上一步的状态信息或总结信息，输出的内容可以被 Agent(claudecode) 读取作为当前步骤或者并包含驱动下一步骤的提示词。

这个提示词中定义了
- 当前任务定义，驱动 Agent(claudecode) 执行当前子任务
- 什么条件下调用下一个脚本， 以触发任务执行的递归性（决策图）

## 思路二：

将思路一的脚本内容，换成 （启动新的 Claude 进程） 

```
$ cat "提示词" | claude
```

提示词中包含

- 上一步的状态
- 当前子任务的定义
- 什么条件下调用下一个 claude 进程

-----

我倾向 思路一， 如果 思路一 不能很好的工作，那么就尝试 思路二。

请帮我
- 评估这些思路的可行性
- 你有没有更好的实践方式


=======


现在我有一个新的想法，要实现递归性，在 claude code 中抽象出 function 才是最好的途径: `function-skill`。

参考编程语言的 function， 即允许输入和输出，以及 function 中可以调用其它 function。

简化数据类型设计，数据类型都抽象为提示词文本

提示词中可以是
- 任务状态
- 下一步计划
等等

function 定义为：当前子任务流程


function 也有名字，也有匿名 Function，以便被其它 function 调用。

【暂缓】未来还还要支持 lambda 演算，高阶函数、柯里化和反柯里化等高级特性。


可靠性是它的特点，不会出现意外中止的情况，只要函数调用不中止，它就可以按照预想的继续工作，除非资源被耗尽（比如类似函数调用爆栈）

为了强调可靠性，可利用 claude code 一切可用的技术，(需查询 Claude Code 文档，甚至其 SDK 文档)
比如 
1. stop-hook 技术（类似于 ralph-loop的实现）, 检查函数运行状态，如果流程没有结束，则需要强制 claude code 继续,
2. skills 中的脚本调用
  1. 驱动下个步骤
  2. 驱动 function 调用
  3. 甚至可以用 claude code 的无头模式驱动下一个任务 `cat "下个任务" | claude -p`
3. **遵循渐进式暴露原则**，每次只暴露一个 function, 即执行函数栈仅有一个函数栈顶。


能力展示：

### 可以调用 claude code 的内置指令：

function claude_code_context_compact() {
   "task"： "执行 claude code 的上下文压缩",
   "return": ""
}


function claude_code_context_clear() {
   "task": "执行 claude code 的上下文清理"，
   "return": ""
}

### 可以调用其它函数

function task_c(input) {
   CALL claude_code_context_clear()
   PROCESS input
}

function task_a(input) {
   switch "$input":
          WHEN condition1 CALL claude_code_context_compact()
          WHEN condition2 CALL claude_code_context_clear()
          WHEN condition3 CALL task_b($input + "balabala" + "balabala")
          DEFAULT call task_c()
   "return": "balabala"
}


语言层的设计可以被放到阶段二，现在暂时以 json 配置的方式抽象 function


================


这是一个面向 claude code 的执行框架，利用 [claude code](https://code.claude.com/docs/en/overview)  中一切可利用的资源，包括不限于：
- [skill 技术](https://code.claude.com/docs/en/skills)
- [subagent](https://code.claude.com/docs/en/sub-agents)
- [Hooks 技术](https://code.claude.com/docs/en/hooks-guide)
- 上下文管理技术（如 clear 和 compact）
- [Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) 或者 利用 `context7 MCP` 查询相关接口
- [Plugins](https://code.claude.com/docs/en/plugins) 
- [best practices](https://code.claude.com/docs/en/best-practices)

来满足以下目标：

1. **可靠性保证，被调用的函数一定会被正确执行**
  - 利用包括 stop-hook 和 Agent SDK 在内的所有可利用的技术保证其运行的可靠性
2. 函数体定义支持分支、序列、循环和递归
- 分支：
```
{
  "name": "route_c",
  "description": "动态路由函数 C - 根据 n 和 from 决定路径",
  "params": ["n", "from"],
  "task": "使用 echo 输出: [C] n=$n, from=$from",
  "tools": ["Bash"],
  "on_complete": {
    "type": "switch",
    "conditions": [
      {
        "when": "$n <= 0",
        "call": "_return"
      },
      {
        "when": "$from == 'A'",
        "tail_call": "route_b",
        "args": {"n": "$n - 1", "from": "C"}
      },
      {
        "when": "$from == 'B'",
        "tail_call": "route_a",
        "args": {"n": "$n - 2"}
      }
    ],
    "default": "route_a",
    "default_args": {"n": "$n - 1"}
  }
}
```

- 递归：

```
{
  "name": "grow",
  "description": "Demonstrates stack growth using regular call (not tail_call). Stack depth increases with each call.",
  "params": ["n"],
  "task": "Bash(echo \"[grow] n=$n, stack will grow...\")",
  "tools": ["Bash"],
  "on_complete": {
    "type": "switch",
    "conditions": [
      {
        "when": "$n <= 0",
        "type": "return"
      },
      {
        "when": "$n > 0",
        "call": "grow",
        "args": {"n": "$n - 1"}
      }
    ],
    "default": "_return"
  }
}
```

- 序列（Sequence）：

```json
{
  "name": "pipeline",
  "description": "数据处理管道 - 按顺序执行多个步骤",
  "params": ["data"],
  "task": "Bash(echo \"[pipeline] 开始处理: $data\")",
  "tools": ["Bash"],
  "on_complete": {
    "type": "sequence",
    "steps": [
      {"call": "validate", "args": {"input": "$data"}},
      {"call": "transform", "args": {"input": "$prev"}},
      {"call": "save", "args": {"input": "$prev"}}
    ]
  }
}
```

序列执行规则：
- 按顺序执行 steps 中的每个步骤
- `$prev` 引用上一步的输出
- 所有步骤完成后自动 return

- 循环（Loop）：

```json
{
  "name": "batch_process",
  "description": "批量处理 - 循环直到条件不满足",
  "params": ["items", "index"],
  "task": "Bash(echo \"[batch] 处理第 $index 项\")",
  "tools": ["Bash"],
  "on_complete": {
    "type": "loop",
    "while": "$index < $items",
    "do": {
      "tail_call": "batch_process",
      "args": {"items": "$items", "index": "$index + 1"}
    },
    "max_iterations": 100
  }
}
```

循环执行规则：
- 检查 while 条件
- 条件为真则执行 do（**只能用 tail_call**，栈深度不增长）
- 用 `$output` 传递上次迭代的输出作为下次输入
- 超过 max_iterations 强制退出

支持传参和传出，参数和返回值可有可无，返回值可以作为序列中的下一个函数的输入参数


3. 支持 call, tail_call，return，switch，sequence，loop

```
"type": "return | call | tail_call | switch | sequence | loop"
```

4. 主会话执行 function 中的 task, 其它的都应该在 subagent 中执行。确保当前这套机制基本不占主会话的上下文
  - 要注意 subagent 与 主会话的交互细节

5. functions 中的函数不应该是平铺状态，应该有命名空间或 package 的概念，可以与目录层次结构相呼应，但要解决名字冲突的问题。利用相对路径，就近调用。
  - 注意函数调用的静态分发，必须用脚本算法写死，不能利用大模型的能力去分发
  - **详细设计见下方 [静态函数分发设计](#静态函数分发设计)**

6. state.json - 考虑设计会话概念，多个会话可以并行执行同一任务或不同任务。
  - 确保仅仅 function 中的 task 才是在主会话完成，其它都应该在 subagent 中完成

7. 支持对主会话上下文的显式和隐式 clear 和 compact

8. **确保此框架的提示词精简且可靠**

9. 当前还在原型阶段可以引入破坏性接口，不必考虑任何兼容性问题

10. state.json 中必须保存当前完整的栈信息，它是此框架的可靠性的保证

11. 编写工具使“栈操作”稳定和可靠，此工具修改更新，完要有输出反馈（当前状态），以便 Agent 可以审视自己的操作是否正确。

12. [低优先级] json 还是比较浪费 token, 可以考虑换成 TOON 
  - https://toonformat.dev/
  - https://github.com/toon-format/toon
  - https://toonformat.dev/guide/format-overview
  - https://toonformat.dev/reference/syntax-cheatsheet
  - https://toonformat.dev/reference/api

13. 我找到了解决会话id持久化的方法了 （当前暂时选用方案一）

方案一：
但是只能在 powershell 中运行的 claude code 才有效：

处理方式： 不需要依赖 startup hook。 每次在 fn 开始执行时，先初始化环境。通过 Bash(echo "WT_SESSION=$WT_SESSION") 获取当前 Windows Terminal 的会话 ID， 然后在 scripts/states/ 生产对应 id 的 state.json; 在 stop -hook 脚本中，先获取当前 当前 Windows Terminal 的会话 ID， 找到对应的 scripts/states/ ID state.json， 判定是否为空栈状态，如果不是则强制继续执行，不能停止。注意不能检测其它 session 的 state.json，因为其它 session 可能还在其它 claude code session 执行中，不能干扰到其它 会话。

方案二（不成熟，但是诱人的是：可在 powershell/linux 环境中兼容）：

我注意到 .hook_debug.log 中可以获取 CLAUDE_ENV_FILE ，这个路径下包含 ~/.claude/session-env/sesssion-id 信息，那么可以在  startup hook 中获取此 claude code sesssion id （然后记下来（记忆到大模型当前上下文窗口）？） 
但是在  stop-hook 脚本中如何获取当前控制台对应的 sesssion-id 是个难题，这个得想办法

---

## 静态函数分发设计

### 1. 命名空间规则

函数的**全限定名 (FQN)** 由目录路径和函数名组成：

```
functions/
├── route_a.json          # FQN: route_a (根命名空间)
├── route_b.json          # FQN: route_b
├── examples/
│   ├── pipeline.json     # FQN: examples/pipeline
│   ├── validate.json     # FQN: examples/validate
│   └── transform.json    # FQN: examples/transform
└── tests/
    ├── seq_step1.json    # FQN: tests/seq_step1
    └── test_sequence.json # FQN: tests/test_sequence
```

### 2. 函数引用语法

| 语法 | 含义 | 示例 |
|------|------|------|
| `name` | 短名，就近查找 | `validate` |
| `ns/name` | 绝对路径 (从 functions/ 开始) | `examples/validate` |
| `./name` | 显式当前目录 | `./validate` |
| `../name` | 显式上级目录 | `../route_a` |

### 3. 解析算法 (就近原则)

```
resolve_function(caller_fqn, target_ref):
    
    # 1. 绝对路径 (包含 / 但不以 . 开头)
    if '/' in target_ref and not target_ref.startswith('.'):
        path = "functions/" + target_ref + ".json"
        if exists(path):
            return path
        else:
            ERROR: "Function not found: {target_ref}"
    
    # 2. 显式相对路径
    if target_ref.startswith('./') or target_ref.startswith('../'):
        caller_dir = dirname(caller_fqn)
        resolved = normalize(caller_dir + '/' + target_ref)
        path = "functions/" + resolved + ".json"
        if exists(path):
            return path
        else:
            ERROR: "Function not found: {target_ref} (from {caller_fqn})"
    
    # 3. 短名就近查找 (向上冒泡)
    caller_dir = dirname(caller_fqn)  # e.g., "tests" for "tests/test_sequence"
    
    # 从调用者所在目录开始，向上查找
    search_dirs = []
    while caller_dir:
        search_dirs.append(caller_dir)
        caller_dir = dirname(caller_dir)
    search_dirs.append("")  # 根目录
    
    for dir in search_dirs:
        if dir:
            path = "functions/" + dir + "/" + target_ref + ".json"
        else:
            path = "functions/" + target_ref + ".json"
        
        if exists(path):
            return path
    
    ERROR: "Function not found: {target_ref} (searched from {caller_fqn})"
```

### 4. 解析示例

假设当前目录结构：
```
functions/
├── validate.json           # 根级 validate
├── examples/
│   ├── pipeline.json
│   └── validate.json       # examples 级 validate
└── tests/
    ├── test_sequence.json
    └── seq_step1.json
```

| 调用者 | 引用 | 解析结果 |
|--------|------|----------|
| `tests/test_sequence` | `seq_step1` | `tests/seq_step1` ✓ 同目录 |
| `tests/test_sequence` | `validate` | `validate` ✓ 冒泡到根 |
| `tests/test_sequence` | `examples/validate` | `examples/validate` ✓ 绝对路径 |
| `examples/pipeline` | `validate` | `examples/validate` ✓ 同目录优先 |
| `examples/pipeline` | `../route_a` | `route_a` ✓ 显式上级 |
| `examples/pipeline` | `tests/seq_step1` | `tests/seq_step1` ✓ 绝对路径 |

### 5. 名字冲突处理

**就近原则自然解决**：同名函数优先匹配最近的。

如果 `examples/` 和根目录都有 `validate.json`：
- 从 `examples/pipeline` 调用 `validate` → 匹配 `examples/validate`
- 从 `tests/test_sequence` 调用 `validate` → 匹配根级 `validate`
- 如果 `tests/` 需要调用 `examples/validate` → 使用绝对路径 `examples/validate`

### 6. 索引文件 (_index.json) - 开发工具 （仅用于函数开发时静态分析和冲突检测）

**注意：运行时分发不依赖此索引**，解析器直接扫描文件系统。

索引文件用于开发时的静态分析：
- 查看所有函数列表
- 检测名字冲突
- `check_calls.py` 用它遍历函数进行验证

生成命令：`python scripts/build_index.py`

```json
{
  "_generated": "2025-01-28T10:00:00Z",
  "functions": {
    "route_a": {"path": "route_a.json", "fqn": "route_a"},
    "examples/validate": {"path": "examples/validate.json", "fqn": "examples/validate"}
  },
  "by_short_name": {
    "validate": ["validate", "examples/validate"]  // 冲突检测
  },
  "stats": {
    "conflicts": {"validate": ["validate", "examples/validate"]}
  }
}
```

### 7. Schema 更新

在函数定义中，`call`/`tail_call` 目标支持所有引用语法：

```json
{
  "name": "test_sequence",
  "on_complete": {
    "type": "sequence",
    "steps": [
      {"call": "seq_step1"},           // 短名，就近查找
      {"call": "./seq_step2"},         // 显式当前目录
      {"call": "examples/validate"},   // 绝对路径
      {"tail_call": "../route_a"}      // 上级目录
    ]
  }
}
```

### 8. 实现脚本

需要实现以下脚本：

1. **`scripts/resolve_fn.py`** - 函数解析器
   - 输入: caller_fqn, target_ref
   - 输出: 解析后的完整路径或错误

2. **`scripts/build_index.py`** - 索引构建器
   - 扫描 functions/ 目录
   - 生成 `functions/_index.json`

3. **`scripts/resolve_fn.ps1`** - PowerShell 版本 (可选)

### 9. 栈帧中的函数标识

状态文件中使用 FQN 标识函数：

```json
{
  "status": "running",
  "stack": [
    {
      "function": "tests/test_sequence",  // 使用 FQN
      "args": {"input": "hello"},
      "step_index": 1
    },
    {
      "function": "tests/seq_step1",
      "args": {"data": "hello"}
    }
  ]
}
```

### 10. 静态验证

提供 `check_calls.py` 脚本静态验证所有函数调用是否合法：

```bash
python scripts/check_calls.py

# 输出:
# ✓ tests/test_sequence -> seq_step1 => tests/seq_step1
# ✓ tests/test_sequence -> seq_step2 => tests/seq_step2
# ✓ examples/pipeline -> validate => examples/validate
# ✗ examples/pipeline -> unknown_fn => NOT FOUND
```

---

## Subagent 架构设计（采纳方案）

### 1. 架构概览：混合模式

采用混合模式架构，平衡可靠性和 token 成本：

```
┌─────────────────────────────────────────────────────────────┐
│ 主会话 (Main Session)                                        │
│                                                              │
│  fn-controller subagent (可 resume):                        │
│    - 负责: 栈操作、函数解析、控制流                         │
│    - 通过 resume 复用（节省 token）                         │
│    - 当上下文达到阈值时自动 compact                          │
│                                                              │
│  task 执行策略:                                              │
│    - task.execute_in == "main":                             │
│        主会话直接执行（默认）                                │
│                                                              │
│    - task.execute_in == "subagent":                         │
│        主会话调用临时 task-executor subagent                │
│        执行后 subagent 结束，结果返回主会话                  │
│        主会话通过 resume 通知 controller 继续               │
│                                                              │
│  可靠性保障:                                                 │
│    - stop-hook: 检查 state.json，非空栈则强制继续           │
│    - 状态完全持久化在 state.json                            │
│    - 任何崩溃后可从 state.json 恢复                         │
└─────────────────────────────────────────────────────────────┘
```

### 2. 执行分工

| 组件 | 执行位置 | 说明 |
|------|---------|------|
| function 中的 task | 主会话（默认）或 subagent（可配置） | 实际业务逻辑 |
| 栈操作 (push/pop/tail_call) | fn-controller subagent | 保持主会话干净 |
| 函数解析和分发 | fn-controller subagent | 静态分发逻辑 |
| 控制流处理 (switch/sequence/loop) | fn-controller subagent | 流程控制 |
| state.json 读写 | fn-controller subagent | 状态管理 |

### 3. task.execute_in 字段设计

在 function 定义中新增 `execute_in` 字段，控制 task 的执行位置：

```json
{
  "name": "complex_task",
  "description": "需要在 subagent 中执行的复杂任务",
  "params": ["input"],
  "task": {
    "prompt": "处理输入数据：$input",
    "tools": ["Bash", "Read", "Edit"],
    "execute_in": "subagent@haiku"
  },
  "on_complete": {
    "type": "return"
  }
}
```

**execute_in 语法：**

| 值 | 含义 |
|----|------|
| `"main"` | 在主会话中执行（默认值） |
| `"subagent"` | 在临时 subagent 中执行，使用默认模型 |
| `"subagent@haiku"` | 在临时 subagent 中执行，使用 haiku 模型 |
| `"subagent@sonnet"` | 在临时 subagent 中执行，使用 sonnet 模型 |
| `"subagent@opus"` | 在临时 subagent 中执行，使用 opus 模型 |

**简化写法（向后兼容）：**

如果 task 是字符串而非对象，等价于 `execute_in: "main"`：

```json
{
  "name": "simple_task",
  "task": "echo 'Hello World'",
  "tools": ["Bash"]
}
```

### 4. fn-controller subagent 配置

创建 `.claude/agents/fn-controller.md`：

```markdown
---
name: fn-controller
description: Function execution framework controller. Manages call stack, function dispatch, and control flow. Use proactively for all cc_function framework operations.
tools: Read, Bash, Glob, Grep
model: haiku
permissionMode: acceptEdits
---

You are the function execution controller for the cc_function framework.

## Responsibilities

1. **State Management**: Read and update `scripts/states/{session_id}.json`
2. **Function Resolution**: Use `scripts/resolve_fn.ps1` or `scripts/resolve_fn.py` for static function dispatch
3. **Stack Operations**: Perform push, pop, tail_call operations
4. **Control Flow**: Handle switch, sequence, loop constructs
5. **Agent ID Persistence**: Save your agent ID to state.json for resume

## Execution Protocol

When invoked:
1. Read current state from state.json
2. Determine next action based on stack top
3. Perform required stack operations
4. Update state.json with new state
5. Return task definition for main session to execute

## Output Format

Always output a JSON response:
```json
{
  "action": "execute_task | complete | error",
  "task": {
    "prompt": "...",
    "tools": ["Bash"],
    "execute_in": "main"
  },
  "state": {
    "stack_depth": 1,
    "current_function": "route_a"
  }
}
```

## Critical Rules

- NEVER execute tasks yourself - return task definitions only
- ALWAYS use scripts for stack operations
- ALWAYS auto-obtain session_id via `echo "WT_SESSION=$WT_SESSION"`

### 5. Resume 机制验证（历史记录）

**Resume 机制验证结论：**

| 方式 | 结果 | 说明 |
|------|------|------|
| 显式 "Resume agent {id}" | ❌ 不可靠 | 经常失败，Invalid tool parameters |
| 模糊 "Continue that task" | ❌ 不可靠 | 失败或创建新 agent |

**已知问题（Claude Code 2026.01）：**
- Agent transcripts 不存储 user prompts，导致 resume 丢失上下文
- Agent ID 在 CLI 输出中不可靠显示
- Resume 功能无法按预期工作

**架构决策：无 Resume 模式**

由于 Resume 机制不可靠，本框架采用"每次新建 subagent + state.json 持久化"策略：
1. **不依赖 resume**：每次调用都创建新的 fn-controller subagent
2. **状态持久化**：所有状态通过 state.json 保持
3. **session_id 由 fn-controller 自动获取**：主会话不处理 session

**session_id 获取规则（fn-controller 内部）**

```bash
echo "WT_SESSION=$WT_SESSION"
```

⚠️ **禁止**：使用 `powershell -Command` 转发此命令（会导致环境变量丢失）

**验证结论**：WT_SESSION 环境变量在 subagent 中可访问，与主会话相同

**state.json 扩展：**

```json
{
  "session_id": "WT_SESSION_xxx",
  "status": "running",
  "stack": [
    {
      "function": "tests/test_sequence",
      "args": {"input": "hello"},
      "step_index": 1
    }
  ],
  "last_updated": "2025-01-30T10:00:00Z"
}
```

### 6. 执行流程详解

```
┌──────────────────────────────────────────────────────────────────────┐
│ 用户调用: fn route_a --n=3                                           │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 主会话: 初始化                                                        │
│   1. 解析用户命令参数                                                 │
│   2. 调用 fn-controller subagent：                                   │
│      operation=start, function=route_a, args={n:3}                   │
│      (session_id 可选传递，fn-controller 可自动获取 WT_SESSION)      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ fn-controller subagent:                                              │
│   1. 读取/创建 state.json                                            │
│   2. 解析函数 route_a                                                │
│   3. 将 route_a 压入栈                                               │
│   4. 返回 task 定义                                                   │
│   (agent_id 由系统自动包含在 Task 工具返回中)                        │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 主会话:                                                              │
│   1. 收到 task 定义                                                  │
│   2. 根据 execute_in 决定执行位置                                    │
│      - "main": 直接执行                                              │
│      - "subagent": 调用临时 task-executor subagent                  │
│   3. 执行完成后，**新建** fn-controller subagent（不 resume）:       │
│      operation=continue, task_result="执行结果摘要"                   │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ fn-controller subagent (新建，从 state.json 恢复状态):               │
│   1. 读取 state.json                                                 │
│   2. 处理 on_complete                                                │
│   3. 根据条件决定下一步 (switch/call/return)                         │
│   4. 更新栈状态                                                       │
│   5. 返回下一个 task 或标记完成                                       │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                            [循环直到栈空]
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 主会话: 完成                                                         │
│   - 栈空，执行结束                                                   │
│   - stop-hook 检测到空栈，允许停止                                   │
└──────────────────────────────────────────────────────────────────────┘
```### 7. stop-hook 与 Agent ID 协作

stop-hook 脚本需要更新，支持 resume controller：

```powershell
# scripts/stop_hook.ps1 (伪代码)

$sessionId = $env:WT_SESSION
$statePath = "scripts/states/$sessionId.json"

if (Test-Path $statePath) {
    $state = Get-Content $statePath | ConvertFrom-Json
    
    if ($state.stack.Count -gt 0) {
        # 栈非空，需要继续执行
        Write-Output @"
[cc_function] Stack is not empty. Continuing execution...

Call fn-controller subagent with operation=continue to process the function stack.
Current stack depth: $($state.stack.Count)
Top function: $($state.stack[-1].function)
"@
    }
    # 栈空则不输出，允许正常停止
}
```

### 8. 技术限制与应对

| 限制 | 影响 | 应对策略 |
|-----|------|---------|
| Subagent 不能 spawn subagent | 无法在 subagent 内部再调用 subagent | 所有 subagent 调用必须由主会话发起 |
| stop-hook 只能输出提示文本 | 不能直接调用 API | 输出提示词让 Claude 调用 fn-controller |

---

## 内置函数设计（_clear 和 _compact）

### 设计状态：已设计，暂不实现

### 1. _clear 内置函数

**效果：** 等同于交互式 `/clear` 命令

**实现方案：** 新会话 + 栈状态持久化

```json
{
  "_clear": {
    "description": "清理主会话上下文",
    "implementation": "new_session",
    "mechanism": "保存当前栈状态到 state.json，启动新 claude 进程，新进程读取 state.json 继续执行"
  }
}
```

**执行流程：**
1. 将当前栈状态完整保存到 state.json
2. 通过 stop-hook 或脚本触发新 claude 进程
3. 新进程启动后读取 state.json，恢复执行

### 2. _compact 内置函数

**效果：** 等同于交互式 `/compact` 命令

**实现方案：** 利用 subagent 独立上下文 + auto-compaction

```json
{
  "_compact": {
    "description": "压缩主会话上下文",
    "implementation": "subagent_isolation",
    "mechanism": "将后续操作转移到 subagent 执行，利用 subagent 的 auto-compaction 机制"
  }
}
```

**说明：**
- Subagent 支持 auto-compaction（~95% 容量时自动触发）
- 可通过 `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` 环境变量调整阈值
- 实现隐式 compact 效果

### 3. 显式与隐式上下文管理

| 类型 | 触发方式 | 效果 |
|------|---------|------|
| 显式 _clear | 函数调用 `_clear()` | 完全清理上下文，启动新会话 |
| 显式 _compact | 函数调用 `_compact()` | 压缩当前上下文 |
| 隐式 compact | subagent auto-compaction | 自动压缩 subagent 上下文 |
| 隐式隔离 | execute_in: "subagent" | task 在独立上下文执行，不污染主会话 |

---

## Schema 更新汇总

### function.json 扩展

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string" },
    "params": { "type": "array", "items": { "type": "string" } },
    "task": {
      "oneOf": [
        { "type": "string" },
        {
          "type": "object",
          "properties": {
            "prompt": { "type": "string" },
            "tools": { "type": "array", "items": { "type": "string" } },
            "execute_in": {
              "type": "string",
              "pattern": "^(main|subagent(@(haiku|sonnet|opus))?)$",
              "default": "main"
            }
          },
          "required": ["prompt"]
        }
      ]
    },
    "tools": { "type": "array", "items": { "type": "string" } },
    "on_complete": { "$ref": "#/definitions/on_complete" }
  }
}
```

### state.json 扩展

```json
{
  "session_id": "string",
  "status": "idle | running | error",
  "stack": [
    {
      "function": "string (FQN)",
      "args": { "key": "value" },
      "step_index": "number (for sequence)",
      "loop_iteration": "number (for loop)",
      "return_value": "any"
    }
  ],
  "last_updated": "ISO8601 timestamp",
  "error": "string | null"
}
```
