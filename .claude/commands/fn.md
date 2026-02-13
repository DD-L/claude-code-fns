# /fn - Function Executor

## 用法
```
/fn <function_name> [args...]
```

## 架构概览

```
主会话 (解析参数 + 执行 task)
    │
    ├─→ fn-controller subagent (start <function> args...)
    │       ↓ 返回 [TASK]
    ├─→ 执行 task (主会话或 subagent)
    │       ↓ 执行完成
    └─→ fn-controller (continue task_result=...) → 循环直到 [COMPLETE]
```

## 执行流程

### 阶段 1: 解析参数

```
/fn route_a --n=3 --from=A
→ function: "route_a", args: n=3 from=A
```

### 阶段 2: 调用 fn-controller subagent

```
Task(subagent_type='fn-controller', prompt='start route_a n=3 from=A')
```

**返回格式**：
```
[TASK]
prompt: Execute: Bash(...)
execute_in: main
resume_next: true
```

### 阶段 3: 执行 Task

根据 `execute_in` 决定执行位置：

| execute_in | 执行方式 |
|------------|---------|
| `main` (默认) | 主会话直接执行 prompt |
| `subagent` | 调用临时 subagent 执行 |
| `subagent@<model>` | 指定模型执行 |

### 阶段 4: 继续执行

根据 `resume_next` 决定复用策略：
```
resume_next=true  → Task(resume=<agent_id>, prompt='continue task_result=...')
resume_next=false → Task(subagent_type='fn-controller', prompt='continue task_result=...')
```

循环阶段 3-4 直到返回 `[COMPLETE]`

### 阶段 5: 完成

收到 `[COMPLETE]` 时输出 result 字段内容。

## ❗关键规则

1. **resume_next 混合方案**：根据返回值决定复用或新建 subagent
2. **主会话职责**：解析参数 + 执行 task + 管理 agent_id
3. **状态持久化**：通过 state.json 保持栈状态

## 错误处理

| 输出 | 处理 |
|-----|------|
| `[ERROR]` | 输出错误，用 `/fn_continue` 恢复 |

$ARGUMENTS
