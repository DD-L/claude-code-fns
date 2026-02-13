# /fn_continue - 恢复执行

从中断处恢复 function 调用链。

## 用法
```
/fn_continue
```

## 执行流程

### 1. 调用 fn-controller

```
Task(subagent_type='fn-controller', prompt='continue')
```

脚本自动从 `state.json` 恢复栈状态。

### 2. 根据输出决定操作

| 输出 | 主会话操作 |
|-----|-----------|
| `[TASK]` | 执行 task，然后继续循环 |
| `[COMPLETE]` | 输出结果，结束 |
| `[ERROR]` | 输出错误信息 |
| 栈为空 | 输出 "没有需要恢复的调用链" |

### 3. 继续执行循环

```
执行 task → fn-controller continue task_result=... → 循环直到 [COMPLETE]
```

## 手动错误恢复

如需手动干预栈状态：
```bash
# 查看栈状态
python scripts/stack_ops.py <session> get

# 弹出栈顶
python scripts/stack_ops.py <session> pop

# 清空栈
python scripts/stack_ops.py <session> clear
```

$ARGUMENTS
