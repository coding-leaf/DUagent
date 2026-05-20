# AGENTS.md

## Workflow
- 修改代码前需要分析并指明问题
- 先解释修改方案,再开始修改
- 只能小范围重构,以minimal diff为准则
- 一次性不可修改过多文件
## Engineering Style
- 不要过度工程化
- 保持代码简洁
- 避免过于抽象的概念提取
- 除非能简化代码编写,否则减少复杂设计模式的引入
- 保持当前项目结构
## Code Changes
- 修改前说明分析可能影响哪些文件和功能
- 保持命名风格
- 不可静默修改,每次修改必须被允许

## git
- 避免在例如master等主分支开发,当前项目为agent/ 分支
- 分支修改时,允许git存档
## 背景补充
- 本项目基于python+FastAPI开发,agentscope为ai框架
- 通过uv进行包管理
- 开发环境为wsl+python3(既,通过python3允许)
- 项目实际来源https://www.cnsoftbei.com/content-3-1286-1.html
