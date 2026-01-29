# /fn_continue - 恢复执行

从中断处恢复 function 调用链。

## 用法
```
/fn_continue [--session=<id>]
```

## Session ID 获取

1. 如有 `--session=<id>` 参数，直接使用
2. 否则执行：`echo "WT_SESSION=$WT_SESSION"`
   - **⚠️ 必须直接用 echo，禁止用 powershell -Command 转发**
   - 解析输出 `=` 后的值作为 session_id
3. 若为空，使用 `default`

## 执行流程

1. 读取 `scripts/states/<WT_SESSION>.json`
2. 如果 `status == "running"` 且 `stack` 不为空：
   - 从栈顶函数继续执行
3. 否则输出 "没有需要恢复的调用链"

$ARGUMENTS
