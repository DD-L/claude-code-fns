# Meta Function Executor

通用的 function-skill 执行器。这是一个"元技能"，可以执行任何符合规范定义的 function。

## 用法

```
/fn <function_name> [input]
```

## 核心规则

1. **链式执行**：如果 function 的 `on_complete` 指向另一个 function，必须继续执行，直到遇到 `_return`
2. **状态追踪**：每个步骤更新 `scripts/state.json`
3. **不中断**：在调用链完成前不能停止响应

## 执行算法

```
execute(function_name, input):
    iteration = 0
    completed = []
    
    while function_name ≠ "_return" and function_name ≠ null and iteration < 20:
        iteration++
        
        # 更新状态
        write("scripts/state.json", {status: "running", current: function_name})
        
        # 输出进度
        print("━━━ [Step {iteration}] {function_name} ━━━")
        
        # 加载定义
        def = read("functions/{function_name}.json")
        
        # 执行任务
        result = execute_task(def.task, input)
        
        # 路由决策
        function_name, input = route(def.on_complete, result)
        
        # 处理内置
        if function_name == "_compact": exec("/compact"); function_name = "_return"
        if function_name == "_clear": exec("/clear"); function_name = "_return"
        
        completed.push(function_name)
    
    # 完成
    write("scripts/state.json", {status: "completed", current: null})
    print("━━━ 完成: {completed.join(' → ')} ━━━")
```

## Function 定义规范

每个 function 是 `functions/` 目录下的 JSON 文件：

```json
{
  "name": "string",           // 唯一标识
  "description": "string",    // 描述
  "task": "string",           // 任务提示词
  "on_complete": {
    "type": "return | call | switch",
    "target": "string",       // type=call 时使用
    "conditions": [           // type=switch 时使用
      {"when": "条件描述", "call": "function_name"}
    ],
    "default": "string"       // switch 默认分支
  },
  "tools": ["string"],        // 可选：限制可用工具
  "max_iterations": number    // 可选：最大迭代次数
}
```

## 内置 Function

| 名称 | 行为 |
|------|------|
| `_return` | 终止调用链 |
| `_compact` | 执行 `/compact` 后终止 |
| `_clear` | 执行 `/clear` 后终止 |

## 路由规则

**type = "return"**
→ 结束调用链

**type = "call"**
→ 调用 `target` 指定的 function

**type = "switch"**
→ 根据结果匹配 `conditions` 中的条件，调用对应 function
→ 无匹配时使用 `default`

## 恢复

如果中断，发送 `/continue` 或读取 `scripts/state.json` 获取状态后继续。

$ARGUMENTS
