#!/usr/bin/env bash
# Wrap the entire installer so child processes cannot consume a piped script.
main() {
    set -Eeuo pipefail
    trap 'printf "安装失败（行 %s），可修复后重跑。\n" "$LINENO" >&2' ERR
    if [[ -z "${PREFIX:-}" || ! -x "$PREFIX/bin/pkg" || ! -x "$PREFIX/bin/apt-get" ]]; then
        printf '请在 Android 原生 Termux（APT）中运行，不支持普通 Linux/proot 客体。\n' >&2
        exit 1
    fi
    command -v timeout >/dev/null || {
        printf '缺少 Termux 基础命令 timeout，请先修复 coreutils。\n' >&2
        exit 1
    }
    local limit="${TERMUX_KIT_TIMEOUT:-1200}"
    [[ "$limit" =~ ^[1-9][0-9]*$ ]] || { printf 'TERMUX_KIT_TIMEOUT 必须为正整数秒。\n' >&2; exit 1; }
    export DEBIAN_FRONTEND=noninteractive
    local -a opts=(-y '-o' 'Dpkg::Options::=--force-confdef' '-o' 'Dpkg::Options::=--force-confold'
        '-o' 'Acquire::Retries=2' '-o' 'Acquire::http::Timeout=30'
        '-o' 'Acquire::https::Timeout=30' '-o' 'DPkg::Lock::Timeout=60')
    printf '更新软件索引，每步最多等待 %s 秒…\n' "$limit"
    timeout --kill-after=15s "${limit}s" pkg update "${opts[@]}" </dev/null
    timeout --kill-after=15s "${limit}s" pkg install "${opts[@]}" \
        openssh mosh tmux termux-tools termux-api nodejs-lts android-tools \
        git python build-essential curl tar proot ca-certificates </dev/null
    python - <<'PYCONFIG'
import os
import shutil
import tempfile
import time
from pathlib import Path

folder = Path.home() / ".termux"
folder.mkdir(parents=True, exist_ok=True)
path = folder / "termux.properties"
if path.is_symlink():
    raise SystemExit("termux.properties 为软链，请先手动确认目标，避免覆盖。")
original = path.read_text() if path.exists() else ""
# Remove only the two owned Java properties, including continued lines.
kept = []
skip = False
for line in original.splitlines(keepends=True):
    stripped = line.lstrip()
    owned = any(__import__('re').match(r"^" + name + r"(?:\s|[=:]|$)", stripped)
                for name in ("bell-character", "extra-keys"))
    remove = skip or owned
    tail = line.rstrip("\r\n")
    continued = (len(tail) - len(tail.rstrip("\\"))) % 2 == 1
    skip = remove and continued
    if not remove:
        kept.append(line)
keys = "extra-keys = [['ESC','/',{macro:'ALT p',display:'MDL'},{key:'PASTE',display:'PST'},{macro:'CTRL b p',display:'PRV'},'UP',{macro:'CTRL b n',display:'NXT'},{key:'PGUP',display:'PGU'},{key:'BKSP',display:'DEL'}],['TAB',{key:'CTRL',display:'CTL'},'ALT',{macro:'SHIFT TAB',display:'S-T'},'LEFT','DOWN','RIGHT',{key:'PGDN',display:'PGD'},{key:'ENTER',display:'[ENT]'}]]"
content = ''.join(kept)
if content and not content.endswith('\n'):
    content += '\n'
content += 'bell-character = ignore\n' + keys + '\n'
if content != original:
    if path.exists():
        backup = path.with_name(path.name + '.bak.' + str(time.time_ns()))
        shutil.copy2(path, backup)
        print('原配置已备份：', backup)
    fd, temp = tempfile.mkstemp(prefix='.termux.properties.', dir=folder)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        if path.exists():
            shutil.copymode(path, temp)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
PYCONFIG
    if ! timeout --kill-after=5s 15s termux-reload-settings </dev/null; then
        printf '配置已保存，但重载失败或超时，请重开 Termux 后确认键盘。\n' >&2
        exit 1
    fi
    printf '基础依赖和双排九列键盘初始化完成。\n'
}
main "$@"
