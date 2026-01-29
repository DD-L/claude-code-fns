# /fn - Function Executor

## 用法
```
/fn <function_name> [args...] [--session=<id>]
```

## Session ID 获取

1. 如有 `--session=<id>` 参数，直接使用
2. 否则执行：`echo "WT_SESSION=$WT_SESSION"`
   - **⚠️ 必须直接用 echo，禁止用 powershell -Command 转发**
   - 解析输出 `=` 后的值作为 session_id
3. 若为空，使用 `default`

## 执行流程

**⚠️ 严格按顺序执行，不可跳过或颠倒：**

```
0. 🔑 SESSION: 获取 session_id
1. 🔍 RESOLVE: 解析函数名 → 获取完整路径（使用脚本，见下文）
2. 📖 READ: 读取解析后的 functions/<fqn>.json
3. 📝 STATE: 更新 scripts/states/<WT_SESSION>.json（栈操作）← 必须在 EXECUTE 之前
4. ▶️ EXECUTE: 执行 task（必须调用 tools 中的工具）
5. 🔀 ROUTE: 根据 on_complete 决定下一步（call/tail_call 目标也需 RESOLVE）
6. 重复，直到栈空
```

**为什么 STATE 必须在 EXECUTE 之前？** 确保中断时可从状态文件恢复。

## 函数名解析（RESOLVE）

**必须使用脚本解析，不能由模型猜测路径。**

### 解析命令

PowerShell（优先）：
```powershell
powershell -ExecutionPolicy Bypass -File scripts/resolve_fn.ps1 <target> [-Caller <caller_fqn>]
```

Python（兜底）：
```bash
python scripts/resolve_fn.py <target> [--caller=<caller_fqn>]
```

### 参数说明

- `<target>`: 函数引用（如 `validate`、`examples/validate`、`./step1`、`../route_a`）
- `<caller_fqn>`: 当前函数的 FQN（如 `tests/test_sequence`），用于就近查找

### 输出格式（JSON）

成功：
```json
{"success": true, "fqn": "examples/validate", "path": "functions/examples/validate.json"}
```

失败：
```json
{"success": false, "error": "Function not found: xxx"}
```

### 解析时机

1. **入口调用**：`/fn <name>` 时，解析 `<name>`（无 caller）
2. **on_complete 跳转**：解析 `call`/`tail_call` 目标时，caller = 当前函数 FQN

## 状态文件

路径: `scripts/states/<WT_SESSION>.json`（WT_SESSION 为 Windows Terminal 会话 ID）

```json
{ "status": "idle|running", "stack": [], "output": null }
```

## 栈帧结构

```json
{
  "function": "<fqn>",
  "args": {...},
  "return_to": null,
  "output": null
}
```

**注意**：`function` 字段存储解析后的 FQN（如 `tests/test_sequence`），不是短名。

## on_complete 类型与栈操作

| 类型 | 栈操作 | 说明 |
|------|--------|------|
| return | POP | 弹出栈顶，返回上一帧 |
| call | PUSH | 压入新帧，完成后返回 |
| tail_call | REPLACE | 替换栈顶（不增加深度）|
| switch | - | 条件分支，选择一个动作执行 |

### switch 条件分支

```json
{
  "type": "switch",
  "conditions": [
    {"when": "<条件>", "type": "return"},
    {"when": "<条件>", "call": "<fn>", "args": {...}},
    {"when": "<条件>", "tail_call": "<fn>", "args": {...}}
  ],
  "default": "_return"
}
```

### sequence 序列（语法糖）

```json
{
  "type": "sequence",
  "steps": [
    {"call": "step1", "args": {...}},
    {"call": "step2", "args": {"input": "$prev"}}
  ]
}
```

**展开为**：按用户指定的 `call`（PUSH）或 `tail_call`（REPLACE）依次执行每个 step。
推荐：非最后一步用 `call`(保证 $prev 可用)，最后一步用 `tail_call`(优化栈深度)。

### loop 循环

```json
{
  "type": "loop",
  "while": "<条件>",
  "do": {"tail_call": "<fn>", "args": {...}}
}
```

**规则**：loop 的 do **只能用 tail_call**（栈深度不增长）。用 `$output` 传递上次输出。

## ❗关键规则

1. **严格顺序** - RESOLVE → READ → STATE → EXECUTE → ROUTE
2. **EXECUTE→ROUTE 原子性** - 执行 task 后必须立即处理 on_complete，不能在两者之间停止
3. **必须用脚本解析函数名** - 禁止猜测或硬编码路径，必须调用 resolve_fn.ps1 或 resolve_fn.py
4. **用 Write 工具更新状态** - 每次 PUSH/POP/REPLACE 立即用 Write 更新文件（禁止用 Bash 写）
5. **必须调用工具执行 task** - 产生可观测输出（工具调用结果/文件写入/stdout），不能仅靠对话描述
6. **禁止走捷径** - return 时必须**逐帧 POP**，不能一次清空多帧
7. **stack 非空时不能停止** - stop-hook 检查当前会话

## 限制

- 栈深度: 100
- 循环次数: max_iterations（默认 1000）

$ARGUMENTS
