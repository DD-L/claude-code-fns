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
0. 🔑 SESSION: 获取 session_id（记住此值，后续复用，若忘记则须重新获取）
1. 🔍 RESOLVE: 解析函数名 → 获取完整路径（使用脚本，见下文）
2. 📖 READ: 读取解析后的 functions/<fqn>.json
3. 📝 STATE: 更新 scripts/states/<session_id>.json（栈操作）← 必须在 EXECUTE 之前
4. ▶️ EXECUTE: 执行 task（必须调用 tools 中的工具）
5. 🔀 ROUTE: 根据 on_complete 决定下一步（call/tail_call 目标也需 RESOLVE）
6. 重复，直到栈空（depth=0）
```

**关键点**：
- STATE 在 EXECUTE 之前 → 确保中断可恢复
- **tail_call 后直接进入新函数的 EXECUTE**，不重复执行当前 task
- **优化**：循环中 tail_call 到**同一函数**时，可跳过 RESOLVE（FQN 已知）

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

## 栈操作（使用 stack_ops 工具）

**所有栈操作必须通过 `scripts/stack_ops.ps1`（或 `.py`）执行。**

- 不清楚用法时：执行无参数 `.\scripts\stack_ops.ps1` 或 `python scripts/stack_ops.py --help` 查看
- **⚠️ 禁止杜撰命令格式**，必须从工具帮助或错误提示中学习正确用法
- 工具输出 BEFORE/AFTER + DIFF，用于审视操作是否正确

状态文件路径: `scripts/states/<session_id>.json`

### 速查

```powershell
# PowerShell 格式
powershell -ExecutionPolicy Bypass -File scripts/stack_ops.ps1 -Session <id> -Op <op> [-Fn <fqn>] [-ArgList "k=v,k2=v2"] [-Value <v>]

# 常用操作完整示例（$sid 为 session_id）
-Op push      -Fn tests/foo -ArgList "n=5,mode=test"   # 压栈
-Op tail_call -Fn tests/foo -ArgList "n=4"             # 尾调用（替换栈顶）
-Op return    [-Value "done"]                          # 返回（弹栈）
-Op show                                               # 查看完整状态
```

```bash
# Python 格式
python scripts/stack_ops.py <session> <op> [fqn] [--arg.k=v]

# 常用操作完整示例
python scripts/stack_ops.py $sid push tests/foo --arg.n=5 --arg.mode=test
python scripts/stack_ops.py $sid tail_call tests/foo --arg.n=4
python scripts/stack_ops.py $sid return "done"
python scripts/stack_ops.py $sid show
```

## on_complete 类型与栈操作

| 类型 | stack_ops 操作 | 说明 |
|------|----------------|------|
| return | `return [-Value v]` | 弹出栈顶，返回值写入父帧 `$prev` + 会话输出 |
| call | `call`/`push` | 压入新帧，被调用函数 return 后，**调用者继续执行自身的 on_complete**（通常是 `return`） |
| tail_call | `tail_call` | 替换栈顶（深度不变），**立即进入新函数 EXECUTE**，**循环中的 tail_call 禁止误用 push** |
| switch | - | 条件分支，选择一个动作执行 |

**⚠️ call 返回后**：被调用函数 `return` 后，控制权回到调用者。调用者应执行自身 on_complete 中 call 之后的隐式 `return`（除非有显式后续动作）。

### ⚠️ return vs pop

| 操作 | 用途 | 传值 |
|------|------|------|
| `return [-Value v]` | **正常结束** | ✅ 写入父帧 `$prev` |
| `pop` | 异常清理 | ❌ 仅弹出 |

**ROUTE 阶段正常结束必须用 `return`，禁止用 `pop`。**

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

**⚠️ loop 的 do 只能用 `tail_call`（禁止 `push`/`call`，否则栈溢出）**。用 `$output` 传递上次输出。

## ❗关键规则

1. **严格顺序** - RESOLVE → READ → STATE → EXECUTE → ROUTE
2. **EXECUTE→ROUTE 原子性** - 执行 task 后必须立即处理 on_complete，不能在两者之间停止
3. **必须用脚本解析函数名** - 禁止猜测或硬编码路径，必须调用 resolve_fn.ps1 或 resolve_fn.py
4. **用 stack_ops 工具进行栈操作** - 禁止手动编辑状态文件，禁止杜撰命令格式
5. **必须调用工具执行 task** - 产生可观测输出（工具调用结果/文件写入/stdout），不能仅靠对话描述
6. **禁止走捷径** - 必须**逐帧 return**，不能一次清空多帧，不能用 pop 替代 return
7. **stack 非空时不能停止** - stop-hook 检查当前会话

## 限制

- 栈深度: 100
- 循环次数: max_iterations（默认 1000）

$ARGUMENTS
