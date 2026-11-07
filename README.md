# termux-devops-kit

Android 原生 Termux 的基础初始化、键盘与远程维护通用模板。

> 当前收录：基础依赖、双排九列键盘，以及 ARM64 安卓真机上的 Codex 修复、反向 SSH、后台运行与开机恢复方案。`install.sh` 仍只负责基础依赖与键盘；后续步骤见下文，不代表一键完成全部配置。

完整操作见 [安卓 AI 与远程接入指南](ANDROID_AI.md)。公开文档仅提供通用步骤与脱敏示例；真实设备参数、远程入口和个人验收记录请保存在自己的私有配置仓库。

## 一键初始化

在 Android 掌机或手机的原生 Termux 中执行：

```bash
curl -fsSL https://raw.githubusercontent.com/andyleimc-source/termux-devops-kit/main/install.sh | bash
```

需要网络、可用的 APT 软件源及足够存储空间。普通 Linux 掌机和 proot 内的 Linux 发行版不能直接运行此脚本。不要使用 root。仓库公开，无需 GitHub token。

如需先检查下载内容，并避免下载中断被管道掩盖：

```bash
curl -fsSL https://raw.githubusercontent.com/andyleimc-source/termux-devops-kit/main/install.sh -o install.sh && bash install.sh
```

## 1. 基础依赖与软件源免交互安装

更新索引的核心命令保持为：

```bash
DEBIAN_FRONTEND=noninteractive pkg update -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
```

安装以下全部包：

```text
openssh mosh tmux termux-tools termux-api nodejs-lts android-tools
git python build-essential curl tar proot ca-certificates
```

`android-tools` 提供本地 ADB。`termux-api` 是命令行包，调用 Android API 还需要匹配安装来源的 Termux:API 应用和相应权限，脚本不会自动安装 Android 应用。安装 proot 不等于已经安装 Linux 发行版，安装 Node.js 不等于已安装或登录 AI 工具。

### 软件源与防卡死补丁

- 不对 `/etc/apt/sources.list` 使用 sed，也不假定新版 Termux 使用该旧路径；保留 Termux 当前软件源布局，由 `pkg` 管理。源不可用时手动运行 `termux-change-repo` 选择源后重试。
- `DEBIAN_FRONTEND=noninteractive`、`-y` 和两个 Dpkg 选项用于免交互并保留已有配置；所有子命令从 `/dev/null` 读输入，防止吞掉 `curl | bash` 的后续脚本。
- 更新与安装每步默认最多 1200 秒，超时后先终止，15 秒后仍未结束则强制终止；APT 单次网络等待 30 秒、重试 2 次、包锁最多等待 60 秒，不无限等待或无限重试。
- 依赖 Termux 自带 coreutils 的 `timeout`；缺失会明确退出。`set -Eeuo pipefail` 保证安装失败不会继续写配置或报成功。
- 无线网络较慢时可延长每步上限：`TERMUX_KIT_TIMEOUT=2400 bash install.sh`。参数必须为正整数秒。
- 不自动执行全量升级，也不删除包管理器锁。若安装被超时中止，先确认没有其他安装进程，再按包管理器提示处理，例如 `dpkg --configure -a`，之后重跑。

## 2. 双排 9 列定制扩展键盘

脚本将以下配置写入 `~/.termux/termux.properties`，原样保留全部按键和宏：

```ini
bell-character = ignore
extra-keys = [['ESC','/',{macro:'ALT p',display:'MDL'},{key:'PASTE',display:'PST'},{macro:'CTRL b p',display:'PRV'},'UP',{macro:'CTRL b n',display:'NXT'},{key:'PGUP',display:'PGU'},{key:'BKSP',display:'DEL'}],['TAB',{key:'CTRL',display:'CTL'},'ALT',{macro:'SHIFT TAB',display:'S-T'},'LEFT','DOWN','RIGHT',{key:'PGDN',display:'PGD'},{key:'ENTER',display:'[ENT]'}]]
```

| 行 | 9 个按键，从左至右 |
| --- | --- |
| 第一排 | ESC、/、MDL、PST、PRV、UP、NXT、PGU、DEL |
| 第二排 | TAB、CTL、ALT、S-T、LEFT、DOWN、RIGHT、PGD、[ENT] |

`MDL` 发送 Alt+p，`PST` 粘贴，`PRV/NXT` 发送 Ctrl+b 再 p/n，适用于默认前缀为 Ctrl+b 的 tmux 上一窗口/下一窗口；`S-T` 发送 Shift+Tab。`DEL` 实际发送 BKSP（退格），不是向前删除。MDL 是否触发模型切换取决于前台程序是否绑定 Alt+p。

写入后执行 `termux-reload-settings`，15 秒超时后终止，5 秒后仍未结束则强制终止；若失败则退出并提示重开 Termux 验证，不把重载失败当作成功。

## 重复执行与恢复

安装可重跑；脚本仅替换 `bell-character` 和 `extra-keys` 两项，并清理它们的旧续行，保留其他设置及注释。内容变化时先生成 `termux.properties.bak.<时间戳>`，再原子替换；相同内容不新增备份。遇到配置软链会停止，避免覆盖不明目标。

恢复时选择实际备份文件复制回去，然后重载：

```bash
ls -t ~/.termux/termux.properties.bak.*
cp ~/.termux/termux.properties.bak.<时间戳> ~/.termux/termux.properties
termux-reload-settings
```

## 验证边界

仓库提供 `python3 tests/test_install.py` 沙盒回归：检查重复运行、旧续行保留、依赖列表、安装失败中止及重载失败。包安装和重载使用替身，不在开发 Mac 安装 Termux 包。Android 真机安装、键盘显示和按键宏仍待验，不将脚本静态检查或替身回归描述为设备验证。

## 官方参考

- [Termux pkg 实现](https://github.com/termux/termux-tools/blob/master/scripts/pkg.in)
- [Termux 软件包管理](https://github.com/termux/termux-packages/wiki/Package-Management)
- [Termux 属性及配置路径](https://github.com/termux/termux-app/blob/master/termux-shared/src/main/java/com/termux/shared/termux/TermuxConstants.java)
- [Termux 扩展键盘实现](https://github.com/termux/termux-app/blob/master/termux-shared/src/main/java/com/termux/shared/termux/extrakeys/ExtraKeysInfo.java)
