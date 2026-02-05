我们来探讨个方案可行性，现在 subagent @.claude/agents/fn-controller.md 已经基本能运作，但是仍有 （1）不可靠 和（2）运行效率低的问题。我们来探讨下，@.claude/agents/fn-controller.md 中的哪些内容和步骤可以压缩，并调用可靠的脚本，完成的操作。确定的输入输出和算法，都可以优化成一个脚本调用或多个脚本调用，如果存在这种优化的可能性，则设计一套方案，脚本运行日志要包含必要的信息，以便 subagent fn-controller 读取审视执行过程和结果。这样还有个好处是可以大幅压缩 fn-controller 提示词长度，减少 subagent 的认知负担，使其运行更可靠效率更高。此外，还有 ps1 的维护成本是否比 py 脚本更高？（你要推演所有 case, 所有控制语句和嵌套控制语句，以便深入评估方案可行。以上都只做探讨，不做修改）


=======================

我来仔细阅读 fn-controller.md 的内容，然后分析优化方案的可行性。

[1 tool called]

让我也读取相关的脚本文件，以便全面分析优化方案。

[3 tools called]

让我再看几个测试用例来理解各种控制流的实际应用。

[4 tools called]

现在我对整个系统有了全面了解。让我来深入分析并设计优化方案。

---

## 深度分析报告：fn-controller 优化方案可行性

### 一、当前架构的问题

**fn-controller 目前需要执行的"认知工作"：**

| 步骤 | 工作内容 | 工具调用 |
|------|---------|---------|
| RESOLVE | 解析函数名 | 1x Shell (resolve_fn) |
| READ | 读取函数定义 JSON | 1x Read |
| STATE | 栈操作 | 1-2x Shell (stack_ops) |
| ROUTE | 解析 on_complete、变量替换、条件评估、决定下一步 | **在 subagent 大脑中** |

问题：
1. **ROUTE 阶段完全依赖 AI 推理**：变量替换、条件评估、控制流判断都在 509 行提示词指导下由 AI 完成
2. **多次工具调用**：每次操作需要 3-5 次工具调用
3. **认知负担重**：subagent 需要理解复杂的嵌套逻辑（sequence 中的 call 返回后如何处理、switch 中的 call 返回后整个 switch 视为完成等）

---

### 二、可脚本化分析（按操作类型）

#### 2.1 `start` 操作

```
输入: function, args
处理: RESOLVE → READ → LOOP前置检查 → STATE.push → 变量替换 → 生成输出
```

| 步骤 | 可脚本化 | 说明 |
|------|----------|------|
| RESOLVE | ✅ | 已有 resolve_fn.py |
| READ JSON | ✅ | 简单文件读取 |
| LOOP 前置检查 | ✅ | 需要条件评估器 |
| STATE.push | ✅ | 已有 stack_ops.py |
| 变量替换 | ✅ | 字符串替换 |
| 生成输出 | ✅ | JSON 构造 |

**结论：start 100% 可脚本化**

#### 2.2 `continue` 操作 — 各 on_complete 类型推演

##### 2.2.1 `type: return`

```python
# 伪代码
def handle_return(value):
    stack_ops.return(value)
    
    while True:
        state = stack_ops.get_next_action()
        if state.depth == 0:
            return {"action": "complete"}  # 栈空
        
        # 栈非空，检查栈顶帧是否有 has_prev（子函数刚 return）
        if state.top_frame.has_prev:
            parent_on_complete = read_function(state.top_frame.function).on_complete
            
            if parent_on_complete.type == "sequence":
                # 继续下一步
                return handle_sequence_continue(parent_on_complete)
            elif parent_on_complete.type == "switch":
                # switch 中的 call 返回后，整个 switch 完成
                stack_ops.return()  # 隐式 return，继续循环
            else:
                # 其他类型，执行隐式 return
                stack_ops.return()  # 继续循环
        else:
            break  # 不应该到这里
    
    return {"action": "error", "message": "Unexpected state"}
```

**关键点**：脚本需要在一次调用中处理整个 return 链，直到栈空或找到需要执行 task 的点。

**可脚本化：✅**（需要处理递归/循环逻辑）

##### 2.2.2 `type: call`

```python
def handle_call(target, args, current_fqn):
    resolved = resolve_function(target, caller=current_fqn)
    fn_def = read_function(resolved.fqn)
    stack_ops.push(resolved.fqn, args)
    task = substitute_vars(fn_def.task, args)
    return {"action": "execute_task", "task": task}
```

**可脚本化：✅**

##### 2.2.3 `type: tail_call`

与 call 类似，只是用 `stack_ops.tail_call` 替换栈顶。

**可脚本化：✅**

##### 2.2.4 `type: switch`

```python
def handle_switch(on_complete, frame_args):
    for condition in on_complete.conditions:
        expr = substitute_vars(condition.when, frame_args)
        if evaluate_condition(expr):
            if condition.type == "return":
                return handle_return(None)
            elif "call" in condition:
                return handle_call(condition.call, condition.args)
            elif "tail_call" in condition:
                return handle_tail_call(condition.tail_call, condition.args)
    
    # default
    if on_complete.default == "_return":
        return handle_return(None)
    else:
        return handle_call(on_complete.default, on_complete.default_args)
```

**需要的组件**：
- 变量替换：`$mode` → `'A'`
- 条件评估器：`'A' == 'A'` → `True`

**可脚本化：✅**

##### 2.2.5 `type: sequence`

```python
def handle_sequence(on_complete, top_frame):
    step_index = top_frame.get("step_index", 0)
    steps = on_complete.steps
    
    if step_index >= len(steps):
        # sequence 完成
        return handle_return(None)
    
    step = steps[step_index]
    
    # 先更新 step_index
    stack_ops.update(step_index=step_index + 1)
    
    # 变量替换（包括 $prev）
    args = substitute_vars(step.args, top_frame.args, prev=top_frame.get("prev"))
    
    if "call" in step:
        return handle_call(step.call, args)
    elif "tail_call" in step:
        return handle_tail_call(step.tail_call, args)
```

**关键**：子函数 return 后，`has_prev=true`，继续处理下一个 step。

**可脚本化：✅**

##### 2.2.6 `type: loop`

```python
def handle_loop(on_complete, frame_args):
    # 1. 计算 do.args 的新值
    new_args = {}
    for key, expr in on_complete.do.args.items():
        new_args[key] = evaluate_expr(substitute_vars(expr, frame_args))
    
    # 2. 用新值评估 while 条件
    condition = substitute_vars(on_complete.while, new_args)
    
    if not evaluate_condition(condition):
        # 循环结束
        return handle_return(None)
    else:
        # 继续循环
        return handle_tail_call(on_complete.do.tail_call, new_args)
```

**需要的组件**：
- 算术表达式求值：`$count + 1` → `6`
- 条件评估器：`6 < 10` → `True`

**可脚本化：✅**

---

### 三、嵌套场景推演（典型示例）

#### Case 1: sequence 中的 call（$prev 传递）

```
test_sequence(input="hello") → sequence
  step[0]: call seq_step1 → return "step1_result" → $prev="step1_result"
  step[1]: call seq_step2 → return "step2_result" → $prev="step2_result"  
  step[2]: tail_call seq_step3 → return → 栈空 → complete
```

**脚本处理要点**：子函数 return 后设置 `has_prev=true`，继续处理下一个 step。

#### Case 2: loop 完整循环

```
test_loop(count=0, max=3) → loop(while: $count < $max)
  iteration 0: count=0 → 新count=1 → 1<3=true → tail_call(count=1)
  iteration 1: count=1 → 新count=2 → 2<3=true → tail_call(count=2)
  iteration 2: count=2 → 新count=3 → 3<3=false → return → complete
```

**脚本处理要点**：先计算新参数，再用新值评估 while 条件。

#### 其他场景概要

| 场景 | 处理要点 |
|------|---------|
| switch 中的 call 返回 | call 返回后整个 switch 完成，执行隐式 return |
| 深层嵌套 sequence | return 时循环检查父帧，直到找到需执行 task 的点或栈空 |
| loop 首次条件不满足 | start 时评估 while，若 false 则不压栈，直接返回 complete |

#### 控制流嵌套组合

控制流结构可相互嵌套，脚本需正确处理所有组合：

| 外层 | 内层 | 说明 |
|------|------|------|
| sequence | switch/triggers | step 中的 call 可触发分支逻辑 |
| sequence | loop | step 中的 call 可进入循环 |
| sequence | sequence | 嵌套序列，$prev 逐层传递 |
| switch (DFA) | sequence/loop/call | 分支命中后执行任意控制流 |
| triggers (NFA) | sequence/loop/call | 多分支按序执行，各分支可含任意控制流 |
| loop | switch/triggers | 循环体内可含分支逻辑 |
| loop | sequence | 循环体内可执行序列 |
| 递归 | 任意 | tail_call 自身形成递归，栈帧复用 |

**处理原则**：
- 脚本按统一模式处理：读取 on_complete → 分发到对应 handler → 递归处理内层
- 栈帧管理是核心：push/pop/tail_call 保证状态一致
- return 时向上冒泡，直到找到需继续执行的点或栈空

---

### 四、混合表达式评估系统设计

#### 4.1 问题分析：评估需求的多样性

AI 介入的场景不仅是"条件判断"（返回 bool），还包括"表达式求值"（返回任意值）：

| 场景 | 输入 | 输出 | 示例 |
|------|------|------|------|
| **条件判断** | 表达式 | bool | `$count < 10` → true |
| **算术求值** | 表达式 | 数值 | `$count + 1` → 6 |
| **语义判断** | 表达式 | bool | `$result 表示成功` → true |
| **语义求值** | 表达式 | 任意值 | `根据 $a 和 $b 情况选择策略` → "aggressive" |

**语义求值的典型场景**：
- 综合决策：`根据 $error_type 和 $retry_count 决定下一步动作` → "retry" / "skip" / "escalate"
- 信息提取：`从 $output 中提取错误原因` → "connection timeout"
- 条件组合：`情况 A ($has_error) 和 情况 B ($is_critical) 同时出现时的处理方式` → "immediate_alert"

#### 4.2 核心设计原则：eval 失败即交给 AI

**简化策略**：不用关键词列表猜测，直接尝试执行

```
表达式 → 变量替换 → safe_eval()
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    执行成功                        执行失败
    返回结果                     （语法错误/不支持的操作）
         │                             │
         ▼                             ▼
    脚本继续处理                  交给 fn-controller
                                 进行语义评估/求值
```

**为什么不用关键词识别**：
- ❌ 条件可能是中文：`$结果 表示成功`
- ❌ 英文关键词枚举不完：indicates, suggests, implies, means, shows, represents...
- ❌ 误判风险：`$status == 'indicates_error'` 会被误判为语义条件
- ✅ **简单可靠**：能 eval 就 eval，不能就交给 AI

#### 4.3 混合评估架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      表达式评估请求                               │
│  expression: "$count + 1"  或  "$result 表示成功"                │
│  context: {count: 5, result: "所有测试通过"}                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    fn_execute.py 脚本                            │
│  1. 变量替换: "$count + 1" → "5 + 1"                            │
│  2. 尝试 safe_eval()                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     ┌────────────────┐              ┌────────────────────┐
     │  eval 成功      │              │  eval 失败          │
     │  result: 6     │              │  (任何原因)          │
     └────────────────┘              └────────────────────┘
              │                               │
              ▼                               ▼
     ┌────────────────┐              ┌────────────────────┐
     │  脚本继续执行   │              │  输出问题 + 挂起    │
     └────────────────┘              │<<CC_FN_INPUT_NEEDED>>│
                                     └────────────────────┘
                                              │
                                              ▼
                                     ┌────────────────────┐
                                     │  fn-controller      │
                                     │  读取问题，评估     │
                                     │  回写 agent_input   │
                                     └────────────────────┘
                                              │
                                              ▼
                                     ┌────────────────────┐
                                     │  脚本读取答案       │
                                     │  继续执行          │
                                     └────────────────────┘
```

#### 4.4 评估函数实现（简化版）

```python
def try_eval(expression: str, context: dict) -> dict:
    """
    尝试评估表达式
    
    Returns:
        成功: {"success": True, "value": <result>}
        失败: {"success": False, "reason": "...", "needs_ai": True}
    """
    # 1. 变量替换
    resolved = substitute_vars(expression, context)
    
    # 2. 尝试 safe_eval
    try:
        result = safe_eval(resolved)
        return {"success": True, "value": result, "resolved": resolved}
    except Exception as e:
        # eval 失败 → 交给 AI（包括语法错误、类型错误、语义表达式）
        return {
            "success": False,
            "reason": str(e),
            "needs_ai": True,
            "resolved": resolved
        }
```

**关键点**：
- 没有复杂的分类逻辑，只有"能 eval"和"不能 eval"两种情况
- 所有 eval 失败都交给 AI 兜底（包括语法错误、类型错误）
- AI 具备理解能力，可以处理各种异常情况

#### 4.5 AI 评估输出格式

> 脚本输出**自然语言**给 AI，而非 JSON 结构。AI 只需回答问题即可。

**场景 1：条件判断（期望 bool）**

脚本输出：
```
需要你判断以下条件是否成立：

条件：'测试输出: 3通过, 1失败' 表示成功

请回答 true 或 false
<<CC_FN_INPUT_NEEDED>>
```

AI 回写 `agent_input.txt`：
```
false
<<CC_FN_INPUT_END>>
```

**场景 2：分支选择（期望整数编号）**

脚本输出：
```
请根据以下情况选择分支：

当前状态：error_type='timeout', is_critical=true

分支选项：
  0: $retry_count >= 3（已重试3次以上则放弃）
  1: $error_code == 'TIMEOUT'（超时错误则重试）
  2: $error 是可恢复的（可恢复则尝试恢复）
  3: 默认（升级处理）

请回答分支编号（整数）
<<CC_FN_INPUT_NEEDED>>
```

AI 回写：
```
1
<<CC_FN_INPUT_END>>
```

**场景 3：语义求值（期望特定格式）**

脚本输出：
```
需要你进行语义评估：

表达式：综合 5 个错误和类型 ['warning', 'error', 'critical'] 评估严重程度

请回答严重程度，可选值：low / medium / high / critical
<<CC_FN_INPUT_NEEDED>>
```

AI 回写：
```
high
<<CC_FN_INPUT_END>>
```

**设计原则**：
- 脚本输出自然语言问题，非 JSON
- 函数定义作者在 function 中定义问题模板和合法格式提示
- 脚本只做变量替换和原样输出，不解析 valid_values 等字段

#### 4.6 AI 回写评估结果

通过 `agent_input.txt` 文件回写答案：

```bash
# 条件判断结果 (bool)
Write(agent_input.txt, "false\n<<CC_FN_INPUT_END>>")

# 分支选择结果 (int)
Write(agent_input.txt, "1\n<<CC_FN_INPUT_END>>")

# 语义求值结果 (string)
Write(agent_input.txt, "escalate\n<<CC_FN_INPUT_END>>")
```

脚本读取答案后，自动根据上下文解析类型并继续执行。

#### 4.7 函数定义示例

```json
{
  "on_complete": {
    "type": "switch",
    "cases": [
      {"case": "$mode == 'A'", "then": {"tail_call": "handler_a"}},
      {"case": "$review_result 符合质量标准", "then": {"tail_call": "approve"}},
      {"case": "$code 存在安全漏洞", "then": {"tail_call": "security_review"}},
      {"default": {"type": "return"}}
    ]
  }
}
```

**评估策略**：
- 所有条件先尝试 safe_eval
- eval 失败自动交给 AI（无需显式标记）
- AI 作为统一兜底，简化设计

#### 4.8 safe_eval 实现（精简版）

```python
import ast
import operator
from typing import Any

SAFE_OPS = {
    # 算术
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
    # 比较
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    # 成员
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 允许的名称（统一 null 处理）
SAFE_NAMES = {
    'True': True, 'False': False,
    'None': None, 'null': None,  # JSON null → Python None
}

def safe_eval(expr: str) -> Any:
    """
    安全的表达式求值
    
    支持：算术、比较、逻辑、成员测试、字面量、null/None
    不支持：函数调用、属性访问、未知变量
    
    失败时抛出异常（由调用者捕获并交给 AI）
    """
    tree = ast.parse(expr, mode='eval')
    return _eval(tree.body)

def _eval(node) -> Any:
    # 字面量
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(el) for el in node.elts]
    
    # 名称（True/False/None/null）
    if isinstance(node, ast.Name):
        if node.id in SAFE_NAMES:
            return SAFE_NAMES[node.id]
        raise ValueError(f"Unknown name: {node.id}")
    
    # 一元操作
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval(node.operand)
        if isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        raise ValueError(f"Unsupported: {type(node.op)}")
    
    # 二元操作
    if isinstance(node, ast.BinOp):
        op = SAFE_OPS.get(type(node.op))
        if op:
            return op(_eval(node.left), _eval(node.right))
        raise ValueError(f"Unsupported: {type(node.op)}")
    
    # 比较操作
    if isinstance(node, ast.Compare):
        left = _eval(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp)
            op_func = SAFE_OPS.get(type(op))
            if not op_func or not op_func(left, right):
                return False
            left = right
        return True
    
    # 布尔操作
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval(v) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval(v) for v in node.values)
    
    raise ValueError(f"Unsupported: {type(node)}")
```

**设计原则**：
- 能 eval 的：数值、字符串、列表、算术、比较、逻辑、`null`/`None`
- 不能 eval 的（抛异常）：中文、自然语言、函数调用、未知变量
- **异常 = 交给 AI**，无需复杂分类
- **null 统一**：JSON `null` 和 Python `None` 等价

#### 4.9 fn-controller 处理 AI 评估请求

当脚本输出 `<<CC_FN_INPUT_NEEDED>>` 时，表示需要 AI 评估。

**处理流程**：
1. 读取 `agent_output.txt` 中的问题内容
2. 理解问题并给出答案
3. 将答案写入 `agent_input.txt`（必须以 `\n<<CC_FN_INPUT_END>>` 结尾）

**示例 1：条件判断**

脚本输出：
```
需要你判断以下条件是否成立：
条件：'测试: 3通过 1失败' 表示成功
请回答 true 或 false
<<CC_FN_INPUT_NEEDED>>
```

fn-controller 评估：有 1 个失败 → 不算成功 → false

回写：
```
false
<<CC_FN_INPUT_END>>
```

**示例 2：分支选择**

脚本输出：
```
请选择分支编号：
  0: 重试次数 >= 3
  1: 错误类型为 TIMEOUT
  2: 默认处理
当前：timeout 错误，已重试 2 次
<<CC_FN_INPUT_NEEDED>>
```

fn-controller 评估：timeout 错误匹配分支 1

回写：
```
1
<<CC_FN_INPUT_END>>
```

#### 4.10 条件设计指南

**核心原则**：可靠性优先，脚本能处理的不交给 AI。

| 条件类型 | 示例 | 处理方 |
|----------|------|--------|
| 数值比较 | `$count < $max` | 脚本 eval |
| 字符串匹配 | `$mode == 'debug'` | 脚本 eval |
| 成员测试 | `$status in ['ready', 'pending']` | 脚本 eval |
| 逻辑组合 | `$count > 0 and $mode == 'auto'` | 脚本 eval |
| 语义判断 | `$result 表示成功` | eval 失败 → AI |

**最佳实践**：
- **确定性前置**：将确定性条件放在前面（快速短路），语义性条件放后面
- **明确阈值**：`$count is large`（不明确）→ 改用 `$count > 100`

**safe_eval 支持**：算术（`+ - * /`）、比较（`== != < > <= >=`）、逻辑（`and or not`）、成员（`in not in`）、字面量（数值、字符串、bool、列表）

**null 处理**：统一使用 Python `None`，JSON 序列化为 `null`，safe_eval 中 `null` 映射为 `None`

---

### 五、脚本语言选择 ✅ 已决策

**全局决策**：优先使用 `.py` 脚本，逐步减少 `.ps1` 脚本依赖。

**核心理由**：
- Python 可维护性显著优于 PowerShell（语法清晰、JSON 原生支持、无编码坑）
- 跨平台兼容性更好
- 调试和测试更容易（pytest vs Pester）

**规范**：新脚本必须使用 Python，现有 ps1 在修改时优先迁移。

---

### 六、优化方案设计

#### 6.0 状态机总览

```
fn_execute.py 脚本状态机（支持 start 和 continue 两种入口）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────────────────────────┐
                    │                   脚本启动入口                        │
                    │         start <func> [args] 或 continue ...         │
                    └─────────────────────────────────────────────────────┘
                                              │
                         ┌────────────────────┴────────────────────┐
                         │                                         │
                         ▼                                         ▼
          ┌──────────────────────────┐              ┌──────────────────────────┐
          │     start <func>         │              │     continue ...         │
          │  初始化栈，push 首帧      │              │  从 state.json 恢复栈    │
          └──────────────────────────┘              └──────────────────────────┘
                         │                                         │
                         └────────────────────┬────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                        RUNNING                                            │
│                                     （执行控制流）                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  resolve → read_fn → eval_conditions → route_on_complete → stack_ops               │  │
│  └─────────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────────┘
          │                    │                    │
          │ 输出 task          │ 遇到语义表达式      │ 栈空
          │                    │                    │
          ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   OUTPUT_TASK    │  │  AWAITING_EVAL   │  │     COMPLETE     │
│                  │  │ （等待 AI 评估）  │  │    （执行完成）   │
│ 1. 保存状态      │  │                  │  │                  │
│ 2. 输出 task     │  │ 输出问题 +       │  │ 输出结果         │
│ 3. 脚本退出      │  │<<CC_FN_INPUT_    │  │ 脚本退出         │
│   (等待continue) │  │ NEEDED>>         │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                     │
         │                     │ subagent 语义评估
         │                     │ 回写 agent_input.txt
         │                     │
         │                     ▼
         │            ┌──────────────────┐
         │            │  脚本读取答案     │
         │            │  继续执行        │
         │            └──────────────────┘
         │                     │
         │                     ▼
         │               回到 RUNNING
         │
         │  ════════════════════════════════════════════════════
         │  ║ 脚本进程已退出，状态已持久化到 state.json         ║
         │  ║ 等待主会话执行 task 后，调用 subagent continue   ║
         │  ════════════════════════════════════════════════════
         │
         └──────────────► 下次 continue task_result=... ──────────┐
                                                                  │
                                                                  ▼
                                                         回到脚本启动入口
```

**状态说明**：

| 状态 | 脚本行为 | subagent 行为 |
|------|----------|---------------|
| **start** | 初始化栈，push 首帧 | 启动脚本 |
| **continue** | 从 state.json 恢复栈 | 启动脚本（resume 或新建 subagent） |
| **RUNNING** | 执行控制流逻辑 | 等待脚本输出 |
| **OUTPUT_TASK** | 保存状态，输出 task，**退出** | 返回 task 给主会话，等待下次 continue |
| **AWAITING_EVAL** | 输出问题，**挂起等待** | 语义评估，回写答案，脚本继续 |
| **COMPLETE** | 输出结果，退出 | 返回完成状态 |

**关键区别**：

| 场景 | 脚本行为 | 交互机制 | subagent 行为 |
|------|----------|----------|---------------|
| **遇到语义表达式** | 挂起等待 | `<<CC_FN_INPUT_NEEDED>>` + `agent_input.txt` | 内部闭环评估 |
| **输出 task** | 保存状态，退出 | 无（状态持久化） | 返回主会话，等待 continue |
| **栈空 complete** | 退出 | 无 | 返回完成状态 |

**设计理由**：
- **语义评估**在 subagent 内部闭环完成，使用交互式机制，无需主会话介入
- **task 执行**需要主会话介入，脚本退出后状态持久化，支持 subagent 替换（混合方案）

#### 6.1 执行器：`fn_execute.py`

> 基于 [AI 语义理解交互模式](./ai-semantic-interactive-pattern.md) 框架。
> 脚本在**语义评估**时作为持久进程挂起，在**输出 task** 时保存状态后退出。

**启动方式**：
```bash
# 通过 wrapper 启动执行器
PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py \
    scripts/fn_execute.py start <function> [args...]

# 或 continue（从 state.json 恢复）
PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py \
    scripts/fn_execute.py continue task_result="..."

# 等待并获取输出
bash scripts/wait_for_status.sh
```

**支持的指令**（命令行参数）：

| 指令 | 格式 | 说明 |
|------|------|------|
| start | `start <function> [arg1=val1 ...]` | 启动函数执行 |
| continue | `continue task_result=...` | task 执行完成后继续 |

**参数格式规范**（统一使用 `key=value`）：
```bash
# start 指令 - 函数参数
start tests/test_loop count=0 max=5
start my_func name="hello world" debug=true

# continue 指令 - task 执行结果
continue task_result="执行成功，输出为 xyz"
```

**语义评估答案**（通过 agent_input.txt 传入，在脚本挂起时）：
```bash
# bool 答案
true

# 整数答案（分支编号）
2

# 字符串答案
escalate
```

**参数值类型自动推断**：
- `true` / `false` → bool
- 纯数字 → int
- 带引号 `"..."` → string（保留原值）
- 其他 → string

**eval-id 格式规范**（脚本内部使用）：
| 场景 | ID 格式 | 示例 |
|------|---------|------|
| switch 条件 | `sw_cond_{index}` | `sw_cond_0`, `sw_cond_1` |
| triggers 条件 | `tg_cond_{index}` | `tg_cond_0`, `tg_cond_1` |
| loop while 条件 | `loop_while` | `loop_while` |

#### 6.2 输出格式

> 脚本通过 `agent_output.txt` 输出**自然语言**，非 JSON。

**情况 1：返回 task 给主会话执行**（脚本保存状态后退出）

**脚本输出**：
```
=== CC_FN_COMPLETE ===
EXIT_CODE: 0

[TASK]
prompt: Execute: Bash(echo "[test_loop] iteration 1 of 5")
execute_in: main
stack_depth: 1
function: tests/test_loop

Next: Call subagent fn-controller with continue, pass task_result.
```

**subagent 行为**：
1. 识别 `CC_FN_COMPLETE` → 知道脚本已退出
2. 识别 `[TASK]` → 知道这是 task 输出
3. **直接截取 `[TASK]` 后的内容转发给主会话**（不解析、不组装）

**主会话收到的内容**（subagent 直接转发）：
```
prompt: Execute: Bash(echo "[test_loop] iteration 1 of 5")
execute_in: main
stack_depth: 1
function: tests/test_loop

Next: Call subagent fn-controller with continue, pass task_result.
```

> subagent 只需识别标记并截取转发，不需要解析或组装 JSON。

**情况 2：需要 AI 语义评估**

```
=== CC_FN_TURN 2 ===
STATUS: CC_FN_WAITING_FOR_INPUT

[EVAL] 需要你进行语义评估：

条件：'The review found 2 minor style issues but no bugs' indicates code is production-ready

请回答 true 或 false
<<CC_FN_INPUT_NEEDED>>
```

**情况 3：需要 AI 选择分支（batch 模式）**

```
=== CC_FN_TURN 3 ===
STATUS: CC_FN_WAITING_FOR_INPUT

[EVAL] 需要你评估以下条件（可能有多个为 true）：

当前状态：has_error=true, needs_cleanup=true, should_notify=false

条件列表：
  0: $has_error（有错误）
  1: $needs_cleanup（需要清理）
  2: $should_notify（需要通知）

请回答所有为 true 的条件编号，用逗号分隔（如：0,1）
<<CC_FN_INPUT_NEEDED>>
```

**情况 4：执行完成**

**脚本输出**：
```
=== CC_FN_COMPLETE ===
EXIT_CODE: 0

[COMPLETE]
result: All tasks completed successfully
```

**subagent 行为**：识别 `[COMPLETE]`，截取后续内容转发。

**主会话收到的内容**：
```
result: All tasks completed successfully
```

**triggers 处理**：脚本内部将命中的多分支转换为隐式 sequence 按序执行，由脚本处理，无需 AI 介入。

#### 6.3 简化后的 fn-controller 提示词

从 **509 行** 压缩到约 **70 行**：

```markdown
# fn-controller

函数执行控制器，通过脚本管理函数调用栈。

## 启动

```bash
PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py \
    scripts/fn_execute.py start <function> [arg1=val1 ...]
```

## 交互循环

1. 执行 `bash scripts/wait_for_status.sh` 等待输出
2. 首行 `CC_FN_AGENT_INPUT_PATH=...` 是回写路径（仅 [EVAL] 时使用）
3. 检查输出内容，按情况处理：

### 情况 A: [EVAL] + CC_FN_WAITING_FOR_INPUT（脚本挂起中）
- 进行语义评估
- 回写答案：`Write(agent_input.txt, "答案\n<<CC_FN_INPUT_END>>")`
- 回到步骤 1（脚本继续执行）

### 情况 B: [TASK] + CC_FN_COMPLETE（脚本已退出）
- 截取 `[TASK]` 后的内容，直接转发给主会话
- 主会话执行 task 后，会再次调用你执行 continue

### 情况 C: CC_FN_COMPLETE（无 [TASK]，无 [EVAL]）
- 执行完成，返回结果给主会话

## continue（主会话执行完 task 后调用）

```bash
PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py \
    scripts/fn_execute.py continue task_result="执行结果..."
```

## 评估类型

| 标记 | 期望答案 | 示例 |
|------|----------|------|
| 请回答 true 或 false | bool | `true` |
| 请回答分支编号 | int | `1` |
| 请回答...编号，用逗号分隔 | int 列表 | `0,1,3`（batch 模式） |
| 请回答 X/Y/Z | 选项之一 | `high` |

## 重要约定

- [EVAL] 回写必须以 `\n<<CC_FN_INPUT_END>>` 结尾
- 评估答案格式错误时，脚本会重新提示，最多 3 次
- 脚本处理所有控制流逻辑，你只需回答问题

## 输出格式

截取 `[TASK]` 或 `[COMPLETE]` 后的内容，直接转发给主会话。无需解析或组装。


#### 6.4 脚本内部架构

```
fn_execute.py（交互式持久进程）
│
├── main()                          # 入口
│   ├── parse_command()             # 解析 start/continue 指令
│   └── main_loop()                 # 主循环
│
├── handle_start(function, args)    # start 指令处理
├── handle_continue(input)          # continue 指令处理（task_result 或 eval_answer）
│
├── resolve_function()              # 复用 resolve_fn.py 逻辑，直接调用已经实现好的脚本
├── read_function()                 # 读取函数定义 JSON
├── substitute_vars()               # 变量替换（保持类型，JSON 序列化）
│
├── route_on_complete()             # 路由分发
│   ├── handle_return()
│   ├── handle_call()
│   ├── handle_tail_call()
│   ├── handle_switch()             # 逐个评估条件，eval 失败则请求 AI 选择分支
│   ├── handle_triggers()           # 集中评估，命中分支转隐式 sequence
│   ├── handle_sequence()           # 管理 step_index 和 $prev
│   └── handle_loop()               # while 条件 + 新参数计算
│
├── try_eval(expr, context)         # 尝试评估表达式
│   └── safe_eval()                 # 确定性求值，失败则返回 None
│
├── request_ai_eval(question)       # 输出问题 + <<CC_FN_INPUT_NEEDED>>，挂起等待
├── output_task(task)               # 输出任务，保存状态，退出（等待 continue）
│
└── stack_ops integration           # 栈操作（复用 stack_ops.py）
```

**核心原则**：
- 能 eval 就 eval，不能就交给 AI
- 控制流逻辑 100% 脚本化
- AI 只负责语义评估

---

### 七、方案优势总结

| 维度 | 当前 | 优化后 | 改善 |
|------|------|--------|------|
| **工具调用次数** | 3-5 次/操作 | 1-2 次/操作 | 2-5x 效率 |
| **提示词长度** | 509 行 | ~80 行 | 6x 压缩 |
| **AI 认知负担** | 高（全部控制流逻辑） | 低（仅转发 + 语义评估） | 显著降低 |
| **确定性流程** | 依赖 AI 推理 | 100% 脚本化 | 可靠性提升 |
| **语义性判断** | 混在控制流中 | 明确分离，按需介入 | 职责清晰 |
| **可调试性** | 难（AI 黑箱） | 详细日志 + 评估追踪 | 显著提升 |
| **可测试性** | 难 | 脚本独立测试 | 显著提升 |
| **扩展性** | 改提示词 | 改脚本逻辑 | 更可控 |

#### 7.1 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| **交互模式** | 语义评估时挂起，输出 task 时退出 | 兼顾交互性和 subagent 替换 |
| **信息分层** | subagent 识别标记后截取转发，不解析不组装 | 简单可靠 |
| **条件评估** | eval 失败即交给 AI | 简单可靠，AI 兜底 |
| **条件分支** | switch (DFA) + triggers (NFA) | 区分单分支/多分支语义 |
| **变量替换** | JSON 序列化，保持类型 | 避免字符串/数值混淆 |
| **AI 结果验证** | 脚本验证 + 最多重试 3 次 | 防止非法值，控制成本 |
| **$prev 作用域** | 帧级变量 | 子函数不影响父函数 |
| **sequence return** | 最后一个 $prev | 语义明确 |
| **null 表示** | Python `None`，JSON `null` | 统一术语 |
| **实现语言** | Python 为主 | 维护成本低，功能强 |

#### 7.2 AI 介入的边界

```
┌─────────────────────────────────────────────────────────────┐
│               fn_execute.py 脚本负责（确定性）                │
├─────────────────────────────────────────────────────────────┤
│ ✓ 函数解析、读取                                             │
│ ✓ 栈操作（push, pop, tail_call, return）                     │
│ ✓ 变量替换（$var → value，保持类型）                          │
│ ✓ 确定性条件评估（数值比较、字符串匹配、布尔逻辑）              │
│ ✓ 控制流决策（switch/triggers/sequence/loop 路由）           │
│ ✓ triggers 隐式 sequence 执行                                │
│ ✓ 输出格式化（自然语言问题）                                  │
│ ✓ 答案验证与重试                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               fn-controller AI 负责（语义性）                 │
├─────────────────────────────────────────────────────────────┤
│ ✓ 启动脚本、管理交互循环                                      │
│ ✓ 语义条件评估（eval 失败时兜底）                             │
│ ✓ 分支选择（多个语义条件时选择编号）                           │
│ ✓ 将 task 返回给主会话执行                                    │
│ ✓ 将执行结果回写给脚本                                        │
└─────────────────────────────────────────────────────────────┘
```

---

### 八、实施建议

#### Phase 1: 核心脚本开发

1. **创建 `fn_execute.py`**（交互式持久进程）
   - 整合 `resolve_fn.py` 和 `stack_ops.py` 逻辑（复用和调用已经实现脚本，不要将其它脚本内容再平铺到 fn_execute.py， 逻辑是分层的不要总想着一个脚本完整实现所有内容，要模块化实现功能）
   - 实现 `handle_start`, `handle_continue`
   - 实现各 `on_complete` 类型处理器（switch/triggers/sequence/loop）
   - 实现 `request_ai_eval()` 和 `request_task_exec()` 交互点

2. **实现 safe_eval**
   - 支持算术、比较、逻辑、成员测试
   - eval 失败统一交给 AI
   - `null` 映射为 Python `None`

3. **自然语言输出**
   - 将评估请求转换为清晰的问题
   - 支持 bool、int、int 列表、选项等答案格式

#### Phase 2: 测试验证

4. **单元测试**
   - safe_eval 各种表达式测试
   - 各控制流类型测试
   - 嵌套场景测试

5. **集成测试**
   - 使用 `functions/tests/` 下的测试函数
   - 验证 start → 交互循环 → complete 全流程
   - 验证 AI 评估请求和答案处理

#### Phase 3: 提示词更新

6. **更新 fn-controller 提示词**
   - 压缩至 ~60 行
   - 交互循环说明
   - 评估类型和答案格式表

7. **文档更新**
   - 条件设计最佳实践
   - 语义性条件编写指南

---

### 九、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| eval 失败频繁 | AI 调用增加 | 函数作者优先使用确定性条件 |
| AI 评估不一致 | 相同条件不同结果 | 问题清晰 + 明确答案格式 |
| 脚本 bug | 控制流错误 | 全面测试 + 日志追踪 |
| 答案格式错误 | 重试消耗 | 最多 3 次重试 + 明确提示 |

---

### 十、待解决问题与设计决策

> 本节记录方案审视中发现的问题及决策

#### 10.1 状态一致性问题 ✅ 已解决

**问题**：脚本执行到一半返回 `needs_ai_eval` 时，栈状态可能已部分修改。

```
场景：sequence 的 step[1] 处理
1. 脚本读取 step_index = 1
2. 脚本 update step_index = 2  ← 已修改栈状态
3. 脚本尝试 eval step.args.data = "根据 $x 决定..." → 失败
4. 返回 needs_ai_eval
→ 如果 AI 评估后用户取消，step_index 已经是 2，重试会跳过 step[1]
```

**难点**：有时需要评估的内容，依赖脚本运行过程中的中间结果。

**候选方案**：

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **方案一：协程模式** | 单线程有栈协程，执行到 AI 点切出，数据准备好后 resume 无感继续 | 最自然，状态自动保持 | Python 协程实现复杂，需要 yield 侵入 |
| **方案二：多线程+条件变量** | 工作线程阻塞等待 AI 结果，另一线程获取数据后通知 | 逻辑清晰 | 线程管理复杂，可能有竞态 |
| **方案三：交互式脚本** | 脚本作为持久进程，通过 stdin/stdout 与 fn-controller 交互 | 状态天然保持 | 对 AI/Agent 交互要求高，进程管理复杂 |
| **方案四：延迟提交** | 先完成所有评估，确认能继续后再一次性修改栈状态 | 简单，无需复杂机制 | 无法处理依赖中间状态的评估 |

**决策**：采用 **方案三：交互式脚本**，该方案已验证可行。

> 📄 **解决方案详见**：[AI 语义理解交互模式](./ai-semantic-interactive-pattern.md)
>
> 该文档定义了完整的交互式脚本框架，包括：
> - 文件系统通信桥 + 状态嵌入输出文件
> - 主进程包装器 `scripts/interactive_wrapper.py`
> - 预授权等待脚本 `scripts/wait_for_status.sh`
> - 会话隔离目录 `scripts/states/<session>/`
> - AI 交互循环协议
>
> **验证状态**：2026-02-03，8 轮测试全部通过

**核心优势**：
- 状态天然保持：脚本作为持久进程运行，无需担心中途状态丢失
- 可靠的通信机制：通过文件系统桥接，避免 stdin/stdout 缓冲问题
- 会话隔离：支持多实例并行运行

#### 10.2 变量类型保持 ✅ 已决策

**问题**：变量替换后丢失类型信息

```python
# args 中是数值
{"count": 5, "max": 10}
"$count < $max" → "5 < 10"  # ✅ OK

# 如果 args 中是字符串
{"count": "5", "max": "10"}
"$count < $max" → "'5' < '10'"  # 字符串比较，结果错误！
```

**决策**：
1. 变量替换时**保留类型**：数值不加引号，字符串加引号
2. 替换使用 `json.dumps(value)` 进行序列化
3. 语义评估结果的类型由处理脚本或 function 定义约束

```python
def substitute_var(value):
    """变量替换时保持类型"""
    if isinstance(value, str):
        return json.dumps(value)  # "hello" → '"hello"'
    elif isinstance(value, bool):
        return "True" if value else "False"
    elif isinstance(value, (int, float)):
        return str(value)  # 5 → "5" (无引号)
    elif isinstance(value, (list, dict)):
        return json.dumps(value)
    else:
        return json.dumps(str(value))
```

#### 10.3 特殊字符转义 ✅ 已决策

**问题**：变量值包含引号时可能破坏表达式

**决策**：变量替换时统一使用 JSON 序列化（`json.dumps`），自动处理转义

```python
# 原始值
message = 'User said: "Hello"'

# 替换后（JSON 序列化）
'"User said: \\"Hello\\""'  # 正确转义
```

#### 10.4 safe_eval 支持范围 ✅ 已决策

**问题**：5.6 节推荐的 `'success' in $output.lower()` 与 safe_eval 能力矛盾

**决策**：
1. 删除 `.lower()` 推荐写法
2. safe_eval 保持简单，**不支持**方法调用、属性访问
3. 需要字符串处理时，使用语义评估或在 task 中预处理

**反模式表**：

| 反模式 | 问题 | 改进 |
|--------|------|------|
| `$count is large` | "large" 不明确，eval 会失败交 AI | `$count > 100`（确定性） |
| `$output == 'success'` | 输出可能有变化 | `$output indicates success`（让 AI 评估） |
| 连续多个语义条件 | AI 调用次数多 | 合并条件或提前计算 |
| 语义条件放在前面 | 无法短路优化 | 确定性条件前置 |

#### 10.5 动态 target ❌ 已移除

**原设计**：支持 `target: "handle_$severity"` 动态函数名。

**移除原因**：
1. **复杂度高**：引入循环依赖问题（target 依赖 args，args 可能需要语义评估）
2. **可替代**：switch 分支可完全实现相同功能，且更清晰
3. **奥卡姆剃刀**：如无必要勿增实体

**替代方案**（使用 switch）：
```json
{
  "type": "switch",
  "cases": [
    {"case": "$severity == 'low'", "then": {"tail_call": "handle_low"}},
    {"case": "$severity == 'high'", "then": {"tail_call": "handle_high"}},
    {"default": {"tail_call": "handle_default"}}
  ]
}
```

#### 10.6 条件分支设计：switch vs triggers ✅ 已决策

**问题**：单分支命中（DFA）与多分支命中（NFA）是两种不同语义，不应混用

**分析**：
- `when` 关键字暗示 NFA 语义（"每当...时"），但原设计实际是 DFA
- 两种场景都常见，应分别支持

**决策**：引入两种结构，明确区分语义

---

##### 10.6.1 `switch` - DFA 单分支语义

```json
{
  "type": "switch",
  "cases": [
    {"case": "$retry_count >= 3", "then": {"type": "return", "value": "max_retries"}},
    {"case": "$error_code == 'TIMEOUT'", "then": {"tail_call": "retry"}},
    {"case": "$error 是可恢复的", "then": {"tail_call": "recover"}},
    {"default": {"tail_call": "escalate"}}
  ]
}
```

**执行语义**：
- 按序评估 `case` 条件
- **首个为 true 即执行 `then`，然后停止**
- 可短路：确定性条件匹配后无需继续评估后续条件
- 无匹配且无 `default` 时，隐式 return null

**返回值**：命中分支的执行结果
- 若 `then` 是 `return`：直接返回 `value`
- 若 `then` 是 `call`/`tail_call`：返回被调用函数的返回值
- **推荐**：分支中的函数调用优先使用 `tail_call`（栈帧复用，效率更高）

**关键字**：`case` / `then` / `default`

**default 语法说明**：`default` 直接跟 action，无需 `then` 包裹
```json
{"default": {"tail_call": "fallback"}}  // ✅ 推荐用 tail_call
{"default": {"type": "return"}}         // ✅ 直接返回
```

**适用场景**：路由决策、状态机转换、错误处理分发

---

##### 10.6.2 `triggers` - NFA 多分支语义

```json
{
  "type": "triggers",
  "rules": [
    {"when": "$has_error", "do": {"call": "log_error"}},
    {"when": "$needs_cleanup", "do": {"call": "cleanup"}},
    {"when": "$should_notify", "do": {"call": "send_notification"}}
  ],
  "on_none": {"type": "return"}
}
```

**执行语义（NFA 模型）**：
- **集中评估**：先评估所有 `when` 条件（基于同一状态快照）
- **按序尝试**：命中分支按定义顺序依次执行
- **$prev 共享**：同层级所有分支的 `$prev` 相同（来自父帧），分支间不传递
- **分支独立**：每个分支独立执行到底，其返回值被丢弃（除最后一个）
- **返回值**：最后一个命中分支的返回值
- **无命中**：执行 `on_none`，若无则隐式 return null

**执行示例**：
```
triggers 命中 [rule_0, rule_2]，父帧 $prev = "initial"
├─ rule_0.do: call log_error（$prev="initial"）→ return "logged" → 丢弃
├─ rule_2.do: call cleanup（$prev="initial"）→ return "cleaned"
└─ triggers return "cleaned"（最后分支的返回值）
```

**关键字**：`when` / `do` / `on_none`

**适用场景**：钩子执行、多副作用触发、观察者模式

**与 switch 的关键区别**：
- switch：首个命中即停（DFA），可短路优化
- triggers：所有命中都执行（NFA），分支独立

---

##### 10.6.3 对比表

| 特性 | `switch` | `triggers` |
|------|----------|------------|
| 语义模型 | DFA（确定性） | NFA（非确定性） |
| 关键字 | `case/then/default` | `when/do/on_none` |
| 匹配模式 | 首个命中即停 | 所有命中都执行 |
| 评估方式 | 可短路或批量 | 必须集中（批量） |
| 执行次数 | 单分支 | 多分支按序 |
| 返回值 | 命中分支结果 | 最后分支结果 |

---

##### 10.6.4 脚本处理逻辑

**switch 处理**（按序 eval，失败则请求 AI 选择）：
```python
def process_switch(cases, frame):
    # 先尝试确定性评估
    for i, case_item in enumerate(cases):
        if case_item.get('default'):
            continue  # default 最后处理
        result = eval_condition(case_item['case'], frame)
        if result == True:
            # 确定性命中，直接执行
            return execute_action(case_item['then'])
        elif result == False:
            continue
        # result == None 表示 eval 失败，继续检查其他分支
    
    # 无确定性命中，检查是否有 eval 失败的分支
    failed_evals = []
    for i, case_item in enumerate(cases):
        if case_item.get('default'):
            continue
        if eval_condition(case_item['case'], frame) is None:
            failed_evals.append(i)
    
    if failed_evals:
        # 请求 AI 选择分支（输出所有分支，让 AI 选编号）
        return request_ai_branch_selection(cases, frame, failed_evals)
    
    # 无命中，执行 default 或隐式 return
    default_case = next((c for c in cases if c.get('default')), None)
    if default_case:
        return execute_action(default_case['default'])
    return handle_implicit_return(frame)  # return None
```

**triggers 处理**（集中评估，脚本内部执行隐式 sequence）：
```python
def process_triggers(triggers_obj, frame):
    """NFA 模型：所有命中分支按序执行"""
    rules = triggers_obj['rules']
    on_none = triggers_obj.get('on_none', {'type': 'return', 'value': None})
    
    # 第一遍：尝试确定性评估所有条件
    eval_results = {}
    pending_evals = []
    for i, rule in enumerate(rules):
        result = eval_condition(rule['when'], frame)
        if result is None:
            pending_evals.append(i)
        else:
            eval_results[i] = result
    
    if pending_evals:
        # 请求 AI 批量评估（返回所有为 true 的编号）
        return request_ai_batch_eval(rules, frame, pending_evals, eval_results)
    
    # 收集命中分支
    matched = [i for i, r in sorted(eval_results.items()) if r == True]
    if not matched:
        return execute_action(on_none)
    
    # 脚本内部执行隐式 sequence（不返回给 fn-controller）
    # 各分支共享同一 $prev（来自父帧），分支间不传递
    last_result = None
    for i in matched:
        last_result = execute_branch(rules[i]['do'], frame)
    return last_result
```

> **设计选择**：triggers 的隐式 sequence 由脚本内部处理，无需 AI 介入，符合"可靠性优先"原则。

---

##### 10.6.5 迁移说明

原有使用 `conditions` + `when` 的 switch 定义需迁移：

```json
// 旧格式（废弃）
{"type": "switch", "conditions": [{"when": "...", ...}]}

// 新格式 - 单分支场景
{"type": "switch", "cases": [{"if": "...", "then": {...}}]}

// 新格式 - 多分支场景
{"type": "triggers", "rules": [{"when": "...", "do": {...}}]}
```

#### 10.7 $prev 作用域与 sequence return 值 ✅ 已决策

**$prev 作用域**：帧级变量，每个栈帧独立

```
┌─────────────────────────────────────────────────────┐
│  $prev 是帧级变量                                    │
│  - 每个栈帧有自己的 $prev                            │
│  - 子函数的 $prev 不影响父函数                       │
│  - triggers 同层级分支共享同一 $prev（来自父帧）     │
└─────────────────────────────────────────────────────┘
```

**sequence return 值**：最后一个 $prev

```
A (sequence)
├─ step[0]: call B → return "b" → A.$prev = "b"
├─ step[1]: call C（可访问 A.$prev="b"）→ return "c" → A.$prev = "c"
└─ (完成) → A return "c" (即最后的 $prev)
```

**嵌套场景**：
```
A (sequence)
├─ step[0]: call B (sequence)
│           ├─ B.step[0]: call X → B.$prev = "x"
│           ├─ B.step[1]: call Y → B.$prev = "y"
│           └─ B return "y"
│           → A.$prev = "y"（B 的返回值）
├─ step[1]: call C（可访问 A.$prev="y"）
└─ ...
```

如果 sequence 没有任何 step 执行（空 sequence），return 值为 `None`（JSON 中为 `null`）

#### 10.8 AI 评估结果验证 ✅ 已决策

**问题**：AI 返回非法值怎么办

**决策**：
1. 脚本**验证 AI 返回值格式**（如期望 int 但收到字符串）
2. 不合法时重新输出问题，并提示上次答案无效
3. **默认最大重试次数**：3 次（避免 token 浪费）
4. 超过重试次数则报错退出

**重试输出示例**：
```
[EVAL] 需要你重新回答：

你上次回答了 "continue"，格式不正确。

请选择分支编号（整数）：
  0: 重试
  1: 跳过

请回答 0 或 1
<<CC_FN_INPUT_NEEDED>>
```

**验证规则**：
| 期望格式 | 验证逻辑 |
|----------|----------|
| bool | 必须是 `true` 或 `false` |
| int | 必须是整数，且在有效范围内 |
| int 列表 | 逗号分隔的整数，如 `0,1,3` |
| 选项 | 必须是提示中列出的选项之一 |

#### 10.9 extract_vars 机制 ❌ 移除

**问题**：5.5 节提到的 `extract_vars` 机制未定义

**决策**：机制不明确，暂时**移除**该最佳实践

如需此功能，应作为独立特性设计，包括：
- 谁负责提取（主会话 task 输出？脚本解析？）
- 提取失败处理
- 变量存储位置

#### 10.10 输入格式统一 ✅ 已决策

**问题**：命令行参数格式不统一

**决策**：采用交互式模式，通过 `agent_input.txt` 传入答案

**启动指令格式**（统一 `key=value`）：
```bash
# start 指令
start <function> [arg1=val1 arg2=val2 ...]

# 示例
start tests/test_loop count=0 max=5
start my_func name="hello world" debug=true
```

**语义评估答案格式**（通过 agent_input.txt 传入）：
| 场景 | 答案格式 | 示例 |
|------|----------|------|
| bool 条件 | `true` / `false` | `true` |
| 分支选择 | 整数编号 | `1` |
| 批量选择 | 逗号分隔整数 | `0,1,3` |
| 选项选择 | 选项值 | `high` |

**continue 参数格式**（通过命令行传入）：
```bash
continue task_result="执行成功，输出为 xyz"
```

**类型自动推断**：
- `true` / `false` → bool
- 纯数字 → int
- 逗号分隔数字 → int 列表
- 其他 → string

#### 10.11 schema 同步 📋 TODO

需要更新 `_schema.json` 支持：
- [ ] switch 新语法：`cases` + `case/then/default`
- [ ] triggers 新结构：`rules` + `when/do/on_none`
- [ ] 废弃旧语法：`conditions` + `when`
- [ ] 移除动态 target 支持

#### 10.12 状态文件路径统一 ✅ 已决策

**问题**：状态文件路径格式不一致

```
旧格式：scripts/states/<session>.json
新格式：scripts/states/<session>/state.json
```

**决策**：统一使用新格式 `scripts/states/<session>/state.json`

**必须**：所有需要获取 session 的都不能直接从环境变量中获取，只能通过调用脚本 get_session_id.py/ps1 的方式获取。

**原因**：
1. 与 [AI 语义理解交互模式](./ai-semantic-interactive-pattern.md) 保持一致
2. 会话目录可容纳多个文件（state.json、agent_output.txt、agent_input.txt）
3. 便于会话清理和管理

**需要更新的脚本**：
- [ ] `scripts/stack_ops.py` - `get_state_file()` 函数
- [ ] `scripts/check_chain.py` - 状态文件路径
- [ ] `scripts/check_chain.sh` - STATE_FILE 变量
- [ ] `scripts/run_chain.py` - state_file 变量
- [ ] `scripts/run_chain.ps1` - $StateFile 变量
- [ ] `scripts/test_stack_ops.py` - 测试中的路径

**目录结构**：
```
scripts/states/<session>/
├── state.json          # 栈状态（fn-controller 用）
├── agent_output.txt    # 对话 + 状态（AI 读取）
└── agent_input.txt     # AI 答案（脚本读取）
```

#### 10.13 fn-controller 脚本设计 📋 待实现

> 基于 [AI 语义理解交互模式](./ai-semantic-interactive-pattern.md) 框架

**核心思路**：`fn_execute.py` 在不同场景有不同行为：
- **语义评估**时：挂起等待 AI 回写答案（交互式）
- **输出 task** 时：保存状态后退出（非交互式）

**脚本设计**（简化示意）：

```python
# scripts/fn_execute.py

def main():
    cmd, args = parse_command()  # start/continue
    
    if cmd == 'start':
        state = initialize_stack(args['function'], args['params'])
    else:  # continue
        state = load_state()
        if 'task_result' in args:
            state = process_task_result(state, args['task_result'])
    
    # 执行循环
    while True:
        action = determine_next_action(state)
        
        if action['type'] == 'complete':
            print(f"执行完成。结果：{action['result']}")
            break  # 退出
        
        if action['type'] == 'task':
            # 输出任务，保存状态，退出（等待 continue）
            save_state(state)
            print("[TASK]")
            print(f"prompt: {action['prompt']}")
            print(f"execute_in: {action.get('execute_in', 'main')}")
            print(f"stack_depth: {len(state['stack'])}")
            print(f"function: {state['stack'][-1]['function']}")
            print()
            print("Next: Call subagent fn-controller with continue, pass task_result.")
            break  # 退出，等待下次 continue
            
        elif action['type'] == 'eval':
            # 输出评估问题，挂起等待 AI 回答
            print(f"[EVAL] {action['question']}")
            print("<<CC_FN_INPUT_NEEDED>>")
            answer = input().strip()  # 挂起，等待 agent_input.txt
            if not validate_answer(answer, action['expect']):
                continue  # 重试
            state = process_eval_answer(state, answer)
            # 继续循环，不退出

if __name__ == '__main__':
    main()
```

**fn-controller 调用流程**：

```bash
# 1. 启动（start）
PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py \
    scripts/fn_execute.py start my_func arg1=val1

# 2. 等待输出
bash scripts/wait_for_status.sh

# 3. 根据输出类型处理：

#    情况 A: [EVAL] - 脚本挂起中
#    → 语义评估
#    → 回写 agent_input.txt: "答案\n<<CC_FN_INPUT_END>>"
#    → 回到步骤 2（脚本继续执行）

#    情况 B: [TASK] + CC_FN_COMPLETE - 脚本已退出
#    → 提取 task 信息（prompt、execute_in）
#    → 返回给主会话（不暴露 CC_FN_* 协议信息）
#    → 主会话执行 task
#    → 主会话调用 subagent 执行 continue（resume 或新建）

#    情况 C: CC_FN_COMPLETE（无 [TASK]）- 执行完成
#    → 返回完成状态

# 4. continue（task 执行完成后）
PYTHONIOENCODING=utf-8 python -u scripts/interactive_wrapper.py \
    scripts/fn_execute.py continue task_result="执行结果..."

# 5. 回到步骤 2
```

**关键设计**：
- 语义评估：脚本挂起，subagent 内部闭环
- task 输出：脚本退出，支持 subagent 替换（混合方案）
- 信息分层：subagent 识别 `[TASK]`/`[COMPLETE]` 标记，截取后续内容直接转发，不解析不组装

#### 10.14 fn-controller 子代理复用策略 🔍 待验证

**问题**：fn-controller 子代理每次操作是启动全新实例还是复用已有实例？

**约束条件**（重要）：
- ❌ agent_id 在子代理内部**无法获取**
- ❌ subagent **不能 spawn subagent**
- ✅ **主会话**可以感知它启动的 subagent 的 id

因此，**复用策略的控制必须由主会话管理**，而非子代理或 state.json。

**候选方案**：

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **方案 A：全新子代理** | start 和 continue 都启动全新子代理 | 上下文不腐烂，隔离性好 | 效率低，每次需重新加载提示词 |
| **方案 B：常驻子代理** | 第一次 start 启动，后续复用 resume | 效率高，上下文延续 | 上下文可能腐烂，需监控 |
| **方案 C：混合方案** | 默认复用，达到阈值后启动新实例 | 平衡效率与可靠性 | 实现复杂 |

**倾向**：方案 C（混合方案），因为它兼容方案 A（已验证）。

---

##### 10.14.1 方案 A：全新子代理（已验证）

```
主会话 → Task(fn-controller, start xxx) → 全新子代理 → 返回 task
主会话 → 执行 task
主会话 → Task(fn-controller, continue) → 全新子代理 → 返回 task
主会话 → 执行 task
...
主会话 → Task(fn-controller, continue) → 全新子代理 → 返回 complete
```

**特点**：
- 每次 start/continue 都是独立的子代理调用
- 子代理无状态，所有状态通过 `scripts/states/<session>/state.json` 持久化
- 已验证可行

---

##### 10.14.2 方案 B：常驻子代理（未验证）

```
主会话 → Task(fn-controller, start xxx) → 启动子代理 A → 返回 task
         ↓ resume 子代理 A
主会话 → Task(resume=A, continue) → 子代理 A → 返回 task
         ↓ resume 子代理 A
主会话 → Task(resume=A, continue) → 子代理 A → 返回 complete
```

**特点**：
- 首次 start 启动子代理，后续通过 resume 复用
- 上下文累积，减少重复理解开销
- 风险：长时间运行后上下文可能"腐烂"（累积噪声、偏离主题）

---

##### 10.14.3 方案 C：混合方案（推荐）

```
主会话 → Task(fn-controller, start xxx) → 启动子代理 A → 返回 {task, resume_next: true}
         ↓ 主会话记住 agent_id=A
主会话 → Task(resume=A, continue) → 子代理 A → 返回 {task, resume_next: true}
         ↓ 主会话继续用 resume=A
主会话 → Task(resume=A, continue) → 子代理 A → 返回 {task, resume_next: false}  ← 达到阈值
         ↓ 主会话丢弃 agent_id
主会话 → Task(fn-controller, continue) → 全新子代理 B → 返回 {task, resume_next: true}
         ↓ 主会话记住 agent_id=B
...
```

**实现细节**：

1. **计数器由 fn-controller subagent 维护**，持久化到 `state.json`

```json
{
  "stack": [...],
  "controller": {
    "resume_count": 3,
    "max_resume_before_refresh": 5
  }
}
```

> **注意**：`agent_id` 不在 state.json 中（子代理无法获知自己的 id）

2. **脚本输出包含 `resume_next` 布尔值**

```json
{
  "action": "execute_task",
  "task": {...},
  "state": {
    "stack_depth": 2,
    "current_function": "tests/test_loop"
  },
  "resume_next": true
}
```

- `resume_next: true` → 主会话下次应 resume 当前子代理
- `resume_next: false` → 主会话下次应启动全新子代理

3. **fn-controller subagent 内部逻辑**：

```python
# fn-controller 每次执行时
def update_resume_count():
    state = load_state()
    controller = state.get('controller', {'resume_count': 0, 'max_resume_before_refresh': 5})
    
    controller['resume_count'] += 1
    
    # 判断下次是否应该复用
    resume_next = controller['resume_count'] < controller['max_resume_before_refresh']
    
    if not resume_next:
        # 达到阈值，重置计数器（下次新实例从 0 开始）
        controller['resume_count'] = 0
    
    state['controller'] = controller
    save_state(state)
    
    return resume_next
```

4. **主会话处理逻辑**（极简）：

```python
# 主会话只需记住上次的 agent_id（从 Task 返回值获取）
last_agent_id = None

def call_fn_controller(operation: str):
    global last_agent_id
    
    if last_agent_id:
        result = Task(resume=last_agent_id, prompt=operation)
    else:
        result = Task(subagent_type='fn-controller', prompt=operation)
    
    # 根据返回值决定是否保留 agent_id
    if result.resume_next:
        last_agent_id = result.agent_id  # 主会话可从 Task 返回值获取
    else:
        last_agent_id = None  # 下次启动新实例
    
    return result
```

**职责划分**：

| 职责 | 负责方 |
|------|--------|
| 管理 resume_count | fn-controller subagent（持久化到 state.json） |
| 决定下次复用还是新建 | fn-controller subagent（返回 resume_next） |
| 记住当前 agent_id | 主会话（从 Task 返回值获取） |
| 执行 resume 或新建 | 主会话 |

**阈值建议**：
- `max_resume_before_refresh`: 5-10 次
- 可根据实际运行情况调整

---

##### 10.14.4 兼容性说明

混合方案兼容方案 A：
- 当 `max_resume_before_refresh = 0` 时，`resume_next` 始终为 `false`，退化为全新子代理模式
- 验证过程中可先用全新模式，稳定后再开启复用

**当前状态**：
- 方案 A 已验证可行
- 方案 B/C 待验证 resume 机制的实际效果

**设计要点**：
- 计数管理：fn-controller subagent（state.json）
- 复用决策：fn-controller subagent（返回 `resume_next` 布尔值）
- agent_id 记忆：主会话（从 Task 返回值获取，subagent 无法获知自己的 id）

---

### 十一、总结

这个混合评估方案实现了**确定性与灵活性的平衡**：

- **确定性流程 100% 脚本化**：数值比较、字符串匹配、布尔逻辑、控制流路由
- **语义判断 AI 兜底**：eval 失败的表达式统一交给 AI（包括语法错误、类型错误）
- **交互式持久进程**：状态天然保持，通信可靠
- **职责边界清晰**：脚本负责"执行"，AI 负责"理解"
- **自然语言交互**：脚本输出问题，AI 回答答案，无复杂 JSON 协议

**相比原方案的改进**：
- 509 行提示词 → ~60 行（8x 压缩）
- 多次工具调用 → 单次启动 + 循环交互
- AI 负责所有控制流 → AI 仅负责语义评估
- JSON 协议 → 自然语言问答

**设计原则落地**：
- ✅ 奥卡姆剃刀：移除动态 target、@ai: 前缀、recover 命令
- ✅ 可靠性优先：triggers 隐式 sequence 由脚本处理，非 AI

**已解决的核心问题**：
- ✅ 状态一致性：交互式脚本方案，详见 [AI 语义理解交互模式](./ai-semantic-interactive-pattern.md)
- ✅ $prev 作用域：帧级变量，子函数不影响父函数
- ✅ null 统一：Python `None`，JSON `null`

**待验证/实现**：
- 📋 `fn_execute.py` 交互式脚本实现（见 10.13 节）
- 🔍 子代理复用策略验证（见 10.14 节）
- 📋 状态文件路径迁移（见 10.12 节）
- 📋 schema 同步（见 10.11 节）

新方案将 AI 的职责收窄到"语义评估"这一核心能力，大幅提升可靠性和效率。


========================


1. 这是一次重构任务，方案中没有覆盖的点，说明要继承现有功能和实现。
2. 不清楚的一定要询问我，不要自作主张
3. 分步骤执行，每一步都可验收，你先验收，然后交给我来验收
4. 设计可靠的单测程序  scripts/tests/ , 每步骤执行完都要进行回归测试，并清理过时的 cases
  - 注意，在 Cursor Agent 中执行 get_session_id 可能会失败，因为有可能 WT_SESSION 没有被配置 ，所以要么先配置环境变量 WT_SESSION（你自己随机生成一个）然后在执行测试脚本，要么告诉我 cases 的运行命令，我来在 cursor Agent 外面手动执行，然后告知你输出和结果
5. 不要总想着一个脚本能平铺所有逻辑，要模块化设计，复用现有已经实现的脚本