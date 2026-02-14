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
    ├─→ 执行 task (主会话 main 或其它 subagent, 由 execute_in 字段决定)
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

主会话执行 [TASK] 中的 prompt（task 由 function 的 task 字段定义，可能是 Bash 或其他工具）。按 `execute_in` 决定执行位置：

| execute_in | 执行方式 |
|------------|---------|
| `main` | 主会话直接执行 prompt |
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

1. **主会话职责**：解析参数；监控 fn-controller 执行，必要时向 fn-controller 索取下一步 [TASK]；收到 [TASK] 后由主会话执行 prompt（按 execute_in）；管理 agent_id。
2. **resume_next**：按返回值复用或新建 fn-controller subagent。
3. **状态**：通过 state.json 持久化。

## 错误处理

| 输出 | 处理 |
|-----|------|
| `[ERROR]` | 输出错误，用 `/fn_continue` 恢复 |

$ARGUMENTS
