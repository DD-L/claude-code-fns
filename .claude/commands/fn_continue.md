# 强制继续执行 Function 调用链

当 function 调用链意外中断时，使用此命令恢复执行。

## 用法

```
/fn_continue
```

## 执行流程

1. **读取状态文件**
   读取 `scripts/state.json` 获取当前执行状态

2. **检查是否需要继续**
   - 如果 `status` 是 "running" 且 `current_function` 不为空
   - 则需要继续执行

3. **恢复执行**
   - 从 `current_function` 继续
   - 按照正常的 function 调用链流程执行
   - 直到遇到 `_return`

## 状态文件格式

```json
{
  "status": "running | completed | idle",
  "current_function": "当前需要执行的 function",
  "current_input": "当前 function 的输入",
  "completed_functions": ["已完成的 function 列表"],
  "last_update": "2024-01-01T12:00:00Z"
}
```

## 示例

假设 `code_review` 执行完后意外停止，状态文件显示：

```json
{
  "status": "running",
  "current_function": "fix_issues",
  "current_input": "... 问题列表 ...",
  "completed_functions": ["code_review"]
}
```

执行 `/fn_continue` 后：

```
━━━ 恢复执行 ━━━
📂 读取状态: scripts/state.json
📍 上次停止于: code_review (已完成)
📍 待执行: fix_issues

━━━ [继续] 执行: fix_issues ━━━
🔧 修复问题...
...

━━━ [继续] 执行: run_tests ━━━
🧪 运行测试...
✅ 测试通过

━━━ 调用链完成 ━━━
```

## 注意

⚠️ 正常情况下不应该需要使用此命令！
如果你频繁需要使用 `/fn_continue`，说明 `/fn` 命令的可靠性机制没有正常工作。

$ARGUMENTS
