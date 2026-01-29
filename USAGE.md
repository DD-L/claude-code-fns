# Function-Skill 使用指南

## 概述

这是一个支持递归、序列、循环和完整调用栈管理的元技能框架。

## 快速开始

### 执行 function

```
/fn function_name arg1 arg2
```

Session ID 自动从环境变量获取，无需手动指定。

### 从中断恢复

```
/fn_continue
```

或指定特定会话：

```
/fn_continue --session=<uuid>
```

## 定义 Function

在 `functions/` 目录创建 JSON 文件：

### 基本 function

```json
{
  "name": "hello",
  "params": ["name"],
  "task": "输出问候语: Hello, $name!",
  "on_complete": {
    "type": "return"
  }
}
```

### 链式调用 (call)

```json
{
  "name": "step1",
  "task": "执行第一步",
  "on_complete": {
    "type": "call",
    "target": "step2",
    "args": {"data": "$output"}
  }
}
```

### 条件分支 (switch)

```json
{
  "name": "check",
  "params": ["value"],
  "task": "检查 $value 的状态",
  "on_complete": {
    "type": "switch",
    "conditions": [
      {"when": "需要修复", "call": "fix"},
      {"when": "正常", "type": "return"}
    ],
    "default": "_return"
  }
}
```

### 序列执行 (sequence)

按顺序执行多个函数，`$prev` 引用上一步输出：

```json
{
  "name": "pipeline",
  "params": ["data"],
  "task": "Bash(echo \"开始处理: $data\")",
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

### 循环执行 (loop)

重复执行直到条件不满足：

```json
{
  "name": "batch_process",
  "params": ["items", "index"],
  "task": "Bash(echo \"处理第 $index 项\")",
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

### 尾调用 (tail_call)

复用栈顶，栈深度不变：

```json
{
  "name": "countdown",
  "params": ["n"],
  "task": "输出: $n",
  "on_complete": {
    "type": "switch",
    "conditions": [
      {"when": "$n > 0", "tail_call": "countdown", "args": {"n": "$n - 1"}}
    ],
    "default": "_return"
  }
}
```

## on_complete 类型

| 类型 | 栈操作 | 说明 |
|------|--------|------|
| return | POP | 出栈返回 |
| call | PUSH | 入栈调用，完成后返回 |
| tail_call | REPLACE | 替换栈顶，不增加深度 |
| switch | - | 条件分支，选择一个动作 |
| sequence | 多次 PUSH | 语法糖：依次执行多个 call |
| loop | - | 语法糖：条件循环 |

## Session 机制

### Session ID 获取（按优先级）

1. 命令行参数 `--session=<id>`（推荐用于并发测试）
2. 环境变量 `$CC_SESSION_ID`（由 SessionStart hook 注入，如可用）
3. 如都不可用，使用固定值 `default`

### SessionStart Hook（可选）

如果 Claude Code 支持 `CLAUDE_ENV_FILE`，SessionStart hook 会自动注入 `$CC_SESSION_ID` 环境变量。
如不支持，请使用 `--session` 参数手动指定。

### Stop Hook

从 stdin 读取 `session_id`，精确匹配当前会话的状态文件

### 状态文件

路径: `scripts/states/<session_id>.json`

```json
{
  "status": "running",
  "stack": [
    {"function": "pipeline", "args": {"data": "test"}},
    {"function": "validate", "args": {"input": "test"}}
  ],
  "output": null
}
```

栈帧结构：
- `function`: 函数名
- `args`: 参数
- `return_to`: 返回点（可选，call 时使用）
- `output`: 函数输出（可选）

## 可靠性机制

| 机制 | 文件 | 作用 |
|------|------|------|
| SessionStart Hook | `.claude/settings.local.json` | 持久化 session_id |
| Stop Hook | `.claude/settings.local.json` | 停止前检查调用栈 |
| 状态追踪 | `scripts/states/<session_id>.json` | 记录完整栈信息 |
| 恢复命令 | `/fn_continue` | 从中断恢复 |

## 限制

- 栈深度：100
- 循环次数：max_iterations（默认 1000）

## 项目结构

```
.claude/
├── settings.local.json    # Hook 配置（SessionStart + Stop）
├── skills.md              # 元技能定义
└── commands/
    ├── fn.md              # /fn 命令
    └── fn_continue.md     # /fn_continue 命令

functions/
├── _schema.json           # JSON Schema
├── _builtins.json         # 内置 function
├── examples/              # 示例函数
│   ├── pipeline.json      # 序列示例
│   ├── batch_process.json # 循环示例
│   └── ...
└── ...                    # 你的 function

scripts/
├── session_start.ps1      # SessionStart Hook 脚本
├── check_chain.ps1        # Stop Hook 脚本
└── states/                # 运行时状态（每会话一个文件，以 UUID 命名）
```
