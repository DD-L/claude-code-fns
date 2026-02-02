# /fn - Function Executor

## 用法
```
/fn <function_name> [args...]
```

## 架构概览

```
主会话 (仅负责解析参数和 task 执行)
    │
    ├─→ fn-controller subagent (session 获取、栈操作、函数解析、控制流)
    │       ↓ 返回 task 定义
    ├─→ 执行 task (主会话或 task-executor subagent)
    │       ↓ 执行完成
    └─→ 新建 fn-controller (operation=continue) → 循环直到栈空
```

## 执行流程

### 阶段 1: 解析参数

```
/fn route_a --n=3 --from=A
→ function_name: "route_a"
→ args: {n: "3", from: "A"}
```

### 阶段 2: 调用 fn-controller subagent

```
使用 fn-controller subagent：
  operation=start, function=route_a, args={n:"3", from:"A"}
```

**返回 JSON**：
```json
{"action": "execute_task", "task": {"prompt": "...", "tools": [...], "execute_in": "main"}}
```

### 阶段 3: 执行 Task

根据 `execute_in` 字段决定执行位置：

| execute_in | 执行方式 |
|------------|---------|
| `main` (默认) | 主会话直接执行 task.prompt，使用 task.tools |
| `subagent` | 调用临时 subagent 执行，使用默认模型 |
| `subagent@haiku` | 调用临时 subagent 执行，使用 haiku |
| `subagent@sonnet` | 调用临时 subagent 执行，使用 sonnet |
| `subagent@opus` | 调用临时 subagent 执行，使用 opus |

### 阶段 4: 继续执行（每次新建 subagent）

1. **调用 fn-controller**（每次都新建，不依赖 resume）
   ```
   使用 fn-controller subagent：
     operation=continue, task_result="[test_sequence] input=hello"
   ```

2. **循环阶段 3-4** 直到返回 `action: "complete"`

### 阶段 5: 完成

当 fn-controller 返回 `action: "complete"` 时：
- 输出最终结果

## ❗关键规则

1. **每次新建 subagent**：不依赖 resume，通过 state.json 保持状态
2. **主会话职责**：仅负责解析参数 + 执行 task
3. **stop-hook**：栈非空时强制继续

## 错误处理

| 错误类型 | 处理 |
|---------|------|
| fn-controller 返回 error | 输出错误，用 `/fn_continue` 恢复 |

$ARGUMENTS
