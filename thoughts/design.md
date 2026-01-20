我想在 claude code 中实现利用其 skill 实现任务的递归性，以便实现更复杂的决策图。

任务被拆解后，每一步暴露的内容都刚好合适。

比如：

可以是一个 skill 里有多个复杂步骤（决策图）， 也可以是 skill 递归的调用另外一个 skill 驱动整个任务进行。

我倾向 一个 skill 里有多个复杂步骤（决策图）。


一个方案别实践后效果不如意。

skills 中的 一个  SKILL.md 中有，一堆 md 的索引的形式


SKILL.md：
```
---
skills header
---

1.md ：<子流程描述>
2.md : <子流程描述>
3.md : <子流程描述>
...
```

1.md
```
- <定义当前步骤>
- <定义下一步骤>
```


2.md
```
- <定义当前步骤>
- <定义下一步骤>
```

...

以上方案被实践后，不容易，注意是当 子步骤或子技能 数量和复杂度达到一定程度后，它将不能按预期正确工作，而且总是提前终止。
-------------


我还有两个思路：


## 思路一：

Skill 是可以调用脚本的，将 md 的提示词用脚本包装下

SKILL.md：
```
---
skills header
---

1.sh ：<什么条件下调用此脚本, 支持传参>
2.sh : <什么条件下调用此脚本，支持传参>
3.sh : <什么条件下调用此脚本，支持传参>
...
```

每个脚本中，都至少这些内容， 比如

1.sh

```
# 上一步的状态
# 当前子任务的定义
# 什么条件下调用下一个脚本
#
```

这个方案中 脚本支持传参和输出，传参可以是上一步的状态信息或总结信息，输出的内容可以被 Agent(claudecode) 读取作为当前步骤或者并包含驱动下一步骤的提示词。

这个提示词中定义了
- 当前任务定义，驱动 Agent(claudecode) 执行当前子任务
- 什么条件下调用下一个脚本， 以触发任务执行的递归性（决策图）

## 思路二：

将思路一的脚本内容，换成 （启动新的 Claude 进程） 

```
$ cat "提示词" | claude
```

提示词中包含

- 上一步的状态
- 当前子任务的定义
- 什么条件下调用下一个 claude 进程

-----

我倾向 思路一， 如果 思路一 不能很好的工作，那么就尝试 思路二。

请帮我
- 评估这些思路的可行性
- 你有没有更好的实践方式


=======


现在我有一个新的想法，要实现递归性，在 claude code 中抽象出 function 才是最好的途径: `function-skill`。

参考编程语言的 function， 即允许输入和输出，以及 function 中可以调用其它 function。

简化数据类型设计，数据类型都抽象为提示词文本

提示词中可以是
- 任务状态
- 下一步计划
等等

function 定义为：当前子任务流程


function 也有名字，也有匿名 Function，以便被其它 function 调用。

【暂缓】未来还还要支持 lambda 演算，高阶函数、柯里化和反柯里化等高级特性。


可靠性是它的特点，不会出现意外中止的情况，只要函数调用不中止，它就可以按照预想的继续工作，除非资源被耗尽（比如类似函数调用爆栈）

为了强调可靠性，可利用 claude code 一切可用的技术，(需查询 Claude Code 文档，甚至其 SDK 文档)
比如 
1. stop-hook 技术（类似于 ralph-loop的实现）, 检查函数运行状态，如果流程没有结束，则需要强制 claude code 继续,
2. skills 中的脚本调用
  1. 驱动下个步骤
  2. 驱动 function 调用
  3. 甚至可以用 claude code 的无头模式驱动下一个任务 `cat "下个任务" | claude -p`
3. 遵循渐进式暴露原则


能力展示：

### 可以调用 claude code 的内置指令：

function claude_code_context_compact() {
   "task"： "执行 claude code 的上下文压缩",
   "return": ""
}


function claude_code_context_clear() {
   "task": "执行 claude code 的上下文清理"，
   "return": ""
}

### 可以调用其它函数

function task_c(input) {
   CALL claude_code_context_clear()
   PROCESS input
}

function task_a(input) {
   switch "$input":
          WHEN condition1 CALL claude_code_context_compact()
          WHEN condition2 CALL claude_code_context_clear()
          WHEN condition3 CALL task_b($input + "balabala" + "balabala")
          DEFAULT call task_c()
   "return": "balabala"
}




