# Function-Skill 使用指南

## 快速开始

### 方式一：直接使用 (可能会中断)

```
/fn code_review test_data/sample_code.py security
```

### 方式二：使用驱动脚本 (推荐，确保完整执行)

**PowerShell:**
```powershell
.\scripts\run_chain.ps1 -Function code_review -Input "test_data/sample_code.py security"
```

**Python (需要 Agent SDK):**
```bash
pip install anthropic-claude-agent-sdk
python scripts/run_chain.py code_review "test_data/sample_code.py security"
```

## 定义自己的 Function

在 `functions/` 目录创建 JSON 文件：

```json
{
  "name": "my_task",
  "task": "执行我的任务: 分析输入内容，生成报告",
  "on_complete": {
    "type": "return"
  }
}
```

然后执行：
```
/fn my_task "我的输入"
```

## 链式调用

```json
{
  "name": "step1",
  "task": "第一步任务",
  "on_complete": {
    "type": "call",
    "target": "step2"
  }
}
```

```json
{
  "name": "step2",
  "task": "第二步任务",
  "on_complete": {
    "type": "return"
  }
}
```

## 条件分支

```json
{
  "name": "analyze",
  "task": "分析代码并判断是否有问题",
  "on_complete": {
    "type": "switch",
    "conditions": [
      {"when": "有问题", "call": "fix"},
      {"when": "无问题", "call": "_return"}
    ],
    "default": "_return"
  }
}
```

## 可靠性机制

| 机制 | 说明 |
|------|------|
| 状态追踪 | `scripts/state.json` 记录当前状态 |
| Hook | `.claude/settings.json` 配置 PostToolUse hook |
| 驱动脚本 | `scripts/run_chain.ps1` / `run_chain.py` 确保完整执行 |

## 调试

查看当前状态：
```powershell
Get-Content scripts/state.json
```

手动继续执行：
```
继续执行 function 调用链，当前: <function_name>
```
