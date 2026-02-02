# /fn_continue - 恢复执行

从中断处恢复 function 调用链。

## 用法
```
/fn_continue
```

## 执行流程

### 1. 调用 fn-controller

```
使用 fn-controller subagent：
  operation=recover
```

### 2. 根据返回决定操作

| fn-controller 返回 | 主会话操作 |
|-------------------|-----------|
| `action: "nothing_to_recover"` | 输出 "没有需要恢复的调用链" |
| `action: "execute_task"` | 执行 task，然后继续循环 |
| `action: "ask_user"` | 询问用户选择，再调用 fn-controller |
| `action: "complete"` | 输出结果，结束 |

### 3. 继续执行循环

收到 task → 执行 → 新建 fn-controller：
```
使用 fn-controller subagent：
  operation=continue, task_result=<执行结果>
```
循环直到 complete

## 错误状态处理

当 fn-controller 返回 `action: "ask_user"` 时，询问用户：
1. retry - 重新执行栈顶函数
2. skip - pop 当前函数继续
3. clear - 清空栈结束

```
使用 fn-controller subagent：
  operation=error_recovery, action=<用户选择>
```

$ARGUMENTS
