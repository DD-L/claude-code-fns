# Function 连续调用链演示

这个文档专门展示如何触发多个 function 的连续调用效果。

## 🔗 调用链结构

```
code_review (发现问题)
    ↓
fix_issues (修复问题)
    ↓
run_tests (验证修复)
    ↓ (如果测试失败)
fix_issues (再次修复)
    ↓
run_tests (再次验证)
    ↓
_return (完成)
```

## 🎯 最佳测试场景（保证触发完整调用链）

### 场景 1: 完整工作流（推荐）

在 Claude Code 中输入：

```
/fn code_review test_data/sample_code.py security
```

**预期执行流程**：

1. **code_review** 执行
   - 读取 `test_data/sample_code.py`
   - 发现安全问题：`eval()` 函数、密码明文存储
   - 输出：`need_fix = true`
   - **自动调用** → `fix_issues`

2. **fix_issues** 执行
   - 接收问题列表
   - 修复 `eval()` 安全问题
   - 修复密码存储问题
   - 输出：修复涉及核心逻辑
   - **自动调用** → `run_tests`

3. **run_tests** 执行
   - 运行 `test_data/test_sample.py`
   - 如果测试通过 → `_return`
   - 如果测试失败 → **自动调用** → `fix_issues`（循环）

---

### 场景 2: 从修复开始（测试 fix_issues → run_tests）

```
/fn fix_issues test_data/sample_code.py 中存在以下问题需要修复：
1. 安全问题：第13行使用 eval() 函数，存在代码注入风险，应该替换为安全的解析方法
2. 安全问题：第32行密码明文存储，应该使用哈希加密
3. 代码质量：第19行缺少错误处理，应该添加 try-except
```

**预期执行流程**：

1. **fix_issues** 执行
   - 修复所有问题
   - 输出：修复涉及核心逻辑
   - **自动调用** → `run_tests`

2. **run_tests** 执行
   - 运行测试验证
   - 根据测试结果决定是否再次调用 `fix_issues`

---

### 场景 3: 任务编排器路由（测试 task_orchestrator → code_review → ...）

```
/fn task_orchestrator 请审查 test_data/sample_code.py 的安全性，如果发现问题请修复并运行测试验证
```

**预期执行流程**：

1. **task_orchestrator** 执行
   - 分析任务：代码审查 + 修复 + 测试
   - 识别为代码审查任务
   - **自动调用** → `code_review test_data/sample_code.py security`

2. **code_review** 执行
   - 发现问题
   - **自动调用** → `fix_issues`

3. **fix_issues** 执行
   - 修复问题
   - **自动调用** → `run_tests`

4. **run_tests** 执行
   - 验证修复
   - 完成

---

## 📋 详细测试步骤

### 步骤 1: 准备测试环境

确保以下文件存在：
- ✅ `test_data/sample_code.py` - 包含问题的代码
- ✅ `test_data/test_sample.py` - 测试文件
- ✅ `functions/code_review.json`
- ✅ `functions/fix_issues.json`
- ✅ `functions/run_tests.json`

### 步骤 2: 在 Claude Code 中执行

**复制并粘贴以下命令**：

```
/fn code_review test_data/sample_code.py security
```

### 步骤 3: 观察执行过程

你应该看到类似以下的输出：

```
🚀 执行 function: code_review
📋 任务: 审查 test_data/sample_code.py 的安全性

正在读取文件...
正在分析代码...

发现的问题：
1. [严重] 第13行：使用 eval() 函数，存在代码注入风险
2. [严重] 第32行：密码明文存储，存在安全风险
3. [中等] 第19行：缺少错误处理

问题总数: 3
需要修复: true

🔄 自动调用下一个 function: fix_issues
```

然后会看到：

```
🚀 执行 function: fix_issues
📋 任务: 修复代码审查中发现的问题

正在修复问题 1/3...
正在修复问题 2/3...
正在修复问题 3/3...

修复完成：
- 已修复问题数: 3
- 修复涉及核心逻辑: true

🔄 自动调用下一个 function: run_tests
```

最后：

```
🚀 执行 function: run_tests
📋 任务: 运行测试验证修复结果

检测测试框架: unittest
运行测试: test_data/test_sample.py

测试结果:
✅ 测试通过: 4/4

🔄 调用链完成，返回结果
```

---

## 🎬 确保触发完整调用链的技巧

### 技巧 1: 明确指定安全问题

使用 `security` 作为审查类型，更容易触发 `fix_issues`：

```
/fn code_review test_data/sample_code.py security
```

### 技巧 2: 在输入中明确提到"修复"

```
/fn code_review test_data/sample_code.py security
```

或者：

```
/fn task_orchestrator 审查并修复 test_data/sample_code.py 中的安全问题
```

### 技巧 3: 确保测试文件存在

如果 `run_tests` 找不到测试文件，可能不会执行。确保：
- `test_data/test_sample.py` 存在
- 或者明确指定测试路径

---

## 🔍 如何验证调用链是否工作

### 检查点 1: code_review 是否调用了 fix_issues

在 `code_review` 的输出中查找：
- ✅ "发现需要修复的问题"
- ✅ "自动调用: fix_issues"
- ✅ "🔄 执行 function: fix_issues"

### 检查点 2: fix_issues 是否调用了 run_tests

在 `fix_issues` 的输出中查找：
- ✅ "修复涉及核心逻辑"
- ✅ "自动调用: run_tests"
- ✅ "🔄 执行 function: run_tests"

### 检查点 3: run_tests 是否完成

在 `run_tests` 的输出中查找：
- ✅ "测试结果"
- ✅ "调用链完成"
- ✅ 最终结果输出

---

## 🐛 如果调用链没有触发

### 问题 1: code_review 没有调用 fix_issues

**可能原因**：
- 没有发现问题
- 问题不够严重（need_fix 不是 true）

**解决方案**：
- 确保 `test_data/sample_code.py` 包含明显的问题（如 `eval()`）
- 明确指定 `security` 审查类型

### 问题 2: fix_issues 没有调用 run_tests

**可能原因**：
- 修复不涉及核心逻辑

**解决方案**：
- 在输入中明确说明"修复涉及核心逻辑，需要运行测试验证"
- 或者直接调用：`/fn run_tests test_data/test_sample.py`

### 问题 3: 执行中断

**解决方案**：
- 发送 "继续" 让 Claude 继续执行
- 或使用：`.\scripts\drive.ps1`

---

## 📊 完整调用链示例输出

```
╔══════════════════════════════════════════════════════════╗
║  Function 调用链执行日志                                 ║
╚══════════════════════════════════════════════════════════╝

[1/3] code_review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输入: test_data/sample_code.py security
任务: 审查代码安全性

发现 3 个问题:
  • [严重] eval() 函数使用
  • [严重] 密码明文存储
  • [中等] 缺少错误处理

决策: need_fix = true → 调用 fix_issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[2/3] fix_issues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输入: [来自 code_review 的问题列表]
任务: 修复代码问题

修复进度:
  ✓ 修复 eval() 安全问题
  ✓ 修复密码存储问题
  ✓ 添加错误处理

决策: 涉及核心逻辑 → 调用 run_tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[3/3] run_tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输入: test_data/test_sample.py
任务: 运行测试验证

测试结果:
  ✓ test_empty_list (0.001s)
  ✓ test_single_item (0.001s)
  ✓ test_multiple_items (0.001s)
  ✓ test_missing_quantity (0.001s)

通过: 4/4
决策: 测试通过 → _return
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 调用链执行完成
```

---

## 🎯 快速测试命令

**一键触发完整调用链**：

```
/fn code_review test_data/sample_code.py security
```

**如果第一次没有触发，尝试更明确的输入**：

```
/fn code_review test_data/sample_code.py security
请仔细检查安全问题，如果发现任何问题请立即修复并运行测试验证
```

---

## 💡 提示

1. **观察输出中的 "🔄" 标记** - 这表示自动调用了下一个 function
2. **查看 function 名称变化** - 应该看到 `code_review` → `fix_issues` → `run_tests`
3. **如果中断** - 发送 "继续" 或使用 `.\scripts\drive.ps1`
4. **测试数据** - 确保 `test_data/` 目录下的文件存在
