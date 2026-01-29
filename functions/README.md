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

## on_complete 类型

| 类型 | 说明 | 示例 |
|------|------|------|
| return | 返回 | `{"type": "return"}` |
| call | 调用并返回 | `{"type": "call", "target": "fn", "args": {...}}` |
| tail_call | 尾调用 | `{"type": "tail_call", "target": "fn", "args": {...}}` |
| switch | 条件分支 | `{"type": "switch", "conditions": [...]}` |
| sequence | 序列执行 | `{"type": "sequence", "steps": [...]}` |
| loop | 循环执行 | `{"type": "loop", "while": "...", "do": {...}}` |

## 目录结构

```
functions/
├── README.md              # 本文件
├── _schema.json           # JSON Schema
├── _builtins.json         # 内置 function
├── examples/              # 示例函数
│   ├── pipeline.json      # 序列示例
│   ├── batch_process.json # 循环示例
│   └── ...
├── tests/                 # 测试用例
│   ├── README.md          # 测试说明
│   ├── test_branch.json   # 分支测试
│   ├── test_sequence.json # 序列测试
│   ├── test_loop.json     # 循环测试
│   ├── test_recursion.json # 递归测试
│   └── ...
├── code_review.json       # 代码审查
├── fix_issues.json        # 修复问题
├── run_tests.json         # 运行测试
├── grow.json              # 栈增长示例
├── route_*.json           # 动态路由示例
├── long_task.json         # 长任务测试
└── your_function.json     # 你定义的 function
```

## 命名空间与函数引用

函数的**全限定名 (FQN)** 由目录路径和函数名组成。

### 引用语法

| 语法 | 含义 | 示例 |
|------|------|------|
| `name` | 短名，就近查找 | `validate` |
| `ns/name` | 绝对路径 (从 functions/ 开始) | `examples/validate` |
| `./name` | 显式当前目录 | `./validate` |
| `../name` | 显式上级目录 | `../route_a` |

### 就近原则

短名调用会从调用者所在目录开始，向上冒泡查找：

```
调用者: examples/pipeline
引用: validate
搜索顺序: examples/ → root/
结果: examples/validate (如果存在)
```

### 名字冲突处理

当多个目录有同名函数时，就近原则自动解决：

- 从 `examples/pipeline` 调用 `validate` → 匹配 `examples/validate`
- 从 `tests/test_sequence` 调用 `validate` → 匹配根级 `validate`
- 如需调用其他命名空间的函数 → 使用绝对路径 `examples/validate`

### 命令行调用

```bash
/fn tests/test_branch A          # 绝对路径
/fn examples/pipeline data       # 绝对路径
/fn code_review src/ security    # 根级函数
```

### 静态验证

验证所有函数引用是否正确：

```bash
python scripts/check_calls.py --verbose
```

重建函数索引：

```bash
python scripts/build_index.py
```

## 示例说明

### 经典链式调用

```
/fn code_review src/ security
```

执行流程：
1. `code_review` → 审查代码，发现问题则调用 →
2. `fix_issues` → 修复问题，需要测试则调用 →
3. `run_tests` → 运行测试，失败则回到 fix_issues

### 其他示例

- `examples/pipeline.json` - 演示 sequence 序列执行
- `examples/batch_process.json` - 演示 loop 循环执行
- `grow.json` - 演示栈增长（普通 call，深度递增）
- `route_*.json` - 演示动态路由和 tail_call（深度不变）
- `long_task.json` - 测试 stop-hook 机制
