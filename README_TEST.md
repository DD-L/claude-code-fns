# Function Skill 测试指南

本目录包含用于测试 function-skill 系统的完整测试套件。

## 文件结构

```
.
├── test_all_functions.ps1    # 自动化测试脚本（验证定义和结构）
├── test_demo.ps1              # 演示脚本（实际调用 function）
├── test_data/                 # 测试数据目录
│   ├── sample_code.py         # 包含问题的示例 Python 代码
│   ├── sample_code.js         # 包含问题的示例 JavaScript 代码
│   ├── test_sample.py         # Python 测试文件
│   ├── test_sample.js         # JavaScript 测试文件
│   └── package.json           # Node.js 项目配置
└── README_TEST.md             # 本文件
```

## 快速开始

### ⭐ 想要看到连续调用效果？

**在 Claude Code 中输入**：

```
/fn code_review test_data/sample_code.py security
```

这会自动触发完整的调用链：`code_review` → `fix_issues` → `run_tests`

**详细说明**：查看 `TEST_CHAIN_DEMO.md`

---

### 1. 运行自动化测试

验证所有 function 的定义和结构：

```powershell
# 运行所有测试
.\test_all_functions.ps1

# 测试单个 function
.\test_all_functions.ps1 -Function code_review

# 详细输出
.\test_all_functions.ps1 -Verbose

# 干运行（只显示测试计划，不实际执行）
.\test_all_functions.ps1 -DryRun
```

### 2. 运行演示程序

实际调用 function 进行演示：

```powershell
# 运行所有演示
.\test_demo.ps1

# 运行特定演示
.\test_demo.ps1 -Demo code_review
.\test_demo.ps1 -Demo fix_issues
.\test_demo.ps1 -Demo run_tests
.\test_demo.ps1 -Demo task_orchestrator
.\test_demo.ps1 -Demo demo_chain
```

### 3. 测试连续调用链

专门用于测试 function 连续调用的脚本：

```powershell
# 显示调用链测试指南
.\test_chain.ps1
```

## 测试覆盖

### 已覆盖的 Functions

1. **task_orchestrator**
   - ✅ 路由到 code_review
   - ✅ 路由到 fix_issues
   - ✅ 路由到 run_tests
   - ✅ 默认返回

2. **code_review**
   - ✅ 安全审查 Python 代码
   - ✅ 性能审查 JavaScript 代码
   - ✅ 质量审查整个目录

3. **fix_issues**
   - ✅ 修复安全问题
   - ✅ 修复性能问题

4. **run_tests**
   - ✅ 运行 Python 测试
   - ✅ 运行 JavaScript 测试
   - ✅ 运行整个测试目录

5. **内置 Functions**
   - ✅ _compact
   - ✅ _clear
   - ✅ _return

6. **Schema 验证**
   - ✅ 验证所有 function 定义符合 schema

## 测试数据说明

### sample_code.py / sample_code.js

包含以下问题，用于测试 code_review 和 fix_issues：

- **安全问题**：使用 `eval()` 函数
- **安全问题**：密码明文存储
- **性能问题**：未优化的循环
- **代码质量**：缺少错误处理

### test_sample.py / test_sample.js

包含测试用例，用于测试 run_tests：

- 空列表测试
- 单个项目测试
- 多个项目测试
- 边界情况测试

## 测试流程

### 自动化测试流程

1. **验证定义文件**：检查 JSON 格式和必需字段
2. **验证 Schema**：确保符合 `_schema.json` 定义
3. **验证内置 Functions**：检查所有内置 function 已定义
4. **生成测试报告**：保存为 JSON 文件

### 演示流程

1. **单个 Function 演示**：独立测试每个 function
2. **调用链演示**：展示 function 之间的自动调用关系
3. **完整 Workflow**：从 code_review 到 fix_issues 到 run_tests

## 预期行为

### task_orchestrator

- 输入 "审查代码" → 路由到 `code_review`
- 输入 "修复问题" → 路由到 `fix_issues`
- 输入 "运行测试" → 路由到 `run_tests`
- 输入其他 → 返回结果

### code_review

- 发现安全问题 → 自动调用 `fix_issues`
- 无问题 → 返回结果

### fix_issues

- 涉及核心逻辑 → 自动调用 `run_tests`
- 其他情况 → 返回结果

### run_tests

- 测试失败 → 自动调用 `fix_issues`
- 测试通过 → 返回结果

## 故障排除

### 测试失败

1. **定义文件不存在**
   - 检查 `functions/` 目录下是否有对应的 JSON 文件

2. **JSON 格式错误**
   - 使用 JSON 验证工具检查格式
   - 确保符合 `_schema.json` 定义

3. **Function 执行失败**
   - 检查 Claude Code 是否正常运行
   - 查看错误日志
   - 使用 `scripts\drive.ps1` 继续执行

### 演示无法运行

1. **脚本不存在**
   - 确保 `scripts\run_function.ps1` 存在
   - 检查文件路径是否正确

2. **Claude Code 未安装**
   - 演示需要 Claude Code 环境
   - 可以手动执行 `/fn` 命令

## 扩展测试

要添加新的测试用例，编辑 `test_all_functions.ps1` 中的 `$TestCases` 变量：

```powershell
$TestCases = @{
    "your_function" = @(
        @{
            Name = "测试名称"
            Input = "测试输入"
        }
    )
}
```

## 注意事项

1. **自动化测试**（test_all_functions.ps1）只验证定义和结构，不实际执行 function
2. **演示程序**（test_demo.ps1）会实际调用 function，需要 Claude Code 环境
3. 测试数据中的代码包含故意设计的问题，用于测试目的
4. 实际执行时，function 会在 Claude Code 中运行，可能需要用户交互

## 相关文档

- `.claude/commands/fn.md` - Function 执行命令说明
- `.claude/skills.md` - Function Skill 系统说明
- `USAGE.md` - 使用指南
