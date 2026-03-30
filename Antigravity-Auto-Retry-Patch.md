# Antigravity "Agent terminated due to error" 自动重试 Patch 技术说明

这份文档描述当前仓库里新版 `patch_antigravity.py` 的实现思路。它不再依赖某一版 Antigravity 打包产物的完整字符串，而是改成对错误分支做结构匹配，因此更适合应对后续常规更新。

## 问题背景

Antigravity 在部分模型和时段下会遇到以下链路：

```text
Google API / 模型服务返回 503
-> agent 执行中断
-> 前端进入 retryable / generic 错误分支
-> 弹出 "Agent terminated due to error"
-> 用户必须手动点 Retry / Continue
```

这个仓库的目标不是改变后端容量状态，而是在本地 UI 层自动执行一次原本就存在的主按钮动作。

## 当前 patch 的核心思路

脚本会修改两个 bundle：

- `resources/app/out/vs/workbench/workbench.desktop.main.js`
- `resources/app/out/jetskiAgent/main.js`

每个 bundle 都会查找两个 `switch case`：

- `case "retryable"`
- `case "generic"`

旧方案的问题是：

- 依赖完整压缩字符串
- 依赖具体变量名，例如 `p`、`Hi`、`D6`
- 只要 Antigravity 更新后重新压缩，匹配就可能直接失效

新方案改成：

1. 用正则匹配 `case "retryable"` / `case "generic"` 的返回对象结构。
2. 捕获原始通知对象整体表达式。
3. 在第一次命中时，不自己手写发送消息逻辑，而是直接调用这个对象已有的 `primaryAction.onClick()`。
4. 第二次命中同一通知 ID 时，继续返回原始通知对象，恢复默认弹窗行为。

这样做的关键收益是：

- 不再依赖压缩变量名
- 不再依赖 sendMessage / 构造器的具体符号名
- 只要通知对象结构没被彻底重写，通常都能继续 patch

## 注入后的行为

注入逻辑等价于：

```js
case "retryable": {
  let __agAutoRetryNotification = ORIGINAL_NOTIFICATION_OBJECT;
  if (!globalThis.__agAutoRetryIds) globalThis.__agAutoRetryIds = new Set();
  if (!globalThis.__agAutoRetryIds.has(__agAutoRetryNotification.id)) {
    globalThis.__agAutoRetryIds.add(__agAutoRetryNotification.id);
    return setTimeout(() => {
      __agAutoRetryNotification.primaryAction.onClick();
    }, 500), void 0;
  }
  return __agAutoRetryNotification;
}
```

`generic` 分支也是同一策略。

也就是说：

- 第一次出错时，不显示弹窗，500ms 后自动执行原按钮逻辑
- 同一个通知 ID 只自动重试一次
- 如果再次失败，就回到 Antigravity 原始提示流程

## 为什么直接调用 `primaryAction.onClick()` 更稳

原始通知对象本身已经包含了正确的行为：

- 正确的消息内容
- 正确的消息发送函数
- 正确的消息构造器
- 当前版本实际绑定的点击逻辑

因此直接复用它，比重新拼装：

- `Try again`
- `Continue`
- 某个消息工厂
- 某个发送函数

都更不容易被版本更新打断。

## 路径发现策略

Windows 下脚本会尝试：

1. `ANTIGRAVITY_WORKBENCH_PATH` + `ANTIGRAVITY_JETSKI_PATH`
2. `--root`
3. `ANTIGRAVITY_INSTALL_DIR`
4. 卸载注册表
5. 常见默认目录
6. glob 模式搜索目录

另外专门补了几个经验路径：

- `%LOCALAPPDATA%\Programs\Antigravity`
- `%LOCALAPPDATA%\Programs\antigravity-stable-user-x64`
- `%LOCALAPPDATA%\Programs\Cloud Code`
- `C:\Antigravity`
- `D:\Antigravity`

macOS 则继续支持 `/Applications/Antigravity.app`。

## 备份与恢复

对每个目标文件，脚本都会维护一个同目录下的 `.bak`：

- 首次 patch 时创建备份
- 如果检测到当前 app 已经更新，而且当前文件是“新版本未 patch”，会自动刷新 `.bak`
- `--restore` 可直接恢复

这解决了“app 更新后旧备份和新文件不一致”的问题。

## 自检模式

`--check` 不修改文件，只做判断：

- `patched`：已经是新版 patch 或旧版 patch
- `patchable`：当前版本可直接 patch
- `missing`：签名找不到，说明结构可能变了
- `ambiguous`：签名匹配到多处，说明需要重新收紧规则

这是排查 Antigravity 新版本兼容性的第一步。

## 局限性

这个实现比旧版强很多，但不是绝对不会失效。

仍然可能失效的情况：

- `retryable` / `generic` 不再用当前这种通知对象结构
- `primaryAction` / `secondaryAction` 字段形态被重写
- 相关逻辑不再存在于这两个 bundle

一旦发生这种情况，`--check` 通常会先给出：

```text
signature not found
```

这时需要重新分析新版本 bundle 的错误通知结构。

## 仓库内相关文件

- `patch_antigravity.py`：主脚本
- `patch_antigravity.cmd`：Windows 启动器
- `README.md`：面向 GitHub 用户的使用文档

## 建议的 GitHub 发布方式

如果你准备公开仓库，建议至少包含：

- `README.md`
- `LICENSE`
- `patch_antigravity.py`
- `patch_antigravity.cmd`
- 本技术说明

这样普通用户看 README 就能用，想看原理的人也有一份不依赖旧变量名的技术说明。
