# 安卓 Termux：Codex 与远程接入完整操作指南

本指南介绍 Android ARM64 原生 Termux 中的 Codex 兼容与反向 SSH 配置。示例使用占位主机、账号与端口，请按自己的设备验证。设备身份、真实连接参数和个人验收记录不在公开仓库维护。

## 1. 配置顺序与目标

先运行 README 中的基础初始化，再确认 AI 可以实际执行命令，然后配置 SSH、反向通道、自动重连、开机启动，最后验证锁屏、切网和重启。

手机保留现有 VPN，通过主动出站 SSH 连接已有跳板；Mac 和服务器经跳板连接回手机，不需要给手机开公网端口，也不依赖安卓 Tailscale。Android 通常只允许一个 VPN 服务同时运行，不能直接让现有 VPN 与 Tailscale 安卓客户端同时工作。

这提供 Termux 文件与命令行访问，不提供安卓屏幕控制权限。安装 ADB 命令也不代表已取得安卓系统调试权限。

## 2. 先确认 Termux 来源和 AI 安装状态

在原生 Termux 执行，整个过程保持一个可用终端：

```sh
termux-info
uname -m
whoami
command -v codex
codex --version
ls -l "$PREFIX/bin/codex" "$PREFIX/bin/codex.real" "$PREFIX/bin/codex-code-mode-host"
npm list -g --depth=0
```

`termux-info` 的 APK release 可区分 Google Play、F-Droid 等来源。不要混装不同签名来源的应用与插件，不要为更换来源卸载已有数据。

npm 中出现 `@openai/codex` 不代表完整安装。某些安装方式使用 JS 启动入口，也有安装方式通过 `proot` 包装独立二进制文件。版本号能显示，也不代表命令工具能运行。

全新设备安装参考官方 CLI 安装说明，需按版本核对 Linux ARM64 完整包及组件。不要只用 `npm install -g` 的成功作为验收。以下修复流程针对已经有可启动 `codex.real` / proot 包装的设备，并非全新安装器。

### 三种错误要分别处理

| 实际错误 | 含义与处理 |
| --- | --- |
| `this CLI has no complete local package` | 当前安装不满足后台服务的完整包要求；`codex --no-daemon` 可绕过该启动路径，但必须继续验收工具 |
| 缺少 `codex-code-mode-host` | 缺少执行组件，补齐同版本、同架构的官方组件；不要关闭 `code_mode_host`，否则可能出现 `code-mode host is disabled` |
| `error building bubblewrap command: Permission denied` | 工具已走到安卓不允许的隔离路径；可按下面的方式对照验证，实际成功与否以设备输出为准 |

`codex doctor --summary --no-color` 可辅助检查，但摘要正常不代表执行组件必然齐全。网络、登录、聊天、工具执行是不同检查项。ripgrep 缺失警告可通过 `pkg install ripgrep` 处理，但不能解释上述所有错误。

### 补齐同版本 ARM64 执行组件

先阅读脚本。它不覆盖已有组件，不升级 Codex；下载或版本检查失败即停止。仅适用于 `aarch64`，以及官方存在对应发布资产的版本。发行包名称未来可能变化，失败时不要改用不明来源文件。

```sh
(
set -eu
case "$(uname -m)" in
  aarch64) ;;
  *) echo "架构不符，停止"; exit 1 ;;
esac
version="$(codex --version | awk '{print $2}')"
case "$version" in
  ''|*[!0-9.]*) echo "无法确认版本，停止"; exit 1 ;;
esac
test ! -e "$PREFIX/bin/codex-code-mode-host" || {
  echo "组件已存在，请先核实版本与可执行性，不覆盖"
  exit 1
}
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
curl --fail --location --connect-timeout 15 --max-time 180 \
  "https://github.com/openai/codex/releases/download/rust-v${version}/codex-code-mode-host-aarch64-unknown-linux-musl.tar.gz" \
  -o "$work/host.tar.gz"
tar -xzf "$work/host.tar.gz" -C "$work"
cp "$work/codex-code-mode-host-aarch64-unknown-linux-musl" \
  "$PREFIX/bin/codex-code-mode-host"
chmod 700 "$PREFIX/bin/codex-code-mode-host"
)
```

组件升级必须与 CLI 版本配套；上面的“已存在则停止”不负责处理版本不一致。

### 启动与真正验收

```sh
codex --no-daemon --sandbox danger-full-access --ask-for-approval on-request
```

这会关闭 Codex 的文件与网络隔离，保留按请求确认操作的机制。工具可访问 Termux 用户本来能访问的文件和网络，不能因此取得 root 或修改安卓系统权限；只对可信任务使用，不附加跳过所有确认的参数。

进入后要求 AI 实际执行 `echo OK` 和 `whoami`。两条命令输出正确且退出码为 0 才算工具验收。仅回复“收到”不算。设备用户名以自己的实际输出为准。

可另外创建用户级便捷入口，转发所有参数，例如在已有 PATH 的目录内保存 `codex-termux`：

```sh
#!/data/data/com.termux/files/usr/bin/sh
exec codex --no-daemon --sandbox danger-full-access --ask-for-approval on-request "$@"
```

设为可执行后可用 `codex-termux resume`。不要直接覆盖已有的 `codex` 包装器。本便捷入口仅为示例，需在自己的设备验证。

## 3. 独立密钥与跳板授权

以下全部为模板，先替换示例账号、域名、机器名和端口，不要照抄连接不存在的示例主机。多台设备分别使用独立密钥、端口及可信主机记录。以下名称 `android-device` 仅为示例。

```sh
pkg install openssh util-linux
mkdir -p ~/.ssh ~/.local/bin ~/.local/state/android-device ~/.termux/boot
chmod 700 ~/.ssh
# 若此路径已有密钥，先核对，不覆盖。
test -e ~/.ssh/android-device_ed25519 || ssh-keygen -t ed25519 -f ~/.ssh/android-device_ed25519 -N ''
ssh-keygen -lf ~/.ssh/android-device_ed25519.pub
```

无人值守通道需能非交互使用密钥，示例为空口令专用密钥，必须保管好私钥并限制用途。只将 `.pub` 公钥添加到跳板的 authorized_keys，客户端设备各自使用自己的私钥。不要复制任何 Mac 或服务器私钥到手机。

先通过已信任的渠道获取跳板主机指纹并写入 known_hosts。`ssh-keyscan` 单独得到的结果不构成身份核验。使用已获授权的远端会话备份后追加公钥，勿覆盖其他人的授权。

在跳板检查待用端口未被占用；同时检查为离线设备预留的端口，不能只看当前监听。示例使用 22022，第二台设备可选另一个空闲端口，实际仍须检查。跳板 sshd 必须允许远程端口转发，且不能用 GatewayPorts=yes 把请求的回环端口改成公网监听。

```sh
ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes \
  -i ~/.ssh/android-device_ed25519 user@jump.example.com 'id -un'
```

探测失败就先处理授权、指纹、网络或转发限制，不无限重试，不关闭主机校验。

## 4. 反向通道与单实例重连

以下是通用反向隧道模板。保存为 `~/.local/bin/android-device-tunnel`，替换跳板账号、主机和已确认空闲的端口。Termux 的 OpenSSH 默认使用其 `$PREFIX/etc/ssh` 配置，不是普通 Linux 的系统 SSH 配置。

手机 SSH 服务仅监听本机 8022；跳板反向端口仅监听跳板 127.0.0.1。先验证各客户端公钥登录成功，再考虑关闭密码登录，避免锁死入口。

```bash
#!/data/data/com.termux/files/usr/bin/bash
set -u
export PATH=/data/data/com.termux/files/usr/bin:$PATH
state="$HOME/.local/state/android-device"
mkdir -p "$state"
exec 9>"$state/lock"
flock -n 9 || exit 0
exec >>"$state/tunnel.log" 2>&1
trap 'exit 0' TERM INT
# 初次配置前确认端口无人占用；重复运行时要确认已有监听确为预期 sshd。
sshd -o ListenAddress=127.0.0.1 -p 8022
while :; do
  date -u '+%FT%TZ connecting'
  ssh -NT -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UpdateHostKeys=no -o IdentitiesOnly=yes \
    -i "$HOME/.ssh/android-device_ed25519" \
    -o ConnectTimeout=10 -o ConnectionAttempts=1 \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    -o ControlMaster=yes -o ControlPath="$HOME/.ssh/android-device-live.sock" \
    -R 127.0.0.1:22022:127.0.0.1:8022 user@jump.example.com
  code=$?
  printf 'ssh exited %s; retry in 15s\n' "$code"
  sleep 15
done
```

`flock` 防止脚本重复启动。日志需要按设备存储条件定期轮换，示例未提供自动轮换。长期 SSH 循环是必要的专用通道，不要让它以前台方式占住 Codex 工具调用。

将脚本设为可执行，先测试后台启动和回连：

```sh
chmod 700 ~/.local/bin/android-device-tunnel
setsid -f "$HOME/.local/bin/android-device-tunnel" </dev/null >/dev/null 2>&1
```

进程存在不代表转发成功。需在跳板确认监听位于回环地址，再通过该端口实际执行远程命令。

## 5. Mac、服务器与另一台手机如何访问

手机 `~/.ssh/authorized_keys` 中追加每个获授权客户端的公钥。对所有文件改动先备份，只添加公钥，不分发客户端私钥。

通过已经验证的手机连接读取手机 SSH 主机公钥，在可信渠道核对指纹，再为每个客户端准备 `~/.ssh/known_hosts_android-device`。配合 `HostKeyAlias=android-device` 时，专用文件记录应使用这个别名，而不是误用公网跳板身份。以下记录为格式示意，不能使用占位公钥连接：

```text
android-device ssh-ed25519 <从手机可信读取的主机公钥内容>
```

```sh
ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=yes \
  -o HostKeyAlias=android-device \
  -o UserKnownHostsFile=~/.ssh/known_hosts_android-device \
  -o 'ProxyCommand=ssh -o BatchMode=yes -o ConnectTimeout=10 -W %h:%p user@jump.example.com' \
  -p 22022 PHONE_USER@127.0.0.1 whoami
```

`PHONE_USER` 用自己的设备实际 `whoami` 结果替换。代理子连接也需要跳板的独立授权和可信主机记录。上面的 127.0.0.1 指跳板回环地址，不能去掉代理后误连客户端自己。

常用入口可写入客户端 SSH config，保持上述身份校验和独立密钥设置。每台机器分别验证，不能把单台维护电脑成功写成全部成功。两台手机之间同理：互授专用客户端公钥，经跳板连接对方的不同反向端口；不共享私钥。

## 6. 开机启动与安卓后台权限

Google Play 版 Termux 自 2024.10.24 起已将 Boot 功能合并入主应用，不需要另外安装 Termux:Boot。F-Droid / GitHub 等来源应按其官方说明安装匹配签名的 Boot 插件，并打开一次。不要要求所有用户都去找不存在的独立插件。

保存为 `~/.termux/boot/android-device-tunnel` 并设为可执行：

```bash
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
setsid -f "$HOME/.local/bin/android-device-tunnel" </dev/null >/dev/null 2>&1
```

保存后执行 `chmod 700 ~/.termux/boot/android-device-tunnel`。

安卓 15 入口依厂商而异：长按 Termux 图标 → 应用信息 → 电池使用情况 → 允许后台使用。若能展开并选择“不受限制”则选择；没有该选项就不要盲找。系统有自启动开关时允许自启动。独立 Boot 插件若存在，也需对应设置。

Termux 的 SSH 身份不是 Android 系统 shell 或 root。部分系统设置命令需要额外权限，Termux 的普通账号可能无法修改。唤醒锁也不保证厂商永不结束进程，并会增加耗电。

## 7. 验收与故障恢复

按顺序验证并在自己的私有设备清单记录结果，不把实际账号、地址、端口、主机指纹及运行日志放入公开教程：

1. Codex 实际执行 echo 和 whoami。调用模型前确认费用与授权。
2. 手机登录跳板，再从维护电脑经反向端口登录手机。
3. 每个获授权客户端分别验证，不能把单机成功当作全部成功。
4. 只断开本设备专用隧道，验证自动重连，不结束无关会话。
5. 分别验证长时间锁屏、切换网络、重启解锁后自动恢复。
6. 如需设备间互访，各自授权公钥，不共享私钥。

遇到 `Bad packet length / Connection corrupted`，先收集实际错误与默认配置下的可重复结果，不据此猜测端口冲突、加密算法或 PRoot 根因，也不要关闭主机身份校验。

原生后台服务的 `/proc/<pid>/status` 中 TracerPid 应为 0；若由 PRoot 跟踪，需要分别验证原生开机启动路径。部分 Android 版本不允许读取 `/proc/uptime`，可用 Python 的 `time.clock_gettime(time.CLOCK_BOOTTIME)` 获取启动后秒数。

终端无响应时先尝试 Ctrl+Q，排除流控暂停。强行停止 Termux 会结束服务和任务，执行前确认影响；不清除应用数据或卸载。SSH 入口已建立时优先复用远程维护通道，不因 ADB 离线要求重新配置或插数据线。

## 官方参考

- [Codex CLI](https://developers.openai.com/codex/cli/)
- [Codex 0.167.0 官方发布与组件](https://github.com/openai/codex/releases/tag/rust-v0.167.0)
- [Google Play Termux 与内置 Boot 公告](https://github.com/termux-play-store)
- [其他来源的 Termux:Boot 安装和签名要求](https://github.com/termux/termux-boot)
- [Android 的 VPN 共存限制](https://tailscale.com/docs/reference/faq/other-vpns)
