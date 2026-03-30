#!/usr/bin/env python3
"""
Antigravity Auto-Retry Patch

Automatically patches Antigravity so transient agent failures trigger one
automatic retry before the original error notification is shown.

Highlights:
- Structure-based patching that survives minified variable renames
- Windows install auto-detection with registry and common-path fallbacks
- Backup auto-refresh when the app updates
- Optional restore mode
- Optional check mode
"""

import argparse
import glob
import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Pattern, Set, Tuple


WORKBENCH_REL = Path("resources") / "app" / "out" / "vs" / "workbench" / "workbench.desktop.main.js"
JETSKI_REL = Path("resources") / "app" / "out" / "jetskiAgent" / "main.js"

ENV_INSTALL_DIR = "ANTIGRAVITY_INSTALL_DIR"
ENV_WORKBENCH_PATH = "ANTIGRAVITY_WORKBENCH_PATH"
ENV_JETSKI_PATH = "ANTIGRAVITY_JETSKI_PATH"

MAC_APP_BUNDLE = Path("/Applications/Antigravity.app")
MAC_CONTENTS_ROOT = MAC_APP_BUNDLE / "Contents"

AUTO_RETRY_SET_NAME = "__agAutoRetryIds"
AUTO_RETRY_NOTIFICATION_NAME = "__agAutoRetryNotification"


@dataclass(frozen=True)
class CasePatch:
    case_name: str
    primary_label: str
    primary_message: str
    pattern: Pattern[str]


def build_case_pattern(case_name: str, primary_label: str, primary_message: str) -> Pattern[str]:
    return re.compile(
        rf'case"{re.escape(case_name)}":return(?P<object>\{{id:(?P<id>[^,]+),(?P<body>.*?)'
        rf'primaryAction:(?P<action>[A-Za-z_$][\w$]*)\("{re.escape(primary_label)}","{re.escape(primary_message)}"\),'
        rf'secondaryAction:(?P<secondary>[A-Za-z_$][\w$]*)\(\)\}})',
        re.DOTALL,
    )


CASE_PATCHES = [
    CasePatch(
        case_name="retryable",
        primary_label="Try again",
        primary_message="Try again",
        pattern=build_case_pattern("retryable", "Try again", "Try again"),
    ),
    CasePatch(
        case_name="generic",
        primary_label="Retry",
        primary_message="Continue",
        pattern=build_case_pattern("generic", "Retry", "Continue"),
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch Antigravity to auto-retry transient agent failures once."
    )
    parser.add_argument(
        "--root",
        help="Install root or app path. Examples: Antigravity install dir, .app bundle, or exe directory.",
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print detected file paths and exit.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore backed-up original files instead of applying the patch.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether the detected files are patchable/already patched without modifying them.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def backup_path_for(path: Path) -> Path:
    return Path(f"{path}.bak")


def dedupe_paths(paths: List[Path]) -> List[Path]:
    result: List[Path] = []
    seen: Set[str] = set()
    for path in paths:
        try:
            normalized = str(path.expanduser().resolve(strict=False))
        except OSError:
            normalized = str(path.expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(Path(normalized))
    return result


def pair_from_base(base: Path) -> Optional[Tuple[Path, Path]]:
    workbench = base / WORKBENCH_REL
    jetski = base / JETSKI_REL
    if workbench.is_file() and jetski.is_file():
        return workbench, jetski
    return None


def resolve_pair_from_hint(path_hint: Path) -> Optional[Tuple[Path, Path]]:
    hint = Path(path_hint).expanduser()
    variants: List[Path] = []

    if hint.is_file():
        variants.extend(list(hint.parents))
    else:
        variants.append(hint)
        variants.append(hint / "Contents")
        variants.extend(list(hint.parents))

    for candidate in dedupe_paths(variants):
        pair = pair_from_base(candidate)
        if pair:
            return pair
    return None


def extract_fs_path(raw: str) -> Optional[Path]:
    text = raw.strip().strip('"')
    if not text:
        return None

    if text.lower().endswith(".exe,0"):
        text = text[:-2]
    elif ".exe," in text.lower():
        text = text.rsplit(",", 1)[0]

    path = Path(text)
    if path.exists():
        return path
    return None


def query_registry_string(key, name: str) -> str:
    try:
        value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return ""
    return value if isinstance(value, str) else ""


def windows_registry_roots() -> List[Path]:
    roots: List[Path] = []
    try:
        global winreg
        import winreg  # type: ignore
    except ImportError:
        return roots

    uninstall_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    hints = ("antigravity", "cloud code")

    for hive, subkey in uninstall_keys:
        try:
            parent_key = winreg.OpenKey(hive, subkey)
        except OSError:
            continue

        try:
            child_count = winreg.QueryInfoKey(parent_key)[0]
            for index in range(child_count):
                try:
                    child_name = winreg.EnumKey(parent_key, index)
                    app_key = winreg.OpenKey(parent_key, child_name)
                except OSError:
                    continue

                with app_key:
                    display_name = query_registry_string(app_key, "DisplayName")
                    install_location = query_registry_string(app_key, "InstallLocation")
                    display_icon = query_registry_string(app_key, "DisplayIcon")
                    combined = " ".join([display_name, install_location, display_icon]).lower()
                    if not any(hint in combined for hint in hints):
                        continue

                    for raw_value in (install_location, display_icon):
                        extracted = extract_fs_path(raw_value)
                        if not extracted:
                            continue
                        roots.append(extracted if extracted.is_dir() else extracted.parent)
        finally:
            winreg.CloseKey(parent_key)

    return dedupe_paths(roots)


def windows_default_roots() -> List[Path]:
    home = Path.home()
    local_appdata = home / "AppData" / "Local"

    candidates = [
        local_appdata / "Programs" / "Antigravity",
        local_appdata / "Programs" / "antigravity-stable-user-x64",
        local_appdata / "Programs" / "Cloud Code",
        local_appdata / "Antigravity",
        Path(r"C:\Antigravity"),
        Path(r"D:\Antigravity"),
    ]

    return dedupe_paths(candidates)


def windows_glob_roots() -> List[Path]:
    candidates: List[Path] = []
    home = Path.home()
    local_appdata = Path(os.environ.get("LOCALAPPDATA", "")) if os.environ.get("LOCALAPPDATA") else home / "AppData" / "Local"
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))

    base_dirs = [
        local_appdata / "Programs",
        local_appdata,
        program_files,
        program_files_x86,
    ]

    name_patterns = [
        "*Antigravity*",
        "*antigravity*",
        "*Cloud Code*",
        "*cloud code*",
        "*cloud-code*",
        "antigravity-stable-user-x64",
    ]

    for base_dir in base_dirs:
        if not base_dir.exists():
            continue

        for pattern in name_patterns:
            for match in glob.glob(str(base_dir / pattern)):
                root = Path(match)
                candidates.append(root)
                for child_pattern in ("app-*", "current"):
                    candidates.extend(root.glob(child_pattern))

    return dedupe_paths(candidates)


def discover_paths(manual_root: Optional[str]) -> Optional[Tuple[Path, Path, str]]:
    explicit_workbench = os.environ.get(ENV_WORKBENCH_PATH)
    explicit_jetski = os.environ.get(ENV_JETSKI_PATH)

    if explicit_workbench or explicit_jetski:
        if not (explicit_workbench and explicit_jetski):
            print(
                f"[ERROR] {ENV_WORKBENCH_PATH} and {ENV_JETSKI_PATH} must be set together.",
                file=sys.stderr,
            )
            return None
        workbench = Path(explicit_workbench).expanduser()
        jetski = Path(explicit_jetski).expanduser()
        if workbench.is_file() and jetski.is_file():
            return workbench, jetski, "environment file override"
        print("[ERROR] Environment override paths do not point to existing files.", file=sys.stderr)
        return None

    candidate_hints: List[Tuple[str, Path]] = []

    if manual_root:
        candidate_hints.append(("--root", Path(manual_root).expanduser()))

    env_root = os.environ.get(ENV_INSTALL_DIR)
    if env_root:
        candidate_hints.append((ENV_INSTALL_DIR, Path(env_root).expanduser()))

    if platform.system() == "Windows":
        candidate_hints.extend(("registry", path) for path in windows_registry_roots())
        candidate_hints.extend(("default", path) for path in windows_default_roots())
        candidate_hints.extend(("glob", path) for path in windows_glob_roots())

    candidate_hints.append(("macOS default", MAC_CONTENTS_ROOT))
    candidate_hints.append(("macOS app bundle", MAC_APP_BUNDLE))

    for source, hint in candidate_hints:
        pair = resolve_pair_from_hint(hint)
        if pair:
            return pair[0], pair[1], f"{source}: {hint}"

    return None


def current_case_marker(case_name: str) -> str:
    return f'case"{case_name}":{{let {AUTO_RETRY_NOTIFICATION_NAME}='


def legacy_case_marker(case_name: str) -> str:
    return f'case"{case_name}":{{if(!globalThis._agRetried)'


def current_case_replacement(case_name: str, object_expr: str) -> str:
    notification = AUTO_RETRY_NOTIFICATION_NAME
    retry_set = AUTO_RETRY_SET_NAME
    return (
        f'case"{case_name}":{{let {notification}={object_expr};'
        f'if(!globalThis.{retry_set})globalThis.{retry_set}=new Set;'
        f'if(!globalThis.{retry_set}.has({notification}.id)){{'
        f'globalThis.{retry_set}.add({notification}.id);'
        f'return setTimeout(()=>{{{notification}.primaryAction.onClick()}},500),void 0}}'
        f"return {notification}}}"
    )


def case_status(content: str, patch: CasePatch) -> Tuple[str, str]:
    if current_case_marker(patch.case_name) in content:
        return "patched", "already patched with structure-based matcher"
    if legacy_case_marker(patch.case_name) in content:
        return "patched", "already patched with legacy matcher"

    matches = list(patch.pattern.finditer(content))
    if len(matches) == 1:
        return "patchable", "signature found"
    if len(matches) == 0:
        return "missing", "signature not found"
    return "ambiguous", f"signature matched {len(matches)} times"


def content_is_fully_unpatched(content: str) -> bool:
    return all(case_status(content, patch)[0] == "patchable" for patch in CASE_PATCHES)


def apply_case_patch(content: str, patch: CasePatch) -> Tuple[str, bool, str]:
    status, detail = case_status(content, patch)
    if status == "patched":
        return content, False, f"{patch.case_name}: {detail}"
    if status == "missing":
        return content, False, f"{patch.case_name}: signature not found; app version may have changed"
    if status == "ambiguous":
        return content, False, f"{patch.case_name}: {detail}"

    matches = list(patch.pattern.finditer(content))
    match = matches[0]
    replacement = current_case_replacement(patch.case_name, match.group("object"))
    updated, count = patch.pattern.subn(replacement, content, count=1)

    if count != 1:
        return content, False, f"{patch.case_name}: failed to apply replacement"
    return updated, True, f"{patch.case_name}: patch applied"


def patch_file(filepath: Path) -> bool:
    if not filepath.exists():
        print(f"  [ERROR] File not found: {filepath}")
        return False

    content = read_text(filepath)
    backup = backup_path_for(filepath)

    if not backup.exists():
        shutil.copy2(filepath, backup)
        print(f"  [OK] Backup created: {backup.name}")
    else:
        backup_content = read_text(backup)
        if content_is_fully_unpatched(content) and backup_content != content:
            shutil.copy2(filepath, backup)
            print(f"  [OK] Backup refreshed for current app version: {backup.name}")
        else:
            print(f"  [OK] Using existing backup: {backup.name}")

    updated = content
    changed = False

    for index, patch in enumerate(CASE_PATCHES, start=1):
        updated, case_changed, message = apply_case_patch(updated, patch)
        if "signature not found" in message or "matched" in message or "failed" in message:
            print(f"  [ERROR] Patch {index} {message}")
            return False
        changed = changed or case_changed
        print(f"  [OK] Patch {index} {message}")

    if changed:
        write_text(filepath, updated)
        print("  [OK] File updated")
    else:
        print("  [OK] No changes needed")
    return True


def check_file(filepath: Path) -> bool:
    if not filepath.exists():
        print(f"  [ERROR] File not found: {filepath}")
        return False

    content = read_text(filepath)
    overall_ok = True

    for patch in CASE_PATCHES:
        status, detail = case_status(content, patch)
        if status in {"patched", "patchable"}:
            print(f"  [OK] {patch.case_name}: {detail}")
            continue
        overall_ok = False
        print(f"  [WARN] {patch.case_name}: {detail}")

    return overall_ok


def restore_file(filepath: Path) -> bool:
    backup = backup_path_for(filepath)
    if not backup.exists():
        print(f"  [ERROR] Backup not found: {backup}")
        return False
    shutil.copy2(backup, filepath)
    print(f"  [OK] Restored from backup: {filepath.name}")
    return True


def print_detected_paths(workbench: Path, jetski: Path, source: str) -> None:
    print("=" * 60)
    print("Antigravity Auto-Retry Patch")
    print("=" * 60)
    print(f"Detected via : {source}")
    print(f"Workbench   : {workbench}")
    print(f"JetskiAgent : {jetski}")


def main() -> int:
    args = parse_args()
    discovered = discover_paths(args.root)

    if not discovered:
        print("=" * 60)
        print("Antigravity Auto-Retry Patch")
        print("=" * 60)
        print("[ERROR] Could not locate the Antigravity installation.")
        print("Try one of the following:")
        print('  1. Run with --root "<install_dir>"')
        print(f"  2. Set {ENV_INSTALL_DIR}")
        print(f"  3. Set both {ENV_WORKBENCH_PATH} and {ENV_JETSKI_PATH}")
        return 1

    workbench_path, jetski_path, source = discovered
    print_detected_paths(workbench_path, jetski_path, source)

    if args.print_paths:
        return 0

    if args.restore:
        print("\n[1/2] Restoring workbench.desktop.main.js")
        result_1 = restore_file(workbench_path)

        print("\n[2/2] Restoring jetskiAgent/main.js")
        result_2 = restore_file(jetski_path)
    elif args.check:
        print("\n[1/2] Checking workbench.desktop.main.js")
        result_1 = check_file(workbench_path)

        print("\n[2/2] Checking jetskiAgent/main.js")
        result_2 = check_file(jetski_path)
    else:
        print("\n[1/2] Patching workbench.desktop.main.js")
        result_1 = patch_file(workbench_path)

        print("\n[2/2] Patching jetskiAgent/main.js")
        result_2 = patch_file(jetski_path)

    print("\n" + "=" * 60)
    if result_1 and result_2:
        if args.restore:
            print("[OK] Restore completed. Restart Antigravity.")
        elif args.check:
            print("[OK] Check completed. The current installation is patchable or already patched.")
        else:
            print("[OK] Patch completed. Restart Antigravity.")
    else:
        print("[WARN] Completed with errors. Check the messages above.")
    print("=" * 60)
    return 0 if result_1 and result_2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
