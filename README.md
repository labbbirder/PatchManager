# PatchManager
多patch管理工具，多渠道、多Mod场景下开发维护的利器。

使用link管理patch模块，不需要手动拷贝，自动同步增删改。
![gif](docs/qgetd-7q4ru.gif)

切换当前的patch：

```shell
python patch_manager.py apply patch1 patch2
```

## Scenarios
以下场景有用：
* 当你的项目需要发布到几十个渠道
* 当你的项目有众多Mod
* etc

应用场景的本质是多模块的管理。对于模块耦合度比较低、单个模块规模较大时，可以使用monorepo的方式进行管理；但是如果模块并不容易解耦、且模块较小，monorepo或多仓库的方式会相对笨重。换言之，并不是所有的系统都适合解耦为"Module"，很多时候最多是个"Patch"，这也是PatchManager命名的原由。

> 如：Unity项目对目录安放位置有要求，可能会区分AOT、HotFix、Editor、Plugins等。

因此，此仓库的意义在于解决了多模块管理的“最后一公里"问题。

> 值得一提的是，patch manager管理的模块在迭代到一定成熟度后，也可以近乎无成本转换为monorepo。

## Under the Hood

切换时，会删除和创建相关的文件和目录。但是完全不用担心丢失work copy的问题。

自动创建内容时，会检测并满足以下条件：
* 目标路径不在patch下

自动删除内容时，会检测并满足以下条件：
* 目标是个link
* link指向patch下内容

patch之间可以通过dependencies设置依赖关系，自动循环依赖检测

如，可能有以下patch：
* webgl-common #webgl相关的功能
* webgl-mobile #webgl手机端功能
* webgl-desktop #webgl桌面端功能
* wx-mini: webgl-common webgl-mobile #微信小游戏模块，依赖webgl-common webgl-mobile
* qq-hall: webgl-common webgl-desktop #QQ游戏大厅模块，依赖webgl-common webgl-desktop

应用wx-mini时，会按顺序应用：依赖webgl-common, webgl-mobile, wx-mini

## Usage

```shell
bbbirder> python patch_manager.py -h
usage: patch_manager.py [-h] {init,list,apply} ...

patch 工具

positional arguments:
  {init,list,apply}  commands
    init             init a sync project
    list             list all patches
    apply            apply patches

options:
  -h, --help         show this help message and exit
```

## Configure

init 之后，会在项目根目录下出现`sync-config.json`文件

```
{
  "home": "GamePatches", // 存放所有patch的路径
  "mappings": // 目录或文件的映射
  {
    "Editor": "Assets/Editor/PatchTools", // patch内的Editor会在应用后映射到Assets/Editor/PatchTools，多个patch只有最后一个生效
    "AOT": "Assets/{name}-AOT", // {name}会自动替换为patch名称，多个patch同时生效
    "HotFix": "Assets/HotFix/PatchLogic" // 见上
  }
}
```

mappings下的文件会映射到项目目录内，项目内的相关路径需要先在版本控制软件内Ingore。直接在工程路径下增删改，会自动同步到Patch路径下。
