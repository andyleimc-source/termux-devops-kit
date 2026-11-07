# Retroid Pocket Duo Lite：街机安装与实体按键排查

2026-11-07 实机记录：在 Android 15 的 Retroid Pocket Duo Lite（6GB / 128GB，QCS6125 系列 / Adreno 610）上使用 RetroArch AArch64 1.22.2_GIT 与 FinalBurn Neo，建立 32 款游戏的中文收藏、分类和离线图片，并修复双屏焦点与十字键映射。

游戏文件需自行准备。本仓库提供方法、配置片段和图片来源映射。原有 Steam Deck / Linux 的安装路径和输入系统不同，不直接套用这里的 Android 命令。

封面及选图方法见 [中文列表补图指南](ARCADE_COVERS.md)。

## 1. 连接并确认目标设备

电脑安装 Android SDK Platform Tools，掌机打开开发者选项和 USB 调试，允许电脑连接：

    adb devices -l

把占位符换成目标掌机的实际 adb 标识，多设备时不要省略目标：

    export ANDROID_SERIAL='在这里填掌机adb标识'
    adb get-state
    adb shell getprop ro.product.model
    adb shell getprop ro.build.version.release
    adb shell getprop ro.soc.model
    adb shell head -5 /proc/meminfo
    adb shell df -h /sdcard

USB 使用序列号，无线 adb 使用设备列表中的地址和端口。不要把一台设备的序列号写死进可复用脚本。

## 2. 安装模拟器与核心

从 [RetroArch 官方下载页](https://www.retroarch.com/platforms.html) 获取 Android 64 位 APK。本次固定版本：

    curl -fL --retry 2 --connect-timeout 15 --max-time 300 \
      -o RetroArch_aarch64.apk \
      https://buildbot.libretro.com/stable/1.22.2/android/RetroArch_aarch64.apk
    adb install RetroArch_aarch64.apk
    adb shell am start -n \
      com.retroarch.aarch64/com.retroarch.browser.mainmenu.MainMenuActivity

首次打开，按提示授予游戏目录的存储访问权限。至少打开一次，让应用创建配置文件。

在“加载核心 → 下载核心”安装 Arcade (FinalBurn Neo)。也可以手动安装本次使用的核心：

    curl -fL --retry 2 --connect-timeout 15 --max-time 300 \
      -o fbneo_libretro_android.so.zip \
      https://buildbot.libretro.com/nightly/android/latest/arm64-v8a/fbneo_libretro_android.so.zip
    unzip fbneo_libretro_android.so.zip
    adb shell mkdir -p /sdcard/RetroArch/downloads
    adb push fbneo_libretro_android.so /sdcard/RetroArch/downloads/

接着在“加载核心 → 安装或还原核心”选择这个 .so 文件，让应用复制到自己的核心目录。普通 adb shell 不能直接写 /data/data/com.retroarch.aarch64/cores。

nightly 地址会更新，复现时记录实际核心版本及校验值。本次日志显示 v1.0.0.03 261105 GITd15071a。

## 3. 游戏文件与完整性

    adb shell mkdir -p /sdcard/Games/Arcade
    adb push dino.zip /sdcard/Games/Arcade/

街机 ZIP 通常直接加载，不解压。优先使用与当前 FBNeo 匹配的完整非合并包（full non-merged），并按核心日志检查父集、BIOS 和 ROM 校验。

文件名相同不代表包内内容相同。本次 Neo Geo 游戏 ZIP 已包含启动所需的系统文件，实测可以直接运行，没有另外安装独立 neogeo.zip；其他来源的包不能据此推定也齐全。

先做压缩文件 CRC 检查：

    python3 - <<'PY'
    import zipfile
    with zipfile.ZipFile("dino.zip") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise SystemExit("ZIP CRC 检查失败: " + bad)
        print("ZIP CRC 检查通过")
    PY

压缩包检查通过以后，仍要在掌机上检查核心初始化、游戏画面和实际操作。

## 4. 备份与修改主配置

本次包名为 com.retroarch.aarch64，配置在：

    /sdcard/Android/data/com.retroarch.aarch64/files/retroarch.cfg

先退出应用并拉回备份：

    adb shell am force-stop com.retroarch.aarch64
    adb pull /sdcard/Android/data/com.retroarch.aarch64/files/retroarch.cfg \
      retroarch-before.cfg
    cp retroarch-before.cfg retroarch-edited.cfg

用文本编辑器按项修改本地文件，完成后写回：

    adb push retroarch-edited.cfg \
      /sdcard/Android/data/com.retroarch.aarch64/files/retroarch.cfg

不要在应用运行时覆盖配置，否则退出保存可能把旧设置写回来。[配置片段](configs/retroid-duo-lite-retroarch.cfg) 只用于合并对应字段，不能替换整个主配置。

恢复时退出应用，再把 retroarch-before.cfg 推回同一路径。

## 5. 游戏在上屏，手柄却控制下屏

本次观察到：上屏游戏正常显示，A/B、方向键却操作下屏启动器。窗口焦点与厂商手柄焦点锁是两层设置，仅把游戏拉到前台不足以修复。

    adb shell settings get system screen_focus_lock
    adb shell dumpsys input
    adb shell dumpsys window

本机厂商控制程序的资源和逻辑确认：

| 数值 | 含义 |
| --- | --- |
| 0 | 自动 / 随触摸切换 |
| 1 | 手柄锁定上屏 |
| 2 | 手柄锁定下屏 |

先记录原值。本次原值 2，改为 1 后实体手柄进入上屏游戏：

    adb shell settings put system screen_focus_lock 1
    adb shell settings get system screen_focus_lock

也可以通过厂商双屏控制中心选择“上屏”。恢复时写回记录的原值。该设置也影响其他应用的手柄目标，想在下屏玩时需相应切换。

这些取值只对经过检查的本机厂商系统成立，不是通用 Android 标准。

## 6. A/B 有反应，左侧十字键却不能移动

### 先看硬件发什么信号

    adb shell getevent -lp
    adb shell dumpsys input

找到内置手柄的事件节点再读取。本次为 /dev/input/event8，换设备或重启后可能变化：

    adb shell -tt getevent -lt /dev/input/event8

实按十字键。本机发送：

    EV_ABS  ABS_HAT0X   ffffffff   # 左，-1
    EV_ABS  ABS_HAT0X   00000001   # 右，+1
    EV_ABS  ABS_HAT0Y   ffffffff   # 上，-1
    EV_ABS  ABS_HAT0Y   00000001   # 下，+1

松开归零。-tt 有助于实时观察输出，避免管道缓冲造成没有事件的误判。

### 本次根因与修复

旧配置把方向按钮手写为 19/20/21/22，并指定 +/-4、+/-5 方向轴，覆盖了原本正确的方向帽（HAT）映射。

改为：

    input_player1_up_btn = "h0up"
    input_player1_down_btn = "h0down"
    input_player1_left_btn = "h0left"
    input_player1_right_btn = "h0right"
    input_player1_up_axis = "nul"
    input_player1_down_axis = "nul"
    input_player1_left_axis = "nul"
    input_player1_right_axis = "nul"

h0 是第一个方向帽。本次只修这八个方向字段，保留其他按键。左摇杆作为方向输入的原设置也保留：

    input_player1_analog_dpad_mode = "1"

对应驱动源码见 [RetroArch 1.22.2 Android joypad](https://github.com/libretro/RetroArch/blob/v1.22.2/input/drivers_joypad/android_joypad.c)：HAT 和普通按键走不同状态路径。此前用 BTN_DPAD 模拟方向键的测试没有覆盖实体 ABS_HAT 路径，这是漏测原因。

## 7. 自动配置与一号玩家

本机内置控制器名为 Xbox Wireless Controller，vendor/product 为 0x2022 / 0x3002，与上游 Retroid Xbox 配置对应：

    curl -fL --connect-timeout 15 --max-time 60 \
      -o Retroid-Pocket.cfg \
      https://raw.githubusercontent.com/libretro/retroarch-joypad-autoconfig/master/android/Retroid_Pocket_5_Xbox.cfg
    adb shell mkdir -p /sdcard/RetroArch/autoconfig/android
    adb push Retroid-Pocket.cfg /sdcard/RetroArch/autoconfig/android/

主配置按本机情况合并：

    input_driver = "android"
    input_joypad_driver = "android"
    joypad_autoconfig_dir = "/storage/emulated/0/RetroArch/autoconfig"
    input_player1_reserved_device = "Xbox Wireless Controller"
    input_player1_device_reservation_type = "2"
    input_player1_joypad_index = "0"

远程注入的 Virtual 设备可能先占第一个端口，预留真实手柄可避免操作变成 2P。重开应用后按一次实体键，在提示或日志确认它处于端口 1。

其他控制器先核对名称、vendor/product 和真实信号，不能套用设备身份。

## 8. 中文收藏与返回菜单

本次使用这些目录和启动选项：

    content_favorites_path = "/storage/emulated/0/RetroArch/playlists/builtin/content_favorites.lpl"
    playlist_directory = "/storage/emulated/0/RetroArch/playlists"
    menu_startup_page = "2"
    input_menu_toggle_gamepad_combo = "4"

RetroArch 1.22.2 中，启动页 2 为收藏，菜单组合 4 为 Start+Select。组合 3 是 L1+R1+Start+Select，不能混用。

收藏为 UTF-8 JSON，最小条目示例：

    {
      "version": "1.5",
      "items": [
        {
          "path": "/storage/emulated/0/Games/Arcade/dino.zip",
          "label": "恐龙快打",
          "core_path": "/data/data/com.retroarch.aarch64/cores/fbneo_libretro_android.so",
          "core_name": "FinalBurn Neo",
          "crc32": "00000000|crc",
          "db_name": "经典街机.lpl"
        }
      ]
    }

crc32 示例占位不代表游戏通过校验，以核心日志为准。备份已有收藏，在本地合并新条目后再推送，避免覆盖用户已有条目：

    adb shell am force-stop com.retroarch.aarch64
    adb shell mkdir -p /sdcard/RetroArch/playlists/builtin
    adb push content_favorites.lpl \
      /sdcard/RetroArch/playlists/builtin/content_favorites.lpl

分类文件用同一 JSON 结构，另存 .lpl 到 playlist_directory。本次统一 db_name，供中文收藏与分类共用图片，详情见 [补图指南](ARCADE_COVERS.md)。

打开 RetroArch → 收藏 → 中文游戏名 → 运行。Select 投币，Start 开始，Start+Select 打开快捷菜单，关闭游戏后返回列表换游戏。闯关常用 A/B，格斗还需 X/Y 与 L/R，具体看游戏映射。

## 9. 调试与有意义的验收

### 日志

临时启用：

    log_verbosity = "true"
    log_to_file = "true"
    log_to_file_timestamp = "false"
    log_dir = "/storage/emulated/0/RetroArch/logs"

    adb pull /sdcard/RetroArch/logs/retroarch.log

关注核心版本、ROM 缺失/CRC、初始化和手柄端口。部分日志会缓冲，文件没有新增行不能直接证明没有输入。

### 指定双屏截图

    adb shell dumpsys SurfaceFlinger --display-id
    adb shell screencap -d '<实际物理显示ID>' -p /sdcard/arcade-screen.png
    adb pull /sdcard/arcade-screen.png

物理截图 ID 与 am start --display 的逻辑编号不同，不指定时可能拍到另一块屏幕。

### 同一 HAT 信号对比修复前后

先确认事件节点和权限。以下在本机向右保持 0.8 秒，然后归零：

    adb shell 'sendevent /dev/input/event8 3 16 1; sendevent /dev/input/event8 0 0 0; sleep 0.8; sendevent /dev/input/event8 3 16 0; sendevent /dev/input/event8 0 0 0'

左右是 ABS_HAT0X（代码16），上下是 ABS_HAT0Y（代码17）。测试后恢复0并发SYN_REPORT，避免方向一直按住。有些设备拒绝写节点，应改用实按采集，不把合成输入当作真人验收。

### 完成标准

- 重开后从中文收藏真实点开游戏。
- 等自检和过场结束，投币开始，进入1P选人或实际关卡。
- 分别验证十字键四方向、左摇杆、攻击/跳跃、投币/开始。
- 打开快捷菜单、关闭游戏、回列表再换游戏。
- 封面既要文件对应和哈希正确，也要实际看小图是否可辨认。

演示画面自己移动不算按键通过；过场、起飞、死亡与续关中人物不动，也不能算方向键失败。自动读档还可能把临近超时的测试状态恢复出来，处理前备份对应游戏状态，勿批量删除用户存档。

## 10. 实测范围

32 款完成核心初始化及缺失文件检查，多个系列代表已投币选人或首关；辛普森一家、铁钩船长、忍者神龟初代和超级街霸2X保留为正常片头启动记录，不冒称完整首关验证。

十字键修复在恐龙快打完成旧配置不响应的复现、修复后四方向、左摇杆和跳跃回归。雷电左/上/下已单独验证，右方向复测遇到过场和续关，未单独计通过。使用者随后实按确认可以使用。

这不是通关所有游戏或覆盖所有 Android 型号的声明。

## 官方参考

- [Retroid Pocket Duo Lite 规格](https://www.goretroid.com/collections/frontpage/products/retroid-pocket-duo-lite-handheld)
- [RetroArch Android 安装](https://docs.libretro.com/guides/install-android/)
- [FinalBurn Neo 核心](https://docs.libretro.com/library/fbneo/)
- [菜单组合枚举](https://github.com/libretro/RetroArch/blob/v1.22.2/input/input_defines.h)
- [启动页枚举](https://github.com/libretro/RetroArch/blob/v1.22.2/menu/menu_defines.h)
- [上游手柄配置](https://github.com/libretro/retroarch-joypad-autoconfig/blob/master/android/Retroid_Pocket_5_Xbox.cfg)
