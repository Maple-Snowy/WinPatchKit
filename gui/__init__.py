"""WinPatchKit GUI（Flet）。

本包是"展示层"：只依赖 core（引擎）与 app（数据目录/设置/导入），
不反向修改它们。GUI 是薄壳——所有 patch/导入/设置能力复用现有接口。

结构（解耦 + 每个子文件单一职责）：
  app.py           入口：纯导入/转发（run / main），无实现逻辑
  boot.py          进程启动（可选自动关闭 + ft.run）
  bootstrap.py     装配编排（组装各模块到 page）
  window.py        窗口初始化（标题/主题/尺寸）
  theme.py         主题定义（种子色 + build_page_theme）+ 文案常量
  theme_switch.py  明暗主题切换
  appbar.py        顶部 AppBar
  navigation.py    底部导航栏（NAV_ITEMS 数据驱动，可配置）
  titlebar.py      Win32/DWM 标题栏适配（深色 + 精确背景色）
  pages_view.py    页面实例化 + tab 切换控制
  screenshot.py    CI 逐页截图驱动
  services.py      GUI↔引擎桥接层：把同步调用包装成结构化结果（页面唯一数据源）
  widgets/         复用控件（每种一个文件）
  pages/           页面（每种一个文件）
"""
