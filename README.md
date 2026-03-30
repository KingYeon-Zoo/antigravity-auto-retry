# Antigravity Auto-Retry Patch

中文 | [English](#english)

Antigravity 在部分模型和时段下会遇到 `503 No capacity available`，随后弹出 `Agent terminated due to error`，必须手动点 `Retry` 才能继续。本项目通过修改 Antigravity 本地打包产物，让 `retryable` 和 `generic` 两类 agent 错误先自动重试一次，再决定是否显示原始弹窗。

这次版本做了两件关键修复：

- 不再依赖旧版 bundle 的完整字符串硬编码，改成按错误分支结构自动定位并 patch
- 增加 Windows 启动器 `patch_antigravity.cmd`，避免 `python` / `py` 不在 PATH 时“直接运行 py 文件没反应”

## 这个仓库现在提供什么

- `patch_antigravity.py`
- `patch_antigravity.cmd`
- Windows 安装目录自动探测
- 自动备份、恢复、更新后备份刷新
- `--check` 自检模式

## 为什么旧版脚本在更新后容易失效

旧方案是直接替换一整段压缩后的 JS 字符串。Antigravity 更新后，即使功能逻辑没变，只要：

- 变量名变了
- 打包器重新压缩了
- JSX/通知对象字段顺序变了

原来的精确字符串匹配就会失效，最终报 `signature not found`。

现在的脚本改成了结构化 patch：

- 先匹配 `case "retryable"` / `case "generic"` 这两个错误分支
- 捕获原始通知对象
- 直接调用该通知对象已有的 `primaryAction.onClick()`
- 因此不再依赖 sendMessage、按钮工厂、消息构造器这些压缩变量名

这比整段硬编码稳得多，适合应对常规更新。

## 工作原理

脚本会同时修改：

- `resources/app/out/vs/workbench/workbench.desktop.main.js`
- `resources/app/out/jetskiAgent/main.js`

插入逻辑后：

- 第一次命中 `retryable` 或 `generic` 时，延迟 500ms 自动执行原始主按钮逻辑
- 同一个通知 ID 只自动重试一次
- 第二次命中同一错误时，恢复原始通知弹窗

内部通过 `globalThis.__agAutoRetryIds = new Set()` 记录已自动重试过的通知 ID。

## 快速开始

### Windows

1. 关闭 Antigravity。
2. 推荐直接运行：

```bat
patch_antigravity.cmd
```

也可以从终端执行：

```powershell
.\patch_antigravity.cmd
```

如果你明确知道本机 Python 路径，也可以直接运行：

```powershell
& "C:\Program Files\Python313\python.exe" .\patch_antigravity.py
```

3. 重启 Antigravity。

### macOS

1. 关闭 Antigravity。
2. 运行：

```bash
python3 ./patch_antigravity.py
```

3. 重启 Antigravity。

## 常用命令

### 只看识别到的安装路径

```powershell
.\patch_antigravity.cmd --print-paths
```

或：

```powershell
python .\patch_antigravity.py --print-paths
```

### 检查当前版本是否可 patch / 已 patch

```powershell
.\patch_antigravity.cmd --check
```

或：

```powershell
python .\patch_antigravity.py --check
```

### 恢复原始文件

```powershell
.\patch_antigravity.cmd --restore
```

或：

```powershell
python .\patch_antigravity.py --restore
```

## 路径解析规则

脚本会按顺序尝试：

1. `ANTIGRAVITY_WORKBENCH_PATH` + `ANTIGRAVITY_JETSKI_PATH`
2. `--root`
3. `ANTIGRAVITY_INSTALL_DIR`
4. Windows 卸载注册表安装信息
5. 常见默认目录和 glob 目录
6. macOS 默认 `.app` 路径

Windows 下除了注册表，也会额外尝试这些常见路径：

- `%LOCALAPPDATA%\Programs\Antigravity`
- `%LOCALAPPDATA%\Programs\antigravity-stable-user-x64`
- `%LOCALAPPDATA%\Programs\Cloud Code`
- `C:\Antigravity`
- `D:\Antigravity`

如果自动探测失败，可以手动指定：

```powershell
.\patch_antigravity.cmd --root "D:\Antigravity"
```

或直接指定两个目标文件：

```powershell
$env:ANTIGRAVITY_WORKBENCH_PATH="D:\Antigravity\resources\app\out\vs\workbench\workbench.desktop.main.js"
$env:ANTIGRAVITY_JETSKI_PATH="D:\Antigravity\resources\app\out\jetskiAgent\main.js"
.\patch_antigravity.cmd
```

## 更新后怎么处理

Antigravity 更新后，原始 JS 文件可能被覆盖。通常只需要重新运行一次：

```powershell
.\patch_antigravity.cmd
```

当前脚本会：

- 自动识别新版本安装目录
- 发现当前文件是“新版未 patch”时自动刷新 `.bak`
- 重新按结构匹配并注入 patch

这就是面向后续更新的主要解决办法。

## CLI 选项

- `--print-paths`：只打印检测到的文件路径
- `--check`：检查当前安装是否已 patch 或仍然可 patch
- `--root <path>`：手动指定安装根目录、`.app` 路径或 exe 所在目录
- `--restore`：从 `.bak` 恢复原始文件

## 目录说明

- `patch_antigravity.py`：主脚本
- `patch_antigravity.cmd`：Windows 启动器
- `Antigravity-Auto-Retry-Patch.md`：更详细的中文技术说明

## 风险与限制

- 这是非官方 patch，会直接修改 Antigravity 本地安装文件
- 虽然新版脚本已经不依赖具体压缩变量名，但如果 Antigravity 将错误通知逻辑整体重写，仍然可能失配
- 如果 `--check` 或 patch 提示 `signature not found`，说明当前版本的错误分支结构已经变了，需要重新适配
- 这个项目只改变本地 UI 自动重试行为，不改变后端容量状态

## License

仓库已包含 `MIT` 许可证，见 `LICENSE`。

---

## English

Antigravity can surface `503 No capacity available` and then show `Agent terminated due to error`, forcing a manual `Retry` click before the agent can continue. This project patches Antigravity's local bundled frontend files so `retryable` and `generic` agent failures trigger one automatic retry before the original notification is shown.

This version fixes two practical problems:

- it no longer relies on one exact minified JS string from an older app build
- it adds a Windows launcher, so the patch is still easy to run when `python` or `py` is not on `PATH`

## What This Repo Includes

- `patch_antigravity.py`
- `patch_antigravity.cmd`
- Windows install auto-detection
- backup / restore support
- backup refresh when the app updates
- `--check` mode

## Why The Older Script Broke After Updates

The older approach replaced one exact minified JS string. That is fragile because an app update can break the match even when the feature still exists:

- variable names change
- bundling output changes
- object field ordering changes

The current script uses structure-based patching instead:

- it finds the `retryable` and `generic` switch branches
- captures the original notification object
- calls the notification's existing `primaryAction.onClick()`

That makes the patch much more resilient to minifier renames and routine updates.

## How It Works

The script patches both:

- `resources/app/out/vs/workbench/workbench.desktop.main.js`
- `resources/app/out/jetskiAgent/main.js`

The inserted logic:

- waits 500ms and auto-clicks the original primary action on the first matching error
- retries each notification ID only once
- falls back to the original popup behavior on the second hit

The retry state is stored in `globalThis.__agAutoRetryIds`.

## Quick Start

### Windows

Close Antigravity, then run:

```bat
patch_antigravity.cmd
```

If you prefer Python directly:

```powershell
& "C:\Program Files\Python313\python.exe" .\patch_antigravity.py
```

Restart Antigravity after the patch completes.

### macOS

```bash
python3 ./patch_antigravity.py
```

## Useful Commands

Print detected paths:

```powershell
.\patch_antigravity.cmd --print-paths
```

Check whether the current install is already patched or still patchable:

```powershell
.\patch_antigravity.cmd --check
```

Restore original files:

```powershell
.\patch_antigravity.cmd --restore
```

## Update Workflow

After Antigravity updates, the bundled JS files may be replaced. In most cases you only need to re-run:

```powershell
.\patch_antigravity.cmd
```

The script will:

- locate the current install again
- refresh stale backups when it detects a new unpatched app version
- re-apply the structure-based patch

## Limitations

- this is an unofficial patch that modifies local Antigravity files
- if Antigravity fully rewrites the error notification flow, the matcher may still need an update
- if `--check` reports `signature not found`, the new app build changed the relevant structure enough to require a new adaptation
