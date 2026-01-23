# Meta Function Skill 使用指南

## 概述

这是一个轻量级的 "元 Skill" 框架，让你可以通过 JSON 配置定义可复用、可组合的 function-skill。

## 核心理念

```
┌─────────────────────────────────────────────────────────┐
│                  Meta Function Skill                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   JSON 配置  →  /fn 命令解析  →  任务执行  →  决策路由   │
│       ↓              ↓              ↓           ↓       │
│   functions/    .claude/       Claude      on_complete  │
│   *.json        commands/      执行任务    call/switch  │
│                 fn.md                      /return      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 使用内置 function

在 Claude Code 中直接使用 Slash Command：

```
/fn code_review src/ security
```

### 2. 定义自己的 function

创建 `functions/my_function.json`：

```json
{
  "name": "my_function",
  "description": "我的自定义 function",
  "task": "执行某个任务...",
  "on_complete": {
    "type": "return"
  }
}
```

### 3. 通过脚本启动（headless 模式）

```powershell
# Windows
.\scripts\run_function.ps1 code_review src/ quality

# Unix
./scripts/run_function.sh code_review src/ quality
```

## Function 定义详解

### 基础结构

```json
{
  "name": "function_name",      // 必填：唯一名称
  "description": "描述",        // 推荐：说明 function 用途
  "task": "任务提示词",         // 必填：告诉 Claude 要做什么
  "on_complete": { ... }        // 可选：完成后的行为
}
```

### on_complete 类型

#### 1. return - 返回结果

```json
{
  "on_complete": {
    "type": "return"
  }
}
```

#### 2. call - 调用下一个 function

```json
{
  "on_complete": {
    "type": "call",
    "target": "next_function",
    "pass_output": true
  }
}
```

#### 3. switch - 条件分支

```json
{
  "on_complete": {
    "type": "switch",
    "conditions": [
      {"when": "条件A", "call": "function_a"},
      {"when": "条件B", "call": "function_b"}
    ],
    "default": "_return"
  }
}
```

## 内置 Function

| 名称 | 说明 | 对应操作 |
|------|------|----------|
| `_compact` | 压缩上下文 | `/compact` |
| `_clear` | 清理上下文 | `/clear` |
| `_return` | 结束调用链 | 终止执行 |

## 可靠性保障

### 1. 强制链式执行

`/fn` 命令要求 Claude 在同一响应中完成整个调用链，不允许中途停止。

### 2. 状态追踪

每个步骤都会更新 `scripts/state.json`：

```json
{
  "status": "running",
  "current_function": "fix_issues",
  "completed_functions": ["code_review"],
  "last_update": "2024-01-01T12:00:00Z"
}
```

### 3. 自动驱动脚本（推荐）

使用 auto_drive 脚本启动 function，它会监控状态并在需要时自动发送继续命令：

```powershell
# Windows - 自动驱动模式
.\scripts\auto_drive.ps1 -Function "code_review" -Input "src/ security"

# Unix
./scripts/auto_drive.sh code_review src/ security
```

### 4. 手动恢复

如果执行中断，可以使用恢复命令：

```
/continue
```

或使用驱动脚本：

```powershell
.\scripts\drive.ps1
```

### 5. 渐进式暴露

通过 `tools` 字段限制每个 function 可用的工具：

```json
{
  "name": "read_only_review",
  "task": "只读审查代码",
  "tools": ["Read", "Grep", "Glob"]
}
```

### 6. 防止无限循环

通过 `max_iterations` 限制循环次数：

```json
{
  "name": "retry_task",
  "max_iterations": 3
}
```

## 示例工作流

### 代码审查 → 修复 → 测试

```
/fn code_review src/

执行流程：
1. code_review 分析代码
2. 发现问题 → 自动调用 fix_issues
3. 修复涉及核心逻辑 → 自动调用 run_tests  
4. 测试通过 → 返回结果
```

### 智能任务路由

```
/fn task_orchestrator "帮我检查 api/ 目录的安全性"

执行流程：
1. task_orchestrator 分析意图
2. 识别为代码审查任务
3. 自动调用 code_review api/ security
```

## 项目结构

```
.
├── .claude/
│   ├── skills.md           # 元 skill 定义
│   └── commands/
│       └── fn.md           # /fn 命令定义
├── functions/
│   ├── _schema.json        # JSON Schema
│   ├── _builtins.json      # 内置 function
│   ├── code_review.json    # 示例：代码审查
│   ├── fix_issues.json     # 示例：问题修复
│   ├── run_tests.json      # 示例：运行测试
│   └── task_orchestrator.json  # 示例：任务编排
├── scripts/
│   ├── drive.sh/.ps1       # 驱动脚本
│   └── run_function.sh/.ps1    # 启动脚本
└── USAGE.md                # 本文档
```

## 对比 design.md 需求

| 需求 | 实现方式 |
|------|----------|
| function 输入/输出 | input_hint + output_hint + pass_output |
| function 调用 function | on_complete.call + on_complete.switch |
| 数据类型为提示词文本 | 所有字段都是字符串 |
| 调用内置指令 | _compact, _clear 内置 function |
| stop-hook 可靠性 | drive.sh/ps1 脚本 |
| 渐进式暴露 | tools 字段限制 |
| JSON 配置 | functions/*.json |

## 后续扩展

当前是 "阶段一" 实现，未来可以：

1. **DSL 语法**：设计更友好的 function 定义语言
2. **Lambda 支持**：匿名 function、高阶函数
3. **更多内置 function**：如 `_retry`, `_parallel` 等
4. **执行追踪**：记录 function 调用链和状态
