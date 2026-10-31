"""WinPatchKit GUI（Flet）。

本包是"展示层"：只依赖 core（引擎）与 app（数据目录/设置/导入），
不反向修改它们。GUI 是薄壳——所有 patch/导入/设置能力复用现有接口。

结构（解耦 + 每种页面/控件独立成文件）：
  entry.py         Flet App 入口（装配导航栏 + 页面切换 + 共享控件）
  services.py      GUI↔引擎桥接层：把同步调用包装成结构化结果（页面唯一数据源）
  theme.py         主题 / 配色 / 状态文案常量
  widgets/         复用控件（每种一个文件）
  pages/           页面（每种一个文件）
"""
