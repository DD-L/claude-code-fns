# Meta Function Executor

执行 function-skill 调用链。

## 用法

```
/fn <function_name> [input]
```

## ⚠️ 强制规则

**在调用链完成前，你不能停止响应。每执行完一个 function，必须立即检查 `on_complete` 并执行下一个。**

## 执行流程

```
1. 读取 functions/<function_name>.json
2. 更新 scripts/state.json (status: "running")
3. 执行 task
4. 根据 on_complete 决定下一步:
   - type="return" → 完成，更新状态为 "completed"
   - type="call" → 立即执行 target function
   - type="switch" → 匹配条件后立即执行对应 function
5. 如果下一步不是 _return，回到步骤 1
```

## 关键：不要停止

每次执行完 function 的 task 后：

1. 判断 `on_complete` 的结果
2. 如果结果指向另一个 function（不是 `_return`）
3. **立即**读取那个 function 的定义并执行
4. **不要**输出"建议执行"或"下一步将调用"
5. **直接执行**，在同一个响应中完成整个链

## 状态文件

每个步骤更新 `scripts/state.json`：

```json
{
  "status": "running",
  "current_function": "当前执行的 function",
  "input": "输入",
  "completed_functions": ["已完成的"],
  "last_update": "ISO 时间戳"
}
```

完成后：
```json
{
  "status": "completed",
  "current_function": null,
  ...
}
```

## 内置 Function

| 名称 | 行为 |
|------|------|
| `_return` | 终止调用链 |
| `_compact` | 执行 /compact |
| `_clear` | 执行 /clear |

## on_complete 路由

**type = "return"**
```json
{"type": "return"}
```
→ 终止，更新状态为 completed

**type = "call"**
```json
{"type": "call", "target": "next_function", "pass_output": true}
```
→ 立即执行 next_function

**type = "switch"**
```json
{
  "type": "switch",
  "conditions": [
    {"when": "need_fix == true", "call": "fix_issues"},
    {"when": "tests_pass == false", "call": "fix_issues"}
  ],
  "default": "_return"
}
```
→ 匹配第一个满足条件的分支并立即执行

$ARGUMENTS
