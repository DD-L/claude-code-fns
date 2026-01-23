# Meta Function Skill

一个"元技能"框架，用于定义和执行可组合的 function-skill。

## 概念

**Function** 是可复用的任务单元：
- 有输入和输出（提示词文本）
- 可以调用其它 function
- 通过 JSON 配置定义

## Function 定义

在 `functions/` 目录下创建 JSON 文件：

```json
{
  "name": "my_function",
  "task": "任务描述提示词",
  "on_complete": {
    "type": "return | call | switch"
  }
}
```

### on_complete 类型

**return** - 结束并返回结果
```json
{"type": "return"}
```

**call** - 调用指定 function
```json
{"type": "call", "target": "other_function"}
```

**switch** - 条件分支
```json
{
  "type": "switch",
  "conditions": [
    {"when": "条件A", "call": "function_a"},
    {"when": "条件B", "call": "function_b"}
  ],
  "default": "_return"
}
```

## 内置 Function

| 名称 | 作用 |
|------|------|
| `_return` | 终止调用链 |
| `_compact` | 压缩上下文后终止 |
| `_clear` | 清理上下文后终止 |

## 执行

使用 `/fn` 命令执行：

```
/fn <function_name> [input]
```

## 可靠性

1. **链式执行**：调用链必须完整执行到 `_return`
2. **状态追踪**：`scripts/state.json` 记录当前状态
3. **恢复机制**：`/continue` 命令可恢复中断的调用链

## 渐进式暴露

通过 `tools` 字段限制 function 可用的工具：

```json
{
  "name": "readonly_task",
  "task": "...",
  "tools": ["Read", "Grep"]
}
```
