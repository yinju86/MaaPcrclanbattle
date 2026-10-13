<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <img src="assets/resource/kyouka.ico" width="128" alt="MaaPcrclanbattle">
</p>

<div align="center">

# MaaPcrclanbattle

**公主连结国服 · 会战 SET / UB 轴自动脚本生成器**

基于 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 图像识别驱动，图形界面 + 命令行双入口

</div>

---

## 这是什么

把会战轴（谁在什么时间点开哪个 SET / UB）录进工具，生成一份 MaaFramework 能直接执行的脚本，
再由 MFAWPF 自动帮你把关卡里的 SET 开关和 UB 点出来。

- **纯图像识别**，不读内存、不修改游戏 —— **但是怕就别用**
- **仅支持 1280\*720 分辨率**，模拟器/设备请按这个设置
- 交流 QQ 群：**532774716**

## 三种模式

菜单「模式切换」里三选一，互斥：

| 模式 | 干什么 | 输入 | 产出的分享码 |
|---|---|---|---|
| **开关SET模式** | 按时间点开关角色的 SET / auto | 表格，一行一个时间点 | `轴名:base62码!延时表` |
| **单次UB模式** | 按顺序点 UB、等倒计时、卡帧目押 | 一段操作流水文本 | `轴名#指令串#五个角色名` |
| **AI识别模式** | 直接贴轴图，自动识别成上面两种 | 一张轴图（截图/图片文件） | 同上，自动判断类型 |

三种模式产出的脚本格式一致，都是写进 `resource/pipeline/*.json` 并注册到 `interface.json`。

## 快速开始

### [单UB视频演示](https://www.bilibili.com/video/BV1FUgXzoE7M/)
### [开关set视频演示](https://www.bilibili.com/video/BV1uiyMY4EnJ/)
### [最简化视频演示](https://www.bilibili.com/video/BV1k1QUBqEV8/)

### 0. 下载最新 [Release 包](https://github.com/yinju86/MaaPcrclanbattle/releases)

### 1. 运行 generator.exe，把轴录进去

轴可以手打，也可以直接粘一条分享码（见下面的「分享码」一节），
还可以在 AI 识别模式里贴一张轴图让模型帮你填。

### 2. 一键导入分享码（可选）

网上现成的轴大多以分享码形式流传，详见 [分享地址](https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz)。
把码粘进「分享码」框 → 点「读取分享」，表格/文本区会自动还原，脚本也会一并生成。

### 3. 进预备挑战界面，需要提前自行选人

先选好队伍进模拟战再退出，让游戏停在预备挑战界面。**本工具不负责自动选人。**

### 4. 运行 MFAWPF.exe，执行脚本

在 MFAWPF 的任务列表里选刚生成的脚本名即可。

## 使用方法详解

### 开关 SET 模式（表格）

表格五列：**时间 / ?号位UB后 / 状态 / 操作 / 延时(秒)**

- **时间**：游戏里倒计时读到的秒数，按 3 位填，例如 `1:11` 填 `111`、`56` 填 `056`；
  第一行填**初始状态**
- **?号位UB后**：这一行是谁的 UB 后面（时点）。写「普攻后 / BOSS」这类无角色触发的行填 `0`，
  卡帧行选「卡帧」
- **状态**：1~5 号位的开关勾选框，外加一个 auto 勾选框
- **操作**：行尾的添加/删除按钮
- **延时(秒)**：这一行之前额外等多久

右上「余刀剩余时间」默认 130。补刀（半路进刀）时填当前的剩余秒数，
工具会把轴上的时间点整体平移对齐。

### 单次 UB 模式（文本）

一行一步，按顺序写操作，支持这些写法（一行里可以连写多个）：

| 写法 | 含义 |
|---|---|
| `角色名` | 点该角色的 UB |
| `角色名AUTO` / `角色名(auto)` | 开 auto 等它自动 UB，完了自动关 |
| `卡帧` / `目押` / `押` / `唱名` / `速压破甲` | 卡帧，游戏里会提示「自行目压」 |
| `延时N` / `N秒` | 延时 N 秒 |
| `s120` | 等倒计时读到 1:20 |

「使用角色」框里**按 1→5 号位顺序**填 5 个角色名，用空格隔开，必须和轴里出现的名字一一对应。

### AI 识别模式（贴图出码）

菜单「模式切换」→ **AI识别模式**，面板从上到下：

1. **接口地址 / 模型 / API Key** —— 改完 0.6 秒自动存到程序目录的 `ai_config.json`，下次打开自动回填
2. **队伍号位顺序** —— 识别后自动填入，按 1→5 号位、空格分隔
3. **图片区** —— 三种入图方式：把图**拖进来**、按 **Ctrl+V 粘贴截图**（焦点在哪都行）、点「选择图片…」
4. **识别并填充** —— 调模型识别，自动判断是 SET 还是单UB，切到对应模式、填好表格或文本区，
   分享码直接进「分享码」框
5. **识别后自动生成脚本** —— 勾上就连脚本一起生成，不勾只填不写盘

接口按 **OpenAI 兼容格式**发（`{接口地址}/chat/completions`），图片走 `image_url` 的 base64 data URL，
所以只要模型支持读图就能用。

**默认走 DeepSeek**：`https://api.deepseek.com` + `deepseek-flash`（原生多模态，直接吃图片）。
换成官方 OpenAI、通义 `https://dashscope.aliyuncs.com/compatible-mode/v1`、智谱等都行，
填上对应的地址、模型名和 Key 即可。

> ⚠️ 两点务必留意
>
> 1. `ai_config.json` 里存的是**明文 API Key**，已加进 `.gitignore`，别手动塞进仓库。
> 2. **SET 的「时点」完全由「队伍号位顺序」推算**，而轴图里的角色顺序（尤其标题里那个）
>    未必等于工具内的号位顺序。识别完请核对一遍这一栏，改了会自动重算时点并刷新分享码。

### 分享码

一条码对应一条轴，粘进「分享码」框点「读取分享」即可还原。「一键分享」把当前轴导出成码。

| 类型 | 格式 | 说明 |
|---|---|---|
| 开关SET | `轴名:base62码!延时表` | 每行 6 位十进制（时间3位 + 时点1位 + 6 个开关压成 2 位）转 base62 定长 3 字符，首尾相接；`!` 后面是延时表 `行号-秒数` |
| 单次UB | `轴名#指令串#五个角色名` | 指令串：`1`~`5` 点该号位 UB、`aN` 开 auto、`dN` 延时、`sMSS` 等倒计时、`k` 卡帧 |

轴名前 5 位若是纯数字（例如 `12345E5`），是 **UB 亮条偏移标记**，也可以用菜单「UB偏移 → 偏移量设置」改。

> 分享码本身没有校验和，被截断也可能「解成功」却解出一条错的轴 —— 复制时注意别漏字。

### 其它菜单

| 菜单 | 作用 |
|---|---|
| 脚本管理 → 管理脚本 | 列出/删除已生成的脚本 |
| 帮助 → 使用说明 / 关于 | 打开本文件 / 看版本号 |
| 清空内容 → 清空所有内容 | 清空当前轴 |
| 获取在线内容 → 获取在线轴 | 从在线分享表批量拉取并生成脚本（已存在的会跳过） |
| 识别速度 | 快速 100 / 中速 200 / 慢速 300，机器差就选快速 |
| UB偏移 → 偏移量设置 | 调整 UB 亮条的识别位置 |

每次生成脚本时，当前分享码都会追加写进程序目录的 `自动保存的分享码.txt`。

## 命令行接口（exe 也可以被调用）

打包出来的 `generator.exe` 同时也是个命令行工具，**不带任何参数运行**才是打开图形界面：

```bash
# 把分享码解成可读轴表（自动识别 SET / 单次UB）
generator.exe decode "D4 34067W:wgpsXuql8ezlbxgaMK!"

# 导入分享码，往安装目录的 resource/pipeline 里生成脚本
generator.exe import "D4 34067W:wgpsXuql8ezlbxgaMK!" --out .\install
generator.exe import "码" --out .\install --speed 100      # 快速识别
generator.exe import "码" --no-script                       # 只解码，不写盘

# 调 AI 识别一张轴图（用 ai_config.json 里配好的接口）
generator.exe image 轴图.png --out .\install

# 版本号
generator.exe version
```

| 参数 | 说明 |
|---|---|
| `--out DIR` | 脚本输出目录，默认是程序所在目录（`resource/` 和 `interface.json` 就在那儿） |
| `--speed N` | 识别速度，默认 200（100 快速 / 200 中速 / 300 慢速） |
| `--no-script` | 只解码/只识别，不写脚本 |
| `--report FILE` | 把输出同时写一份到文件 |

几点提示：

- exe 是 GUI 程序，从 **cmd / PowerShell** 调用时会自动附到父控制台，输出能正常看到；
  从别的程序（没有控制台）调用时输出看不到，请加 `--report` 把结果落到文件。
- 退出码：`0` 成功、`1` 运行失败、`2` 输入或环境有问题（错误信息会说明原因）。
- 也可以直接 `python generator.py <子命令>` 用，效果一样。

## 自带的 WorkBuddy skill

仓库里带了一个 [WorkBuddy](https://www.workbuddy.cn) Skill —— **轴图 / 轴表 → 分享码**，
位置在 `.workbuddy/skills/pcr-timeline-to-sharecode/`，Release 包解压后也有（`.workbuddy/skills/` 下）。

它和本工具的分工是：

- **skill** 负责「看图 → 抽出轴 → 算出分享码」，纯标准库脚本 + 反向自检，不依赖本仓库代码
- **generator.exe** 负责「拿到分享码 → 生成 Maa 脚本」，也就是上面命令行接口那部分

把解压出来的目录用 WorkBuddy 打开，它就会自动带上这个 skill；也可以把它复制到
`~/.workbuddy/skills/` 下当作个人 skill 用。

## 目录结构

```
├── generator.py            # 图形界面主程序，也是命令行入口
├── cli.py                  # 命令行接口（decode / import / image / version）
├── pipeline.py             # 生成 MaaFramework pipeline JSON（SET / 单次UB 两种）
├── sharecode.py            # 分享码编解码（base62）
├── install.py              # 打包安装目录（deps / 资源 / skill / README）
├── configure.py            # OCR 模型配置
├── check_resource.py       # 校验 resource 目录能否被 MaaFramework 加载
├── assets/
│   ├── interface.json      # MaaFramework 接口定义
│   ├── requirements.txt    # Python 依赖（PyQt5 / Requests）
│   ├── config/             # MaaFramework 配置
│   └── resource/           # 识别模板图、pipeline 目录、图标
├── .workbuddy/skills/      # 自带的 WorkBuddy skill
└── .github/workflows/      # CI：打包 exe 并出 Release
```

运行时产物（不进仓库）：`resource/pipeline/*.json`、`interface.json`、`ai_config.json`、
`自动保存的分享码.txt`、`install/`。

## 从源码构建

```bash
# 1. 拉代码（带子模块）
git clone --recursive https://github.com/yinju86/MaaPcrclanbattle.git
cd MaaPcrclanbattle

# 2. 装依赖
pip install -r assets/requirements.txt

# 3. 直接运行界面（调试用，不需要打包）
python generator.py

# 4. 打完整安装目录：先把 MaaFramework 和 MFAWPF 下好
#    MaaFramework 解压到 deps/，MFAWPF.exe 放到 MFA/（版本见 .github/workflows/install.yml）
python install.py v4.0.0
cp MFA/MFAWPF.exe install/

# 5. 打包 exe
pip install pyinstaller
pyinstaller --onefile -w --icon=assets/resource/kyouka.ico generator.py
cp dist/generator.exe install/
```

不想本地折腾的话：**打一个 `v*` 标签推上去**，GitHub Actions 会自动跑上述流程并发布 Release
（见 `.github/workflows/install.yml`）。

## 注意事项

1. 尾刀继续借人可能需要自己点确定
2. 最好设置二倍速，不支持四倍速
3. 支持 bossub 后，需要自己设定读秒后延迟时间（现实时间）
4. 虽然设定了最后自己按暂停，但是还是有滑刀风险
5. 使用 MaaPicli 时弹窗报错，应用程序错误：应用程序无法正常启动

![缺少运行库](https://github.com/user-attachments/assets/942df84b-f47d-4bb5-98b5-ab5d44bc7c2a)

一般是电脑缺少某些运行库，请安装一下 [vc_redist](https://aka.ms/vs/17/release/vc_redist.x64.exe)。

## 常见问题

**识别不准 / 卡在某一步**
检查分辨率是不是 1280\*720、游戏是不是二倍速；菜单「识别速度」换成快速重试；
按提示关掉角色的属性动画和多目标动画。

**AI 模式报「模型只返回了思考过程、没有正文」**
这类模型（DeepSeek 默认开思考）把 token 全用在推理上了。工具已经对 DeepSeek 自动关闭思考模式，
换成别的厂商模型时如果遇到，把 `max_tokens` 调大或改用能关思考的模型。

**分享码解出来的轴不对**
多半是复制时截断/漏字。SET 码正文长度必须是 3 的倍数，命令行会提示；界面里请重新复制一遍。

**单次UB 生成出来点错人**
「使用角色」的顺序必须和轴里 1→5 号位一致，名字也要完全一样（含昵称写法）。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 和
**[MFAWPF](https://github.com/SweetSmellFox/MFAWPF)** 强力驱动！
识别用的公共资源来自 [MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets)。

## 开源协议

[MIT](LICENSE)
