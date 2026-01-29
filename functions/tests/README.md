# Function Skill 测试用例

## 并发测试说明

使用 `--session` 参数隔离多个并发会话：

```bash
# 在不同会话中并发运行不同测试
/fn tests/test_branch A --session=s1
/fn tests/test_loop count=0 max=5 --session=s2
```

## 测试类别

### 1. 分支测试 (Branch/Switch)

测试条件分支的不同路径选择。

```bash
# 测试分支 A (call 调用，会返回)
/fn tests/test_branch A --session=s1

# 测试分支 B (tail_call 调用，不返回)
/fn tests/test_branch B --session=s2

# 测试分支 C (直接返回)
/fn tests/test_branch C --session=s3

# 测试默认分支
/fn tests/test_branch D --session=s4
```

**预期行为**：
- A: 栈深度增至 2，执行 handler_a 后返回，栈清空
- B: 栈深度保持 1 (tail_call 替换栈顶)，执行 handler_b 后栈清空
- C: 立即返回，栈清空
- D: 走 default 分支，直接返回

---

### 2. 序列测试 (Sequence)

测试序列执行和 `$prev` 参数传递。

```bash
/fn tests/test_sequence hello
```

**预期行为**：
1. `test_sequence` 输出: `[test_sequence] input=hello`
2. `seq_step1` 输出: `[seq_step1] processing: hello -> step1_hello`
3. `seq_step2` 输出: `[seq_step2] processing: step1_hello -> step1_hello_step2`
4. `seq_step3` 输出: `[seq_step3] FINAL: step1_hello_step2 -> DONE`

**栈深度变化**：
- 非最后一步使用 `call`: 栈增长
- 最后一步使用 `tail_call`: 不增加栈深度

---

### 3. 循环测试 (Loop)

测试循环迭代和终止条件。loop 的 do **只能用 tail_call**（栈深度不增长）。

```bash
/fn tests/test_loop count=0 max=5
```

**预期行为**：输出 6 次迭代信息（0-5），栈深度始终为 1

---

### 4. 递归测试 (Recursion)

测试真正的递归和尾递归优化。

```bash
# 真正的递归 (栈增长)
/fn tests/test_recursion 5

# 尾递归优化 (栈深度恒为 1)
/fn tests/test_tail_recursion 5
```

**预期行为**：
- `test_recursion`: 栈深度从 1 增长到 6，然后依次返回
- `test_tail_recursion`: 栈深度始终为 1

---

### 5. 综合测试 (Combined)

结合多种控制结构的测试。

```bash
# 测试序列模式
/fn tests/test_combined mode=sequence count=3

# 测试循环模式
/fn tests/test_combined mode=loop count=5

# 测试递归模式
/fn tests/test_combined mode=recursion count=3

# 测试尾递归模式
/fn tests/test_combined mode=tail count=5
```

---

## 验证要点

### 栈状态检查

每次测试后检查会话状态文件:

```bash
# 如使用 --session 参数
cat scripts/states/<session_id>.json

# 如使用环境变量
cat scripts/states/$CC_SESSION_ID.json

# 如未指定 session，使用默认值
cat scripts/states/default.json
```

测试完成后应该看到:
```json
{ "status": "idle", "stack": [], "output": "..." }
```

### 运行时栈深度

在测试过程中观察状态文件的变化：

| 测试类型 | 预期栈深度变化 |
|---------|--------------|
| loop 循环 | 恒为 1（强制 tail_call）|
| 尾递归 | 恒为 1 |
| 真递归 | 随调用深度增长 |
| 序列 | 根据 call/tail_call 类型变化 |

### Stop-Hook 测试

长任务测试可以验证 stop-hook 机制：

```bash
/fn long_task n=0 total=20
```

如果 Claude 尝试提前终止，stop-hook 应该阻止并提示继续。

---

## 测试文件列表

| 文件 | 用途 |
|-----|------|
| test_branch.json | 分支测试入口 |
| branch_handler_a.json | 分支 A 处理器 |
| branch_handler_b.json | 分支 B 处理器 |
| test_sequence.json | 序列测试入口 |
| seq_step1.json | 序列步骤 1 |
| seq_step2.json | 序列步骤 2 |
| seq_step3.json | 序列步骤 3 |
| test_loop.json | 循环测试（强制 tail_call）|
| test_recursion.json | 真递归测试 |
| test_tail_recursion.json | 尾递归测试 |
| test_combined.json | 综合测试入口 |
