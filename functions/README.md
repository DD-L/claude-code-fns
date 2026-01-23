# Functions 目录

在此目录下创建 JSON 文件定义你的 function。

## 快速开始

创建 `my_function.json`：

```json
{
  "name": "my_function",
  "description": "我的 function",
  "task": "执行某个任务的提示词",
  "on_complete": {
    "type": "return"
  }
}
```

然后使用 `/fn my_function` 执行。

## 完整字段

```json
{
  "name": "string",           // 必填：唯一标识
  "description": "string",    // 可选：描述
  "task": "string",           // 必填：任务提示词
  "input_hint": "string",     // 可选：输入说明
  "output_hint": "string",    // 可选：输出说明
  "on_complete": {            // 可选：完成后行为，默认 return
    "type": "return | call | switch",
    "target": "string",
    "conditions": [{"when": "...", "call": "..."}],
    "default": "string"
  },
  "tools": ["string"],        // 可选：限制可用工具
  "max_iterations": number    // 可选：最大迭代
}
```

## 目录结构

```
functions/
├── README.md              # 本文件
├── _schema.json           # JSON Schema
├── _builtins.json         # 内置 function 说明
├── code_review.json       # 示例：代码审查
├── fix_issues.json        # 示例：问题修复
├── run_tests.json         # 示例：运行测试
├── task_orchestrator.json # 示例：任务编排
└── your_function.json     # 你定义的 function
```

## 示例说明

目录中的 `code_review.json`、`fix_issues.json`、`run_tests.json`、`task_orchestrator.json` 是示例，展示如何定义 function。你可以：
- 参考它们的结构
- 直接修改使用
- 删除后创建自己的 function
