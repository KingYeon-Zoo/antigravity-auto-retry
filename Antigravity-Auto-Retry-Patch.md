# Antigravity "Agent terminated due to error" 自动重试 Patch

## 问题描述

Antigravity（Google 的 VS Code fork，内部代号 Cloud Code）在使用 Claude Opus 4.6 Thinking / Claude Sonnet 4.6 模型时，Google 后端频繁返回 **503 No capacity available**，导致 Agent 执行中断并弹出 "Agent terminated due to error" 弹窗，需要用户手动点击 Retry 才能继续。

### 错误日志

```
UNAVAILABLE (code 503): No capacity available for model claude-opus-4-6-thinking on the server
agent executor error: model unreachable
```

### 错误链路

```
用户发送消息
  → Go后端 planner_generator.go 调用 Google API
  → googleapis.com 返回 503
  → Go后端自动重试3次（间隔5s→7s→9s递增）
  → 3次都503 → 抛出 "agent executor error: model unreachable"
  → 前端收到错误 → t6i() 分类为 "retryable" 或 "generic"
  → r6i() 构造通知对象 → 弹窗 "Agent terminated due to error"
  → 用户手动点 Retry → 发送 "Try again"/"Continue" 消息 → 重新开始
```

---

## 解决方案

在前端 JS 层拦截错误处理函数，遇到 `retryable`/`generic` 类型错误时**自动发送重试消息**，不弹窗。使用 `globalThis._agRetried` Set 防重复，同一个 error 只自动重试一次，之后走原来的弹窗逻辑。

### 需要修改的文件

| 文件 | 作用 | 路径 |
|------|------|------|
| `workbench.desktop.main.js` | **主进程 workbench**，实际渲染弹窗的文件 | `/Applications/Antigravity.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js` |
| `jetskiAgent/main.js` | Agent webview 面板 | `/Applications/Antigravity.app/Contents/Resources/app/out/jetskiAgent/main.js` |

> **重要**：两个文件都要改。弹窗实际由 `workbench.desktop.main.js` 渲染，只改 `jetskiAgent/main.js` 无效。

---

## 详细改动

### 核心逻辑

错误处理函数 `r6i`（workbench中变量名不同但逻辑相同）的 switch 中有两个 case 需要修改：

```
case "retryable" → 503/内部错误/超时/不可用等（errorCode 在 e6i 列表中）
case "generic"   → 其他未分类错误（errorCode 不在列表中或为空）
```

**修改策略**：在每个 case 中，用 `globalThis._agRetried` Set 记录已自动重试的 notificationId，第一次自动重试，第二次弹窗。

---

### 文件1：workbench.desktop.main.js

**关键变量映射**：

| 变量 | 含义 |
|------|------|
| `p` | `sendMessage` — 发送聊天消息 |
| `Hi` | 消息构造器（等价于 jetskiAgent 中的 `ur`） |
| `D6` | 消息类型常量（等价于 jetskiAgent 中的 `KS`） |
| `i` | `notificationId`（格式：`cortex_error-{trajectoryId}-{stepIndex}`） |
| `v` | 按钮构造器 `(label, message) => ({label, onClick: () => p([Hi(D6, {chunk:{case:"text",value:message}})])})` |
| `zFo` | 字符串常量 `"Agent terminated due to error"` |

#### retryable case

**原始代码**：
```js
case"retryable":return{id:i,icon:n,title:zFo,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:v("Try again","Try again"),secondaryAction:b()}
```

**修改后**：
```js
case"retryable":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(i)){globalThis._agRetried.add(i);return setTimeout(()=>{p([Hi(D6,{chunk:{case:"text",value:"Try again"}})])},500),void 0}return{id:i,icon:n,title:zFo,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:v("Try again","Try again"),secondaryAction:b()}}
```

#### generic case

**原始代码**：
```js
case"generic":return{id:i,icon:n,title:zFo,message:L(ps,{children:["You can prompt the model to try again or start a new conversation if the error persists.",o&&L("span",{children:[" ","See our"," ",L("a",{href:o,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:v("Retry","Continue"),secondaryAction:b()}
```

**修改后**：
```js
case"generic":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(i)){globalThis._agRetried.add(i);return setTimeout(()=>{p([Hi(D6,{chunk:{case:"text",value:"Continue"}})])},500),void 0}return{id:i,icon:n,title:zFo,message:L(ps,{children:["You can prompt the model to try again or start a new conversation if the error persists.",o&&L("span",{children:[" ","See our"," ",L("a",{href:o,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:v("Retry","Continue"),secondaryAction:b()}}
```

---

### 文件2：jetskiAgent/main.js

**关键变量映射**：

| 变量 | 含义 |
|------|------|
| `v` | `sendMessage` |
| `ur` | 消息构造器 |
| `KS` | 消息类型常量 |
| `r` | `notificationId` |
| `S` | 按钮构造器 |
| `s0n` | `"Agent terminated due to error"` |

#### retryable case

**原始代码**：
```js
case"retryable":return{id:r,icon:n,title:s0n,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:S("Try again","Try again"),secondaryAction:F()}
```

**修改后**：
```js
case"retryable":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(r)){globalThis._agRetried.add(r);return setTimeout(()=>{v([ur(KS,{chunk:{case:"text",value:"Try again"}})])},500),void 0}return{id:r,icon:n,title:s0n,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:S("Try again","Try again"),secondaryAction:F()}}
```

#### generic case

**原始代码**：
```js
case"generic":return{id:r,icon:n,title:s0n,message:A(or,{children:["You can prompt the model to try again or start a new conversation if the error persists.",s&&A("span",{children:[" ","See our"," ",A("a",{href:s,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:S("Retry","Continue"),secondaryAction:F()}
```

**修改后**：
```js
case"generic":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(r)){globalThis._agRetried.add(r);return setTimeout(()=>{v([ur(KS,{chunk:{case:"text",value:"Continue"}})])},500),void 0}return{id:r,icon:n,title:s0n,message:A(or,{children:["You can prompt the model to try again or start a new conversation if the error persists.",s&&A("span",{children:[" ","See our"," ",A("a",{href:s,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:S("Retry","Continue"),secondaryAction:F()}}
```

---

## 自动化 Patch 脚本

将以下脚本保存为 `patch_antigravity.py`，每次 Antigravity 更新后重新执行：

```python
#!/usr/bin/env python3
"""
Antigravity Auto-Retry Patch
遇到 503/模型不可用错误时自动重试一次，不弹窗。
同一个error只自动重试一次，之后走原来的弹窗逻辑。
"""

import os
import shutil

def patch_file(filepath, patches):
    """对文件执行多个替换patch"""
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return False
    
    # 备份
    bak = filepath + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(filepath, bak)
        print(f"📦 备份: {bak}")
    
    with open(bak, 'rb') as f:
        content = f.read().decode('utf-8', errors='replace')
    
    for old, new in patches:
        count = content.count(old)
        if count == 0:
            print(f"⚠️  未找到匹配（可能已patch或版本更新）")
            return False
        if count > 1:
            print(f"⚠️  找到{count}处匹配，预期1处")
            return False
        content = content.replace(old, new)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Patch成功: {filepath}")
    return True


def make_auto_retry_patch(notif_id_var, send_msg_expr_try, send_msg_expr_continue, original_retryable, original_generic):
    """构造自动重试patch代码"""
    nid = notif_id_var
    
    new_retryable = (
        f'case"retryable":{{if(!globalThis._agRetried)globalThis._agRetried=new Set;'
        f'if(!globalThis._agRetried.has({nid})){{globalThis._agRetried.add({nid});'
        f'return setTimeout(()=>{{{send_msg_expr_try}}},500),void 0}}'
        f'{original_retryable[len("case\\"retryable\\":return"):]}}}'  # 这里不能直接拼，见下方
    )
    
    # 实际使用精确的字符串替换，不用这个函数
    pass


# ============ workbench.desktop.main.js ============
wb_path = '/Applications/Antigravity.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js'

wb_patches = [
    # retryable case
    (
        'case"retryable":return{id:i,icon:n,title:zFo,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:v("Try again","Try again"),secondaryAction:b()}',
        'case"retryable":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(i)){globalThis._agRetried.add(i);return setTimeout(()=>{p([Hi(D6,{chunk:{case:"text",value:"Try again"}})])},500),void 0}return{id:i,icon:n,title:zFo,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:v("Try again","Try again"),secondaryAction:b()}}'
    ),
    # generic case
    (
        'case"generic":return{id:i,icon:n,title:zFo,message:L(ps,{children:["You can prompt the model to try again or start a new conversation if the error persists.",o&&L("span",{children:[" ","See our"," ",L("a",{href:o,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:v("Retry","Continue"),secondaryAction:b()}',
        'case"generic":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(i)){globalThis._agRetried.add(i);return setTimeout(()=>{p([Hi(D6,{chunk:{case:"text",value:"Continue"}})])},500),void 0}return{id:i,icon:n,title:zFo,message:L(ps,{children:["You can prompt the model to try again or start a new conversation if the error persists.",o&&L("span",{children:[" ","See our"," ",L("a",{href:o,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:v("Retry","Continue"),secondaryAction:b()}}'
    ),
]

# ============ jetskiAgent/main.js ============
jk_path = '/Applications/Antigravity.app/Contents/Resources/app/out/jetskiAgent/main.js'

jk_patches = [
    # retryable case
    (
        'case"retryable":return{id:r,icon:n,title:s0n,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:S("Try again","Try again"),secondaryAction:F()}',
        'case"retryable":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(r)){globalThis._agRetried.add(r);return setTimeout(()=>{v([ur(KS,{chunk:{case:"text",value:"Try again"}})])},500),void 0}return{id:r,icon:n,title:s0n,message:"This error is likely temporary. You can prompt the model to try again after some time.",primaryAction:S("Try again","Try again"),secondaryAction:F()}}'
    ),
    # generic case
    (
        'case"generic":return{id:r,icon:n,title:s0n,message:A(or,{children:["You can prompt the model to try again or start a new conversation if the error persists.",s&&A("span",{children:[" ","See our"," ",A("a",{href:s,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:S("Retry","Continue"),secondaryAction:F()}',
        'case"generic":{if(!globalThis._agRetried)globalThis._agRetried=new Set;if(!globalThis._agRetried.has(r)){globalThis._agRetried.add(r);return setTimeout(()=>{v([ur(KS,{chunk:{case:"text",value:"Continue"}})])},500),void 0}return{id:r,icon:n,title:s0n,message:A(or,{children:["You can prompt the model to try again or start a new conversation if the error persists.",s&&A("span",{children:[" ","See our"," ",A("a",{href:s,target:"_blank",rel:"noopener noreferrer",className:"underline opacity-70 transition-opacity hover:opacity-100 cursor-pointer underline-offset-2",children:"troubleshooting guide"})," ","for more help."]})]}),primaryAction:S("Retry","Continue"),secondaryAction:F()}}'
    ),
]

if __name__ == '__main__':
    print("=" * 50)
    print("Antigravity Auto-Retry Patch")
    print("=" * 50)
    
    print("\n[1/2] Patching workbench.desktop.main.js...")
    patch_file(wb_path, wb_patches)
    
    print("\n[2/2] Patching jetskiAgent/main.js...")
    patch_file(jk_path, jk_patches)
    
    print("\n" + "=" * 50)
    print("完成！请重启 Antigravity 使 patch 生效。")
    print("=" * 50)
```

---

## 使用方法

### 首次 Patch

```bash
python3 ~/Desktop/patch_antigravity.py
# 然后重启 Antigravity
```

### Antigravity 更新后重新 Patch

每次 Antigravity 更新后，JS 文件会被覆盖，需要：

1. 删除旧备份文件：
   ```bash
   rm /Applications/Antigravity.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js.bak
   rm /Applications/Antigravity.app/Contents/Resources/app/out/jetskiAgent/main.js.bak
   ```
2. 重新运行 patch 脚本
3. 重启 Antigravity

> **注意**：如果 Antigravity 版本更新后变量名变化（如 `zFo` → `xxx`），patch 会匹配失败。此时需要重新分析变量映射并更新脚本中的 old/new 字符串。

### 恢复原始版本

```bash
# workbench
cp /Applications/Antigravity.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js.bak \
   /Applications/Antigravity.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js

# jetskiAgent
cp /Applications/Antigravity.app/Contents/Resources/app/out/jetskiAgent/main.js.bak \
   /Applications/Antigravity.app/Contents/Resources/app/out/jetskiAgent/main.js
```

---

## 运行效果

| 场景 | patch前 | patch后 |
|------|---------|---------|
| 首次503错误 | 弹窗等待手动点Retry | 自动发送"Try again"，无弹窗 |
| 同一step连续503 | 每次都弹窗 | 第1次自动重试，第2次弹窗 |
| 非503错误(429配额/403) | 弹窗（正确行为） | 不受影响，仍然弹窗 |

---

## 技术细节

### 错误分类逻辑（t6i 函数）

```
errorCode === 429 → 配额超限（longTermQuotaExceeded / insufficientCredits）
errorCode === 403 → 需要验证（verificationRequired / tosViolation）
errorCode in [ResourceExhausted, Internal, DeadlineExceeded, Unavailable] → retryable
其他 → generic
```

### 为什么 503 可能走 generic 而非 retryable

Go 后端的 agent executor 在3次重试都失败后，抛出 `agent executor error: model unreachable`。这个错误传到前端时，`errorCode` 可能不在 `e6i` 列表中（取决于 gRPC status code 的映射），导致被分类为 `generic` 而非 `retryable`。因此**两个 case 都需要 patch**。

### notificationId 格式

```
cortex_error-{trajectoryId}-{stepIndex}
```

每个 step 的 error 有唯一的 notificationId，所以 `globalThis._agRetried` Set 可以精确控制"同一个 error 只自动重试一次"。

### 为什么用 setTimeout 500ms

- `0ms`：过快，消息可能在错误处理完成前发出
- `500ms`：给前端状态足够的更新时间，确保 sendMessage 在正确的 context 中执行
- `void 0`：return undefined，让通知系统认为没有通知要显示，不弹窗

---

## 踩坑记录

| 问题 | 原因 | 解决 |
|------|------|------|
| 只改 jetskiAgent/main.js 无效 | 弹窗由 workbench.desktop.main.js 渲染 | 两个文件都要改 |
| 只改 retryable case 无效 | 503 被分类为 generic | retryable + generic 都要改 |
| 自动重试变成无限循环 | 每次503都触发自动重试 | 用 globalThis._agRetried Set 防重复 |
| 之前的UI层patch（3秒倒计时）无效 | dismiss后组件卸载，onClick失效 | 改在错误处理函数层拦截 |
