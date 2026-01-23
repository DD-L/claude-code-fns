# 快速测试指南

在 Claude Code 中测试 function-skill 系统，直接输入以下命令：

## 🚀 快速开始

### 方法 1: 直接在 Claude Code 中输入命令

在 Claude Code 的聊天框中输入 `/fn` 命令：

```
/fn <function_name> [输入参数]
```

## 📝 测试示例

### 1. 测试 task_orchestrator（智能任务编排）

```
/fn task_orchestrator 请审查 test_data/sample_code.py 的安全性
```

这会自动路由到 `code_review` function。

---

### 2. 测试 code_review（代码审查）

```
/fn code_review test_data/sample_code.py security
```

或者：

```
/fn code_review test_data/sample_code.js performance
```

或者审查整个目录：

```
/fn code_review test_data/ quality
```

**预期行为**：如果发现问题，会自动调用 `fix_issues`。

---

### 3. 测试 fix_issues（修复问题）

```
/fn fix_issues test_data/sample_code.py 中存在安全问题：使用 eval() 函数，应该替换为安全的解析方法
```

**预期行为**：如果涉及核心逻辑，会自动调用 `run_tests`。

---

### 4. 测试 run_tests（运行测试）

```
/fn run_tests test_data/test_sample.py
```

或者：

```
/fn run_tests test_data/test_sample.js
```

或者运行整个目录：

```
/fn run_tests test_data/
```

**预期行为**：如果测试失败，会自动调用 `fix_issues`。

---

### 5. 完整工作流测试（推荐）

从代码审查开始，会自动触发后续流程：

```
/fn code_review test_data/sample_code.py security
```

**完整流程**：
1. `code_review` 审查代码
2. 发现问题 → 自动调用 `fix_issues`
3. 修复完成 → 自动调用 `run_tests`
4. 测试通过 → 返回结果

---

## 🎯 测试所有 Function 的完整命令列表

复制以下命令到 Claude Code 中依次测试：

```bash
# 1. 任务编排器 - 路由测试
/fn task_orchestrator 请审查 test_data/sample_code.py 的安全性
/fn task_orchestrator 修复 test_data 中的代码问题
/fn task_orchestrator 运行测试验证代码

# 2. 代码审查
/fn code_review test_data/sample_code.py security
/fn code_review test_data/sample_code.js performance
/fn code_review test_data/ quality

# 3. 修复问题
/fn fix_issues test_data/sample_code.py 中存在安全问题：使用 eval() 函数

# 4. 运行测试
/fn run_tests test_data/test_sample.py
/fn run_tests test_data/test_sample.js
```

---

## 💡 提示

### 如果执行中断

如果 Claude Code 在执行过程中停止，可以：

1. **发送 "继续"** - 让 Claude 继续执行
2. **使用驱动脚本**：
   ```powershell
   .\scripts\drive.ps1
   ```

### 查看执行进度

每个 function 执行时会显示：
- ✅ 当前正在执行的 function
- 📋 执行的任务内容
- 🔄 自动调用的下一个 function（如果有）

### 测试数据位置

所有测试数据在 `test_data/` 目录：
- `sample_code.py` / `sample_code.js` - 包含问题的示例代码
- `test_sample.py` / `test_sample.js` - 测试用例文件

---

## 🔍 验证测试是否成功

### code_review 成功标志
- ✅ 输出了问题列表
- ✅ 自动调用了 `fix_issues`（如果发现问题）

### fix_issues 成功标志
- ✅ 输出了修复总结
- ✅ 自动调用了 `run_tests`（如果涉及核心逻辑）

### run_tests 成功标志
- ✅ 输出了测试结果
- ✅ 显示测试通过/失败状态

### task_orchestrator 成功标志
- ✅ 正确路由到了对应的 function
- ✅ 显示了路由决策

---

## 🎬 推荐测试顺序

### ⭐ 想要看到连续调用效果？看这里！

**最佳命令（保证触发完整调用链）**：

```
/fn code_review test_data/sample_code.py security
```

这会自动触发：`code_review` → `fix_issues` → `run_tests`

**详细说明请查看**：`TEST_CHAIN_DEMO.md`

---

### 其他测试顺序

1. **先测试单个 function**：
   ```
   /fn code_review test_data/sample_code.py security
   ```

2. **测试完整工作流**：
   ```
   /fn code_review test_data/sample_code.py security
   ```
   （会自动触发 fix_issues → run_tests）

3. **测试任务编排器**：
   ```
   /fn task_orchestrator 请审查 test_data/ 目录的代码质量
   ```

---

## ❓ 常见问题

**Q: 命令没有反应？**  
A: 确保你在 Claude Code 的聊天框中输入，而不是在终端。

**Q: 提示找不到 function？**  
A: 确保你在项目根目录（`cc_function`），并且 `functions/` 目录存在。

**Q: 如何知道 function 执行完成？**  
A: 查看输出中是否有最终结果，或者看到 `_return` 标记。

**Q: 可以同时测试多个 function 吗？**  
A: 可以，但建议一个一个测试，观察每个 function 的行为。

---

## 📚 更多信息

- 详细文档：`README_TEST.md`
- 使用指南：`USAGE.md`
- Function 定义：`functions/*.json`
