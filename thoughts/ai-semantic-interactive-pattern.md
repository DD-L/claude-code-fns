# AI 语义理解交互模式 (AI Semantic Interactive Pattern)

## 方案核心

文件系统通信桥 + 状态嵌入输出文件，实现 AI 与交互式脚本的可靠通信。

## 架构

```
scripts/
├── interactive_wrapper.py   # 主进程包装器
└── wait_for_status.sh       # 预授权等待脚本

scripts/states/<WT_SESSION>/
├── state.json               # 会话状态（fn-controller 用）
├── agent_output.txt         # 对话 + 状态（AI 读取）
└── agent_input.txt          # AI 答案（脚本读取）
```

**agent_output.txt 格式：**
```text
=== CC_FN_TURN 1 ===
STATUS: CC_FN_WAITING_FOR_INPUT
[对话内容...]<<CC_FN_INPUT_NEEDED>>

=== CC_FN_COMPLETE ===
EXIT_CODE: 0
```

**agent_input.txt 格式（AI 写入）：**
```text
答案内容
<<CC_FN_INPUT_END>>
```

> **原子性保护**：AI 写入内容必须包含 `\n<<CC_FN_INPUT_END>>` 标记，wrapper 检测到此标记才读取。<<CC_FN_INPUT_END>>标记前需要换行。

**STATUS 值：**
- `CC_FN_WAITING_FOR_INPUT` - 等待 AI 输入（唯一的运行状态）
- 完成靠 `=== CC_FN_COMPLETE ===` 识别

## 主进程实现

主进程包装器：**scripts/interactive_wrapper.py**。负责启动子脚本、检测 `<<CC_FN_INPUT_NEEDED>>`、写入 `agent_output.txt`、等待并读取 `agent_input.txt` 后继续，结束时写入 `=== CC_FN_COMPLETE ===` 与 `EXIT_CODE`。实现见脚本本身。

**约定：** 被调用脚本在需要 AI 交互时必须输出 `<<CC_FN_INPUT_NEEDED>>`，主程序据此检测并挂起等待 AI 回写。

## 正确操作顺序与路径

**顺序（不可颠倒）：**

1. **先启动主程序**：在终端运行 `PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py <交互式脚本> [参数...]`，主程序内部通过 **scripts/get_session_id.py** 自动获取会话 ID（同环境变量 `WT_SESSION`，未设置时用 `default`），并创建 `scripts/states/<session_id>/`。
2. **再执行等待**：预授权下运行 `bash scripts/wait_for_status.sh`。脚本内部用同一方式自动获取会话 ID，等待新轮次或完成标记。

**路径由脚本自动给出，无需在执行流程中主动获取 session：**

- **scripts/wait_for_status.sh** 在输出内容前会先打印一行：`CC_FN_AGENT_INPUT_PATH=scripts/states/<session_id>/agent_input.txt`（正斜杠、相对仓库根）。
- AI 只需解析该行得到写入路径，再根据后续输出的 `agent_output.txt` 内容做语义分析并 **Write(解析到的路径, 答案)**，无需再跑 get_session_id 或手拼路径。

## AI 交互循环

1. **等待**：预授权下执行 `scripts/wait_for_status.sh`。首行为 `CC_FN_AGENT_INPUT_PATH=...`，之后为本次 `agent_output.txt` 内容。
2. **检查是否完成**：若内容中出现 `=== CC_FN_COMPLETE ===`，读取 `EXIT_CODE` 后结束；否则继续。
3. **语义分析**：根据首行后的输出内容生成答案。
4. **回写并继续**：`Write(首行解析出的 CC_FN_AGENT_INPUT_PATH, "答案内容\n<<CC_FN_INPUT_END>>")`，然后回到步骤 1。

> **重要**：写入内容必须以 `\n<<CC_FN_INPUT_END>>` 结尾，否则 wrapper 会一直等待。

示例：从 wait_for_status 输出中解析路径并检查完成（首行即路径）：

```bash
# 假设 wait_for_status.sh 输出在变量或文件中，首行是路径
# 完成判断：内容中出现 === CC_FN_COMPLETE === 则读 EXIT_CODE 结束
```

## 预授权辅助脚本

**scripts/wait_for_status.sh**：内部自动获取会话 ID（与主程序一致），等待 `agent_output.txt` 出现 `=== CC_FN_TURN N ===` 或 `=== CC_FN_COMPLETE ===` 后，**先输出一行** `CC_FN_AGENT_INPUT_PATH=scripts/states/<session_id>/agent_input.txt`，再输出本次文件内容。AI 用该行得到写入路径，无需主动获取 session。

用法：

- 自动会话（推荐）：`scripts/wait_for_status.sh`
- 指定输出文件：`scripts/wait_for_status.sh scripts/states/<session_id>/agent_output.txt`

## 关键技术点

### 1. 状态嵌入输出文件方案（推荐）

**文件结构：**
```
scripts/states/<WT_SESSION>/
├── state.json               # fn-controller 用
├── agent_output.txt         # 对话 + 状态（AI 读取）
└── agent_input.txt          # AI 答案（脚本读取）
```

**优势：**
- 状态和对话在同一文件，自动一致
- AI 只需读取 1 个文件
- 减少同步复杂度

**STATUS 值：**
- `CC_FN_WAITING_FOR_INPUT` - 等待 AI 输入（唯一的运行状态）
- 完成靠 `=== CC_FN_COMPLETE ===` 识别

### 2. 统一关键词前缀 CC_FN_

**所有协议关键词统一使用 `CC_FN_` 前缀，避免与脚本输出误匹配：**
- 输入提示：`<<CC_FN_INPUT_NEEDED>>`（被调用脚本在需要 AI 交互时**必须**输出）
- 输入结束：`\n<<CC_FN_INPUT_END>>`（AI 写入答案时**必须**以此结尾）
- 确认提示：`<<CC_FN_BINARY_YES_NO>>`（可选）
- 状态/完成标记见上文（`CC_FN_WAITING_FOR_INPUT`、`=== CC_FN_COMPLETE ===`、`=== CC_FN_TURN N ===` 等）

**约定：**
- 被调用脚本必须在需要 AI 交互时输出 `<<CC_FN_INPUT_NEEDED>>`，主程序据此检测并挂起等待 AI 回写。
- AI 写入答案时必须以 `\n<<CC_FN_INPUT_END>>` 结尾，确保 wrapper 读取到完整内容。

### 3. 会话隔离

**scripts/states/<SESSION_ID>/**
- 支持多实例并行
- 与 fn-controller 的 state.json 同目录

**会话 ID：** 由主程序与 wait_for_status.sh 内部自动通过 **scripts/get_session_id.py** 获取（读 `WT_SESSION`，空则 `default`），执行流程中无需主动获取。AI 只需使用 wait_for_status.sh 首行输出的 `CC_FN_AGENT_INPUT_PATH` 作为写入路径。fn-controller 场景下由控制器设置 `WT_SESSION` 后启动主程序即可。

## 限制与注意事项

1. **编码：** 设置 `PYTHONIOENCODING=utf-8` 和 `encoding='utf-8'`
2. **超时：** 等待 AI 回答应设置超时
3. **清理：** finally 块中清理临时文件
4. **无缓冲：** 使用 `-u` 参数禁用 Python 缓冲
5. **会话 ID：** 多实例运行需设置不同的 WT_SESSION

## 应用于 fn-controller

### 改造方案

在 fn-controller 中添加 "interactive" 类型：

```json
{
  "name": "interactive_test",
  "task": "与交互式脚本对话",
  "params": ["script_path", "args..."],
  "on_complete": {
    "type": "interactive",
    "wrapper": "scripts/interactive_wrapper.py",
    "script": "{{script_path}}",
    "args": "{{args}}"
  }
}
```

fn-controller 自动：
1. 设置 WT_SESSION（基于当前会话 ID）
2. 启动包装器并传递参数
3. 触发 AI 语义理解
4. 管理文件系统通信（scripts/states/<WT_SESSION>/）

---

**验证：** 2026-02-03，8 轮测试全部通过，退出码 0
**脚本：** scripts/interactive_test.py

**优化记录：**
- 初始：多文件 + PID 检测 → 不可靠
- 改进：状态文件 + 无 PID → 可靠
- 最终：状态嵌入输出文件 + 会话隔离 + 参数转发 → 最优

**实现文件：**
- `scripts/interactive_wrapper.py` - 主进程包装器
- `scripts/wait_for_status.sh` - 预授权等待脚本