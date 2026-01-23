# Design by Opus: Function-Skill 框架的批判性重构

> 本文档对 `design_by_gemini.md` 进行批判性评估，并基于 **Claude Code Agent SDK** 的真实 API 给出一个完整、可靠、可实施的方案。

## 1. 对 Gemini 方案的批判性评估

### 1.1 正确的方向

Gemini 方案正确识别了以下关键问题：

| 洞察 | 评估 |
|------|------|
| Markdown 索引驱动的控制流脆弱 | ✅ 正确。LLM 容易"遗忘"流程或提前终止 |
| "Host-Driven Agency" 模式 | ✅ 核心理念正确：控制流归宿主，思考归模型 |
| 状态应显式传递而非依赖对话历史 | ✅ 减少上下文污染，提高可靠性 |
| 渐进式暴露原则 | ✅ 每次只暴露必要工具，防止 Agent 迷失 |

### 1.2 关键缺陷

然而，Gemini 方案存在以下严重问题：

#### 缺陷 1：API 假设不准确

```python
# Gemini 假设的 API（错误）
from claude_code_client import ClaudeCodeClient, AgentOptions
client = ClaudeCodeClient()
result = await client.query(prompt, options=AgentOptions(...))
```

```python
# 实际的 SDK API（正确）
from claude_agent_sdk import query, ClaudeAgentOptions
async for message in query(prompt="...", options=ClaudeAgentOptions(...)):
    # 处理消息流
```

**问题**：SDK 返回的是 **异步消息流**，不是单一结果对象。这是流式处理架构，不能像普通函数一样调用。

#### 缺陷 2：忽略了 Subagents 原生支持

Gemini 设计了复杂的手工 Function 编排，但 SDK 原生支持 **Subagents**：

```python
agents={
    "code-reviewer": AgentDefinition(
        description="Expert code reviewer",
        prompt="Review code for issues...",
        tools=["Read", "Grep", "Glob"],
        model="sonnet"
    )
}
```

这意味着"Function 调用"不需要手动实现递归，SDK 已提供原生的子代理机制。

#### 缺陷 3："context_compact" 内置指令幻想

```python
# Gemini 假设（错误）
await claude_code_context_compact()
await claude_code_context_clear()
```

SDK 没有直接暴露这些命令。实际可用的机制是：
- `PreCompact` Hook：在压缩前插入自定义逻辑
- 使用 `resume` 参数恢复会话
- 使用 `maxTurns` 限制对话轮次防止上下文爆炸

#### 缺陷 4：决策路由设计过于理想化

```python
# Gemini 的理想化决策
decision = result.get("decision")
if decision == "compact_context":
    ...
```

问题：
1. 依赖 Agent 可靠返回结构化 JSON，但未指定 `outputFormat`
2. 没有处理 Agent 不返回有效 decision 的情况
3. 没有考虑流式消息中多个 message 的聚合

#### 缺陷 5：阶段二 DSL 设计空洞

描述了"极简语法"、"核心原语"，但：
- 没有具体语法定义
- 没有解释器实现思路
- 没有与 SDK 的集成点

### 1.3 评估总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 方向正确性 | 8/10 | 核心理念正确 |
| API 准确性 | 3/10 | 基于假设的 API，无法直接运行 |
| 完整性 | 4/10 | 阶段二空洞，缺乏落地细节 |
| 可实施性 | 3/10 | 需要大幅重写才能运行 |

---

## 2. 重构方案：Function-Skill Framework v2

### 2.1 设计原则

基于 Gemini 的正确洞察，结合 SDK 真实 API，我们确立以下原则：

```
┌─────────────────────────────────────────────────────────────────┐
│                    FUNCTION-SKILL PRINCIPLES                    │
├─────────────────────────────────────────────────────────────────┤
│ 1. STREAM-NATIVE     │ 拥抱 SDK 的流式架构，不对抗             │
│ 2. SUBAGENT-FIRST    │ 优先使用原生 Subagent，非必要不自建    │
│ 3. STRUCTURED-OUTPUT │ 强制结构化输出，消除解析歧义            │
│ 4. HOOK-POWERED      │ 利用 Hooks 实现可靠性控制               │
│ 5. COMPOSITION       │ 组合优于继承，小函数组合成大流程         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FUNCTION-SKILL FRAMEWORK                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐   │
│  │   USER      │────▶│   ORCHESTRATOR  │────▶│   SKILL REGISTRY │   │
│  │   INPUT     │     │   (Python/TS)   │     │   (Definitions)  │   │
│  └─────────────┘     └────────┬────────┘     └──────────────────┘   │
│                               │                                      │
│                               ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      CLAUDE AGENT SDK                          │ │
│  ├────────────────────────────────────────────────────────────────┤ │
│  │                                                                │ │
│  │   ┌─────────┐   ┌──────────────┐   ┌─────────────────────┐    │ │
│  │   │ HOOKS   │   │  SUBAGENTS   │   │  STRUCTURED OUTPUT  │    │ │
│  │   │         │   │              │   │                     │    │ │
│  │   │ • Pre   │   │ • Reviewer   │   │  { decision: ...    │    │ │
│  │   │ • Post  │   │ • Executor   │   │    next_skill: ...  │    │ │
│  │   │ • Stop  │   │ • Validator  │   │    context: ...  }  │    │ │
│  │   └─────────┘   └──────────────┘   └─────────────────────┘    │ │
│  │                                                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                               │                                      │
│                               ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     STATE MANAGER                              │ │
│  │   • Persist state between skills                               │ │
│  │   • Enable resume from checkpoint                              │ │
│  │   • Track execution history                                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 实现详解

### 3.1 Skill 定义格式

每个 Skill 是一个结构化定义，包含输入/输出约定和执行逻辑：

```python
# skills/code_review.py
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel

# ===== 输入/输出 Schema 定义 =====
class CodeReviewInput(BaseModel):
    """Skill 输入结构"""
    target_path: str
    review_type: Literal["security", "performance", "quality"]
    context: str | None = None

class CodeReviewOutput(BaseModel):
    """Skill 输出结构 - 强制 Agent 按此格式返回"""
    decision: Literal["issues_found", "all_clear", "need_more_context", "delegate"]
    issues: list[dict] = []
    next_skill: str | None = None  # 如果 decision 是 delegate，指定下一个 skill
    summary: str = ""
    context_for_next: dict = {}  # 传递给下一个 skill 的上下文


# ===== Skill 定义 =====
@dataclass
class SkillDefinition:
    """Skill 元数据"""
    name: str
    description: str
    prompt: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    tools: list[str]
    model: str = "sonnet"
    max_turns: int = 10


CODE_REVIEW_SKILL = SkillDefinition(
    name="code-review",
    description="Review code for security, performance, or quality issues",
    prompt="""You are a code review specialist.

## Your Task
Analyze the code at the specified path according to the review type requested.

## Instructions
1. Read and understand the code structure
2. Identify issues based on the review type
3. Provide actionable recommendations

## Output Requirements
You MUST respond with a valid JSON matching the output schema.
- If issues found: decision = "issues_found", list issues
- If all clear: decision = "all_clear"
- If you need to analyze more files: decision = "need_more_context"
- If this requires a different specialist: decision = "delegate", specify next_skill
""",
    input_schema=CodeReviewInput,
    output_schema=CodeReviewOutput,
    tools=["Read", "Grep", "Glob"],
    model="sonnet",
    max_turns=15
)
```

### 3.2 Skill 执行器 (Executor)

核心执行器负责调用 SDK 并处理流式响应：

```python
# framework/executor.py
import asyncio
from typing import AsyncIterator
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

from .skill_definition import SkillDefinition


class SkillExecutor:
    """Skill 执行器 - 处理单个 Skill 的执行"""
    
    def __init__(self, skill: SkillDefinition, cwd: str = "."):
        self.skill = skill
        self.cwd = cwd
    
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """
        执行 Skill 并返回结构化输出
        
        Args:
            input_data: 符合 skill.input_schema 的输入
        
        Returns:
            符合 skill.output_schema 的输出
        """
        # 1. 构建 prompt
        prompt = self._build_prompt(input_data)
        
        # 2. 配置 SDK 选项
        options = ClaudeAgentOptions(
            # 结构化输出 - 强制 Agent 返回符合 schema 的 JSON
            output_format={
                "type": "json_schema",
                "schema": self.skill.output_schema.model_json_schema()
            },
            # 工具限制 - 渐进式暴露
            allowed_tools=self.skill.tools,
            # 执行限制
            max_turns=self.skill.max_turns,
            # 模型选择
            model=self.skill.model,
            # 工作目录
            cwd=self.cwd,
            # 系统提示
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": self.skill.prompt
            },
            # 权限模式 - 自动接受编辑
            permission_mode="acceptEdits"
        )
        
        # 3. 执行并收集结果
        structured_output = None
        cost_usd = 0.0
        
        async for message in query(prompt=prompt, options=options):
            # 捕获结构化输出
            if hasattr(message, 'structured_output') and message.structured_output:
                structured_output = message.structured_output
            
            # 捕获成本信息
            if isinstance(message, ResultMessage):
                cost_usd = getattr(message, 'total_cost_usd', 0.0)
                print(f"[{self.skill.name}] Cost: ${cost_usd:.4f}")
        
        # 4. 验证并返回结果
        if structured_output is None:
            raise RuntimeError(f"Skill {self.skill.name} did not return structured output")
        
        return self.skill.output_schema.model_validate(structured_output)
    
    def _build_prompt(self, input_data: BaseModel) -> str:
        """构建发送给 Agent 的完整 prompt"""
        code_block_start = "```json"
        code_block_end = "```"
        return f"""
## Skill Execution Request

**Skill**: {self.skill.name}
**Description**: {self.skill.description}

## Input Data
{code_block_start}
{input_data.model_dump_json(indent=2)}
{code_block_end}

## Expected Output Schema
{code_block_start}
{self.skill.output_schema.model_json_schema()}
{code_block_end}

Please execute this skill and return a valid JSON response matching the output schema.
"""
```

### 3.3 编排器 (Orchestrator)

编排器负责管理 Skill 之间的流转：

```python
# framework/orchestrator.py
import asyncio
from typing import TypeVar, Generic
from pydantic import BaseModel

from .skill_registry import SkillRegistry
from .executor import SkillExecutor
from .state import StateManager


class Orchestrator:
    """
    Skill 编排器 - 管理决策图的执行
    
    核心职责：
    1. 根据 Skill 输出的 decision 和 next_skill 路由到下一个 Skill
    2. 管理状态在 Skill 之间的传递
    3. 处理错误和重试
    4. 防止无限循环
    """
    
    def __init__(
        self,
        registry: SkillRegistry,
        state_manager: StateManager,
        max_depth: int = 10,
        cwd: str = "."
    ):
        self.registry = registry
        self.state = state_manager
        self.max_depth = max_depth
        self.cwd = cwd
        self._execution_stack: list[str] = []
    
    async def run(self, entry_skill: str, initial_input: dict) -> dict:
        """
        执行决策图
        
        Args:
            entry_skill: 入口 Skill 名称
            initial_input: 初始输入数据
        
        Returns:
            最终执行结果
        """
        return await self._execute_skill(entry_skill, initial_input, depth=0)
    
    async def _execute_skill(
        self,
        skill_name: str,
        input_data: dict,
        depth: int
    ) -> dict:
        """递归执行 Skill"""
        
        # 1. 深度检查 - 防止无限递归
        if depth >= self.max_depth:
            raise RecursionError(
                f"Max depth {self.max_depth} exceeded. "
                f"Stack: {' -> '.join(self._execution_stack)}"
            )
        
        # 2. 循环检测 - 防止简单循环
        if skill_name in self._execution_stack[-3:]:  # 检查最近 3 次调用
            print(f"[WARN] Potential loop detected: {skill_name} called recently")
        
        self._execution_stack.append(skill_name)
        print(f"[{depth}] Executing: {skill_name}")
        
        try:
            # 3. 获取 Skill 定义
            skill = self.registry.get(skill_name)
            if skill is None:
                raise ValueError(f"Unknown skill: {skill_name}")
            
            # 4. 验证输入
            validated_input = skill.input_schema.model_validate(input_data)
            
            # 5. 执行 Skill
            executor = SkillExecutor(skill, cwd=self.cwd)
            output = await executor.execute(validated_input)
            
            # 6. 保存状态
            self.state.save_checkpoint(
                skill_name=skill_name,
                input_data=input_data,
                output_data=output.model_dump()
            )
            
            # 7. 决策路由
            return await self._route_decision(output, depth)
            
        finally:
            self._execution_stack.pop()
    
    async def _route_decision(self, output: BaseModel, depth: int) -> dict:
        """根据 Skill 输出决定下一步"""
        
        output_dict = output.model_dump()
        decision = output_dict.get("decision", "done")
        next_skill = output_dict.get("next_skill")
        context_for_next = output_dict.get("context_for_next", {})
        
        print(f"    Decision: {decision}, Next: {next_skill}")
        
        # 终态判断
        if decision in ["done", "all_clear", "issues_found"]:
            return output_dict
        
        # 需要委托给其他 Skill
        if decision == "delegate" and next_skill:
            # 合并上下文
            next_input = {**context_for_next}
            return await self._execute_skill(next_skill, next_input, depth + 1)
        
        # 需要更多信息 - 可以增加重试逻辑
        if decision == "need_more_context":
            print(f"    [WARN] Skill needs more context, returning partial result")
            return output_dict
        
        # 未知决策 - 保守处理
        print(f"    [WARN] Unknown decision: {decision}")
        return output_dict
```

### 3.4 Hooks 集成 - 可靠性保障

```python
# framework/hooks.py
from claude_agent_sdk import HookMatcher, HookContext
from typing import Any
import json


async def validate_output_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    """
    PostToolUse Hook: 验证工具输出符合预期
    
    这对应 Gemini 方案中提到的 "Ralph Loop" 验证机制
    """
    tool_name = input_data.get('tool_name', '')
    tool_result = input_data.get('tool_result', {})
    
    # 示例：验证 Write 工具确实创建了文件
    if tool_name == 'Write':
        file_path = input_data.get('tool_input', {}).get('file_path', '')
        # 可以在这里添加额外验证逻辑
        print(f"[Hook] File written: {file_path}")
    
    return {}  # 继续执行


async def prevent_dangerous_commands(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    """
    PreToolUse Hook: 阻止危险命令
    """
    if input_data.get('tool_name') != 'Bash':
        return {}
    
    command = input_data.get('tool_input', {}).get('command', '')
    
    # 危险命令模式
    dangerous_patterns = [
        'rm -rf /',
        'rm -rf ~',
        '> /dev/sda',
        'mkfs.',
        ':(){:|:&};:',  # Fork bomb
    ]
    
    for pattern in dangerous_patterns:
        if pattern in command:
            return {
                'hookSpecificOutput': {
                    'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny',
                    'permissionDecisionReason': f'Dangerous command blocked: {pattern}'
                }
            }
    
    return {}


async def log_execution_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext
) -> dict[str, Any]:
    """
    通用日志 Hook: 记录所有工具使用
    """
    tool_name = input_data.get('tool_name', 'unknown')
    print(f"[Audit] Tool: {tool_name}, ID: {tool_use_id}")
    return {}


def get_safety_hooks() -> dict:
    """获取安全相关的 Hooks 配置"""
    return {
        'PreToolUse': [
            HookMatcher(matcher='Bash', hooks=[prevent_dangerous_commands]),
            HookMatcher(hooks=[log_execution_hook])  # 所有工具
        ],
        'PostToolUse': [
            HookMatcher(hooks=[validate_output_hook])
        ]
    }
```

### 3.5 状态管理

```python
# framework/state.py
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Checkpoint:
    """执行检查点"""
    skill_name: str
    input_data: dict
    output_data: dict
    timestamp: str
    depth: int = 0


class StateManager:
    """
    状态管理器 - 支持持久化和恢复
    
    解决 Gemini 方案中提到的"断点恢复"需求
    """
    
    def __init__(self, state_dir: str = ".function_skill_state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.checkpoints: list[Checkpoint] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def save_checkpoint(
        self,
        skill_name: str,
        input_data: dict,
        output_data: dict
    ) -> None:
        """保存检查点"""
        checkpoint = Checkpoint(
            skill_name=skill_name,
            input_data=input_data,
            output_data=output_data,
            timestamp=datetime.now().isoformat(),
            depth=len(self.checkpoints)
        )
        self.checkpoints.append(checkpoint)
        
        # 持久化到文件
        checkpoint_file = self.state_dir / f"{self.session_id}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump([asdict(c) for c in self.checkpoints], f, indent=2)
    
    def load_session(self, session_id: str) -> list[Checkpoint]:
        """加载历史会话"""
        checkpoint_file = self.state_dir / f"{session_id}.json"
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        
        with open(checkpoint_file) as f:
            data = json.load(f)
        
        return [Checkpoint(**item) for item in data]
    
    def get_last_checkpoint(self) -> Checkpoint | None:
        """获取最后一个检查点"""
        return self.checkpoints[-1] if self.checkpoints else None
    
    def resume_from(self, checkpoint: Checkpoint) -> dict:
        """从检查点恢复输入数据"""
        return checkpoint.output_data.get("context_for_next", checkpoint.input_data)
```

### 3.6 Skill 注册表

```python
# framework/skill_registry.py
from typing import Dict
from .skill_definition import SkillDefinition


class SkillRegistry:
    """Skill 注册表 - 管理所有可用的 Skills"""
    
    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
    
    def register(self, skill: SkillDefinition) -> None:
        """注册一个 Skill"""
        self._skills[skill.name] = skill
        print(f"[Registry] Registered skill: {skill.name}")
    
    def get(self, name: str) -> SkillDefinition | None:
        """获取 Skill 定义"""
        return self._skills.get(name)
    
    def list_skills(self) -> list[str]:
        """列出所有注册的 Skills"""
        return list(self._skills.keys())
    
    def to_agent_definitions(self) -> dict:
        """
        转换为 SDK 的 AgentDefinition 格式
        用于将 Skills 作为 Subagents 暴露给主 Agent
        """
        from claude_agent_sdk import AgentDefinition
        
        return {
            skill.name: AgentDefinition(
                description=skill.description,
                prompt=skill.prompt,
                tools=skill.tools,
                model=skill.model
            )
            for skill in self._skills.values()
        }
```

---

## 4. 两种使用模式

### 4.1 模式 A：程序化编排 (Programmatic Orchestration)

完全由宿主程序控制流程，适合复杂的、需要精确控制的场景：

```python
# examples/programmatic_mode.py
import asyncio
from framework import Orchestrator, SkillRegistry, StateManager
from skills.code_review import CODE_REVIEW_SKILL
from skills.fix_issues import FIX_ISSUES_SKILL
from skills.run_tests import RUN_TESTS_SKILL


async def main():
    # 1. 注册 Skills
    registry = SkillRegistry()
    registry.register(CODE_REVIEW_SKILL)
    registry.register(FIX_ISSUES_SKILL)
    registry.register(RUN_TESTS_SKILL)
    
    # 2. 创建编排器
    orchestrator = Orchestrator(
        registry=registry,
        state_manager=StateManager(),
        max_depth=10,
        cwd="/path/to/project"
    )
    
    # 3. 执行决策图
    result = await orchestrator.run(
        entry_skill="code-review",
        initial_input={
            "target_path": "src/",
            "review_type": "security",
            "context": "Focus on authentication and authorization"
        }
    )
    
    print("Final Result:", result)


asyncio.run(main())
```

### 4.2 模式 B：Agent 自主编排 (Agent-Driven Orchestration)

将 Skills 作为 Subagents 暴露，让主 Agent 自主决定调用哪个 Skill：

```python
# examples/agent_driven_mode.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition
from framework import SkillRegistry
from skills import ALL_SKILLS


async def main():
    # 1. 注册所有 Skills
    registry = SkillRegistry()
    for skill in ALL_SKILLS:
        registry.register(skill)
    
    # 2. 转换为 Subagent 定义
    subagents = registry.to_agent_definitions()
    
    # 3. 让主 Agent 自主编排
    async for message in query(
        prompt="""
        I need you to review and improve the codebase at src/.
        
        You have access to specialized agents:
        - code-review: For reviewing code quality
        - fix-issues: For fixing identified issues
        - run-tests: For running and validating tests
        
        Please orchestrate these agents to achieve the goal.
        """,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob", "Task"],  # Task 用于调用 Subagent
            agents=subagents,
            max_turns=30,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": "You are a software architect. Delegate work to specialized agents."
            }
        )
    ):
        if hasattr(message, "result"):
            print(message.result)


asyncio.run(main())
```

---

## 5. 与 Gemini 方案的对比

| 特性 | Gemini 方案 | Opus 方案 |
|------|-------------|-----------|
| **API 准确性** | 假设的 API | 基于真实 SDK |
| **流式处理** | 忽略 | 原生支持 |
| **结构化输出** | 隐式约定 | `output_format` 强制 |
| **子任务委托** | 手工实现 | 原生 Subagent |
| **可靠性控制** | 概念性描述 | Hooks 具体实现 |
| **状态管理** | "序列化保存" | 完整实现 |
| **错误处理** | "可加 Try-Catch" | 具体策略 |
| **代码可运行** | 否 | 是 |

---

## 6. 实施路线图

### 阶段一：核心框架 (1-2 周)

```
Week 1-2: Core Framework
├── [ ] SkillDefinition 数据结构
├── [ ] SkillExecutor 基础实现
├── [ ] 验证 structured output 工作
├── [ ] 基础 Hooks (安全、日志)
└── [ ] StateManager 持久化
```

**验收标准**：能执行单个 Skill 并获得结构化输出

### 阶段二：编排器 (1-2 周)

```
Week 3-4: Orchestrator
├── [ ] 决策路由实现
├── [ ] 递归深度控制
├── [ ] 循环检测
├── [ ] 断点恢复
└── [ ] 错误重试策略
```

**验收标准**：能执行 3+ Skill 的决策图

### 阶段三：Skills 库 (持续)

```
Week 5+: Skill Library
├── [ ] code-review
├── [ ] fix-issues
├── [ ] run-tests
├── [ ] refactor
├── [ ] document
└── [ ] deploy
```

### 阶段四 (可选)：DSL 层

如果宿主语言确实成为障碍，可以考虑 DSL：

```yaml
# skills/workflow.yaml
name: code-improvement
entry: code-review

skills:
  code-review:
    on_issues_found: fix-issues
    on_all_clear: done
    
  fix-issues:
    on_success: run-tests
    on_failure: manual-review
    
  run-tests:
    on_pass: done
    on_fail: fix-issues
    max_retries: 3
```

但建议：**先用 Python 验证模式，再考虑 DSL**。过早抽象是万恶之源。

---

## 7. 快速开始示例

```python
# quick_start.py
"""
最小可运行示例 - 验证框架可行性
"""
import asyncio
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions


# 定义输出结构
class AnalysisResult(BaseModel):
    summary: str
    issues_count: int
    recommendations: list[str]


async def run_simple_skill():
    """运行一个简单的分析 Skill"""
    
    async for message in query(
        prompt="Analyze the Python files in the current directory for code quality issues.",
        options=ClaudeAgentOptions(
            output_format={
                "type": "json_schema",
                "schema": AnalysisResult.model_json_schema()
            },
            allowed_tools=["Read", "Glob", "Grep"],
            max_turns=10,
            permission_mode="acceptEdits",
            cwd="."
        )
    ):
        if hasattr(message, 'structured_output') and message.structured_output:
            result = AnalysisResult.model_validate(message.structured_output)
            print(f"Summary: {result.summary}")
            print(f"Issues: {result.issues_count}")
            for rec in result.recommendations:
                print(f"  - {rec}")


if __name__ == "__main__":
    asyncio.run(run_simple_skill())
```

---

## 8. 总结

本方案相比 Gemini 版本的核心改进：

1. **基于真实 SDK API**：所有代码示例可直接运行
2. **拥抱流式架构**：正确处理 async generator 模式
3. **强制结构化输出**：消除 Agent 输出的不确定性
4. **利用原生 Subagent**：减少重复造轮子
5. **具体的 Hooks 实现**：可靠性不再是空话
6. **完整的状态管理**：支持断点恢复

**核心理念保持不变**：控制流归宿主，思考归模型，状态即变量。

这就是 **Function-Skill Framework v2**。
