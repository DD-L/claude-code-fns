# Meta Function Skill

执行 `functions/` 目录中的 JSON 定义的 function。

## Function 定义

```json
{
  "name": "my_fn",
  "params": ["arg1", "arg2"],
  "task": "任务描述，使用 $arg1 $arg2 引用参数",
  "tools": ["Bash", "Read"],
  "on_complete": {
    "type": "return | call | tail_call | switch"
  }
}
```

## on_complete 类型

| 类型 | 栈操作 | 说明 |
|------|--------|------|
| return | POP | 出栈返回 |
| call | PUSH | 入栈调用，完成后返回 |
| tail_call | REPLACE | 替换栈顶，不增加深度 |
| switch | - | 条件分支 |

### switch 条件分支

```json
{
  "type": "switch",
  "conditions": [
    {"when": "$n <= 0", "type": "return"},
    {"when": "$n > 0", "call": "fn", "args": {...}},
    {"when": "...", "tail_call": "fn", "args": {...}}
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

### loop 循环（语法糖）

```json
{
  "type": "loop",
  "while": "$n > 0",
  "do": {"tail_call": "fn", "args": {...}},
  "max_iterations": 100
}
```

## 命令

- `/fn name args [--session=id]` - 执行 function
- `/fn_continue [--session=id]` - 恢复中断的执行

## Session ID 获取（按优先级）

1. 命令行参数 `--session=<id>`（推荐用于并发测试）
2. 环境变量 `$CC_SESSION_ID`（由 SessionStart hook 注入，如可用）
3. 如都不可用，使用固定值 `default`
4. Stop hook 从 stdin 读取 session_id 精确匹配

状态文件: `scripts/states/<session_id>.json`

## 关键规则

1. 用 Write 工具更新 `scripts/states/<session_id>.json`（禁止 Bash 写）
2. 必须调用工具执行 task，产生可观测输出（不能仅靠对话描述）
3. return 时**逐帧 POP**，禁止一次清空多帧
4. 当前会话 stack 非空时不能停止
