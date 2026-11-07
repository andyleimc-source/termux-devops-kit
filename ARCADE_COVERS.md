# 中文街机列表：补图、选图与离线显示

方案沿用 RetroArch 自带的缩略图机制，图片来自 [Libretro 社区 FBNeo 图片库](https://github.com/libretro-thumbnails/FBNeo_-_Arcade_Games)。中文游戏名、ROM 路径、核心和已调好的按键保持原样。

图片先下载到本地，再安装到掌机；浏览列表时不依赖联网。同步工具使用 Python 3 标准库，安装到 Android 设备时还需要 adb。

## 先解决“选到好图”，再解决“图片显示”

社区的 Named_Boxarts 目录里并非每张图都适合掌机。它可能收录街机宣传单、控制说明、机柜照片和密集小字页。文件名与游戏完全匹配，只能证明对应关系，不能证明作为小图好看、好认。

本次 32 款最终选择：12 张清晰角色/宣传主视觉、16 张可读标题画面、4 张实机画面，逐张记录选择理由。

本次选图准则：

- 能在列表缩略图尺寸下认出游戏，大标题、主要角色或典型场景优先。
- 剔除说明书、光盘页、控制面板说明、机柜照片和密集宣传文字。
- 好的宣传主视觉可以保留；宣传图不合适时，用该版本实际标题画面或游戏画面。
- 逐张看候选图，再在真实掌机的中文收藏和分类列表看效果。
- 图片来源、原始种类、选择理由、对应版本和校验值都放入映射清单。

“宣传图目录里有文件”和“图片校验通过”都不能替代视觉筛选。

## 中文名为什么匹配不上自动封面

默认下载器通常围绕上游数据库名与游戏名匹配。自建列表显示“恐龙快打”，上游图片却叫英文的 Cadillacs and Dinosaurs 加区域/版本，中文条目就可能找不到图片。

保留中文名的做法是：

1. 用 ROM 短名及核心运行日志中的准确版本，找到上游同一游戏的图片。
2. 把已选图片按本地列表 label 命名。
3. 放进 db_name 所指向的缩略图子目录。
4. 中文收藏和各分类共用同一份图片。

本次所有条目的 db_name 都是“经典街机.lpl”，因此图片目录为：

    RetroArch/thumbnails/经典街机/Named_Boxarts/恐龙快打.png
    RetroArch/thumbnails/经典街机/Named_Boxarts/拳皇97.png
    RetroArch/thumbnails/经典街机/Named_Boxarts/打击者1945 II.png

这里只是把所选图片放到当前界面读取的卡片位置。图片原始来源可以是 Named_Boxarts、Named_Titles 或 Named_Snaps，清单会如实记录，不能把标题画面冒称为实体盒装封面。

不同的 db_name、游戏 label 或缩略图根目录，需要同步调整本地清单或目录。ASCII 的 &、*、/、冒号、反引号、双引号、尖括号、问号、反斜线和竖线按 RetroArch 规则换成下划线；中文全角冒号保留。

## 使用同步工具

本仓库提供：

- [32 款映射清单](configs/arcade-cover-manifest.json)：游戏版本、中文名、图片来源和 SHA256。
- [同步工具](scripts/sync-covers.py)：下载、复用缓存、校验、可选推送设备并回读校验。
- [行为测试](tests/test_sync_covers.py)：错误游戏名、损坏图片、缓存、路径和 adb 空格处理。

先在仓库根目录运行，复制清单到临时位置；工具会补全或更新其中的本地相对路径：

    mkdir -p "$HOME/tmp/retroarch-covers"
    cp configs/arcade-cover-manifest.json "$HOME/tmp/retroarch-covers/manifest.json"
    python3 scripts/sync-covers.py \
      --manifest "$HOME/tmp/retroarch-covers/manifest.json" \
      --output "$HOME/tmp/retroarch-covers/images" \
      --only dino

先检查下载的这张图片。确认目标掌机：

    adb devices -l

把下面占位符换成这台掌机实际在线的 adb 标识。USB 调试使用序列号，无线 adb 使用设备列表里的地址与端口：

    export ANDROID_SERIAL='在这里填掌机的adb标识'
    adb get-state
    adb shell getprop ro.product.model

先停止 RetroArch，避免缩略图旧缓存影响观察，然后只推一张验证：

    adb shell am force-stop com.retroarch.aarch64
    python3 scripts/sync-covers.py \
      --manifest "$HOME/tmp/retroarch-covers/manifest.json" \
      --output "$HOME/tmp/retroarch-covers/images" \
      --serial "$ANDROID_SERIAL" \
      --only dino

打开 RetroArch，在中文收藏里检查“恐龙快打”。路径和效果正确后，去掉 --only 执行整批：

    adb shell am force-stop com.retroarch.aarch64
    python3 scripts/sync-covers.py \
      --manifest "$HOME/tmp/retroarch-covers/manifest.json" \
      --output "$HOME/tmp/retroarch-covers/images" \
      --serial "$ANDROID_SERIAL"

默认远端根目录为 /sdcard/RetroArch/thumbnails；如果配置里 thumbnails_directory 指向别处，用 --remote-root 指定对应目录。

工具会复用已通过校验的本地缓存；目标位置存在同名图时，推送会覆盖它。已有自定义图片先保存备份。清单固定了上游提交与图片哈希，上游内容变动不会被静默当作同一图片接受。

工具不会改游戏列表、模拟器配置或手柄设置。它也不会猜测新增游戏该用哪张图。添加新游戏时，先人工核实版本与图片，再扩展清单。

## 查看当前设置与排查

    adb shell 'grep -E "thumbnails_directory|menu_thumbnails|menu_driver" /sdcard/Android/data/com.retroarch.aarch64/files/retroarch.cfg'

本次实测：

    menu_driver = "glui"
    menu_thumbnails = "3"
    thumbnails_directory = "/storage/emulated/0/RetroArch/thumbnails"

这是 RetroArch 1.22.2 的 MaterialUI 配置。本次原设置已支持封面，最终无需修改配置。其他版本或菜单驱动，优先在“用户界面 / 外观”和列表管理里选择相应缩略图类型，不要照搬数字。

不显示时依次查：

1. 图片已下载且格式是 PNG，文件传输完成。
2. db_name 对应的目录名与实际一致。
3. 图片名与中文 label 一致，特殊字符转义正确。
4. 缩略图类型与 Named_Boxarts 等目录对应。
5. 退出重开 RetroArch 清除旧缓存。
6. 收藏与分类各看一款，避免只在某个列表匹配成功。

“打击者1945 II”等名称包含空格；adb shell 的远端路径必须正确引用。同步工具已处理该问题，并逐张回读远端 SHA256。

## 回退与验证边界

回退前先退出 RetroArch，只删除或还原本次清单列出的那 32 张图片，再重开应用。不要整目录删除 thumbnails，也不要为回退封面去重置手柄或删除游戏。

本次验证同时包括图片对应关系、设备文件哈希与真实列表显示。收藏和合金弹头、格斗、飞机分类都做了实际检查；按键与焦点设置保持不变。

官方命名及目录规则见 [Libretro 缩略图文档](https://docs.libretro.com/guides/roms-playlists-thumbnails/)，其他安装和按键方法见 [安卓街机指南](ANDROID_ARCADE.md)。
