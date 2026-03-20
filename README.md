# Antigravity Auto-Retry Patch

中文 | [English](#english)

Antigravity 在部分模型和时段下会遇到 `503 No capacity available`，随后弹出 `Agent terminated due to error`，必须手动点击 `Retry` 才能继续。本项目通过修改 Antigravity 前端打包产物，在 `retryable` 和 `generic` 两类错误上自动发送一次重试消息，减少人工干预。

这个仓库提供：
- 自动 patch 脚本 `patch_antigravity.py`
- Windows 安装目录自动探测
- macOS 默认路径支持
- 自动备份与恢复
- 适合直接开源发布的说明文档

## 功能特性

- 首次遇到目标错误时，自动发送一次 `Try again` 或 `Continue`
- 同一个错误只自动重试一次，避免无限循环
- 如果同一 step 再次失败，仍然保留原始弹窗行为
- Windows 下优先自动探测安装路径
- 支持 `--restore` 回滚
- 支持环境变量和 `--root` 手动覆盖路径

## 适用场景

- Antigravity / Cloud Code 在执行 agent 任务时频繁出现 503 容量错误
- 你不想每次都手动点 `Retry`
- 你接受直接修改本地应用安装目录中的 JS 文件

## 工作原理

脚本会同时修改下面两个文件：

- `resources/app/out/vs/workbench/workbench.desktop.main.js`
- `resources/app/out/jetskiAgent/main.js`

其中：
- `workbench.desktop.main.js` 负责主界面通知，是真正弹出错误提示的关键文件
- `jetskiAgent/main.js` 负责 agent 面板逻辑

脚本会在这两个文件的错误分支中插入一段逻辑：

- 使用 `globalThis._agRetried = new Set()` 记录已经自动重试过的 `notificationId`
- 第一次命中时，延迟 500ms 自动发出重试消息，不显示弹窗
- 第二次命中同一错误时，恢复原始通知逻辑

## 快速开始

### Windows

1. 关闭 Antigravity。
2. 在仓库目录运行：

```powershell
python .\patch_antigravity.py
# or
py -3 .\patch_antigravity.py
```

3. 重启 Antigravity。

如果你只想先看脚本识别到了哪个安装目录：

```powershell
python .\patch_antigravity.py --print-paths
# or
py -3 .\patch_antigravity.py --print-paths
```

### macOS

1. 关闭 Antigravity。
2. 在仓库目录运行：

```bash
python3 ./patch_antigravity.py
```

3. 重启 Antigravity。

## 路径解析规则

### Windows 自动探测

脚本会依次尝试：

1. `ANTIGRAVITY_WORKBENCH_PATH` + `ANTIGRAVITY_JETSKI_PATH`
2. `--root` 参数
3. `ANTIGRAVITY_INSTALL_DIR`
4. Windows 卸载注册表中的安装位置
5. 常见安装目录匹配，例如：
   - `%LOCALAPPDATA%\\Programs\\*Antigravity*`
   - `%LOCALAPPDATA%\\*Antigravity*`
   - `%ProgramFiles%\\*Antigravity*`
   - 常见 `app-*` / `current` 子目录
6. macOS 默认路径回退

如果自动探测失败，请手动指定：

```powershell
python .\patch_antigravity.py --root "C:\Path\To\Antigravity"
# or
py -3 .\patch_antigravity.py --root "C:\Path\To\Antigravity"
```

或者直接指定两个目标文件：

```powershell
$env:ANTIGRAVITY_WORKBENCH_PATH="C:\Path\To\workbench.desktop.main.js"
$env:ANTIGRAVITY_JETSKI_PATH="C:\Path\To\main.js"
python .\patch_antigravity.py
# or
py -3 .\patch_antigravity.py
```

## 更新后如何重新 patch

Antigravity 更新后，应用文件可能被覆盖，需要重新运行脚本：

```powershell
python .\patch_antigravity.py
# or
py -3 .\patch_antigravity.py
```

当前版本脚本会在检测到“应用文件已更新但 `.bak` 仍然是旧版本”时，自动刷新备份；通常不需要手动删除 `.bak`。

## 恢复原始文件

```powershell
python .\patch_antigravity.py --restore
# or
py -3 .\patch_antigravity.py --restore
```

## 命令行选项

- `--print-paths`：只打印检测到的文件路径，不执行 patch
- `--root <path>`：手动指定安装根目录、`.app` 路径或可执行文件所在目录
- `--restore`：用 `.bak` 备份恢复原始文件

## 目录说明

- `patch_antigravity.py`: 自动 patch 脚本
- `Antigravity-Auto-Retry-Patch.md`: 更详细的中文技术说明

## 风险与说明

- 这是非官方 patch，会直接修改 Antigravity 本地安装文件
- Antigravity 更新后可能导致字符串签名变化，从而 patch 失败
- 如果 patch 提示 `signature not found`，通常意味着新版本需要重新分析前端变量映射
- 本项目只处理本地 UI 层自动重试，不改变后端实际容量状态

## License

如需开源发布，请自行补充你希望使用的许可证。

---

## English

Antigravity can surface `503 No capacity available` and then show `Agent terminated due to error`, forcing a manual `Retry` click before the agent can continue. This project patches Antigravity's bundled frontend files so `retryable` and `generic` agent failures trigger one automatic retry before the original notification is shown.

This repository includes:
- `patch_antigravity.py`
- Windows install auto-detection
- macOS default-path support
- backup and restore support
- documentation suitable for a public GitHub repo

## Features

- Automatically sends `Try again` or `Continue` on the first matching failure
- Retries each error only once to avoid infinite loops
- Falls back to the original popup on repeated failure for the same step
- Auto-detects Windows install locations
- Supports `--restore`
- Supports manual overrides through environment variables or `--root`

## How It Works

The script patches both of these files:

- `resources/app/out/vs/workbench/workbench.desktop.main.js`
- `resources/app/out/jetskiAgent/main.js`

Why both:

- `workbench.desktop.main.js` is the main workbench bundle and is responsible for the actual notification popup
- `jetskiAgent/main.js` handles the agent panel side

The inserted logic:

- stores retried notification IDs in `globalThis._agRetried`
- sends one retry message after a 500ms delay
- suppresses the popup on the first hit
- falls back to the original notification flow on the second hit

## Quick Start

### Windows

1. Close Antigravity.
2. Run:

```powershell
python .\patch_antigravity.py
# or
py -3 .\patch_antigravity.py
```

3. Restart Antigravity.

To inspect detected paths first:

```powershell
python .\patch_antigravity.py --print-paths
# or
py -3 .\patch_antigravity.py --print-paths
```

### macOS

1. Close Antigravity.
2. Run:

```bash
python3 ./patch_antigravity.py
```

3. Restart Antigravity.

## Path Resolution

On Windows, the script checks the following in order:

1. `ANTIGRAVITY_WORKBENCH_PATH` and `ANTIGRAVITY_JETSKI_PATH`
2. `--root`
3. `ANTIGRAVITY_INSTALL_DIR`
4. uninstall-registry install locations
5. common install folders such as:
   - `%LOCALAPPDATA%\\Programs\\*Antigravity*`
   - `%LOCALAPPDATA%\\*Antigravity*`
   - `%ProgramFiles%\\*Antigravity*`
   - nested `app-*` / `current` folders
6. macOS fallback paths

If auto-detection fails, point the script at the install root:

```powershell
python .\patch_antigravity.py --root "C:\Path\To\Antigravity"
# or
py -3 .\patch_antigravity.py --root "C:\Path\To\Antigravity"
```

Or set direct file overrides:

```powershell
$env:ANTIGRAVITY_WORKBENCH_PATH="C:\Path\To\workbench.desktop.main.js"
$env:ANTIGRAVITY_JETSKI_PATH="C:\Path\To\main.js"
python .\patch_antigravity.py
# or
py -3 .\patch_antigravity.py
```

## Re-apply After an Update

Antigravity updates may overwrite the patched files. Re-run:

```powershell
python .\patch_antigravity.py
# or
py -3 .\patch_antigravity.py
```

This version automatically refreshes stale `.bak` files when it detects a new unpatched app version, so manual backup cleanup is usually unnecessary.

## Restore

```powershell
python .\patch_antigravity.py --restore
# or
py -3 .\patch_antigravity.py --restore
```

## CLI Options

- `--print-paths`: print detected file paths and exit
- `--root <path>`: manually specify an install root, `.app` bundle, or executable directory
- `--restore`: restore original files from `.bak`

## Notes

- This is an unofficial patch that modifies local Antigravity application files
- App updates can change bundle variable names and break exact string matching
- If you see `signature not found`, the current app version likely needs a new mapping analysis
- This only changes local retry behavior in the frontend; it does not change backend capacity
