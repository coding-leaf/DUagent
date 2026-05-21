# AGENTS.md

## 开发重点
- 我们只负责 agent_service 内部的智能体服务，不负责主业务后端或数据库业务系统。

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
- 修改代码前必须先输出：
  1. 问题分析
  2. 计划修改的文件
  3. 修改方案
  4. 可能影响的功能
- 用户确认后，才允许修改文件。
- 涉及 AgentScope API、用法、配置时，优先参考 AgentScope 官方文档和项目当前已有代码，不凭空编造接口。

## git
- 避免在 master/main/dev 等主分支直接开发。
- 默认在 feat/agent 或用户当前指定的 agent 功能分支开发。
- 修改前如工作区已有未提交内容，允许使用 git stash 保存，但必须先告知用户。

## 背景补充
- 本项目基于python+FastAPI开发,agentscope为ai框架
- `agent_service` 目录内使用 `uv` 管理，根目录不是 `uv` 项目根
- 开发环境为wsl+python3(既,命令行为 python3)
- 项目实际来源https://www.cnsoftbei.com/content-3-1286-1.html
- 拟定项目结构为
    agent_service/
    api/
      v1/
        router.py
        health.py
        tutoring.py
        profile.py
        evaluation.py
    schemas/
      common.py
      tutoring.py
      profile.py
      evaluation.py
    agents/
      tutoring.py
      profile.py
      evaluation.py
    memory/
      qdrant_store.py
      retriever.py
    tools/
      diagram.py
    prompts/
      tutoring.py
      profile.py
    core/
      config.py
      qdrant.py
    main.py

  各层职责建议固定为：

  - api：只处理 FastAPI 路由、参数接收、返回包装、SSE 输出。
  - schemas：只放 Pydantic 实体，严格对齐 OpenAPI。
  - agents：放真正的 Agent/Workflow 编排逻辑。
  - memory：放 Qdrant 读写、检索、事实提取适配。
  - tools：放图解、代码执行、外部工具封装。
  - prompts：放系统提示词和模板。
  - core：放配置和基础设施初始化。
## 开发准则
- 以辅助用户开发为核心，避免主动开发，做好伴学。
- 提供思路、合理的开发建议和合理的开发框架。
- 渐进式开发。
- 实际开发以../docs/20-agent-api目录为准
- 涉及 AgentScope API、用法、配置时，优先参考 AgentScope 官方文档和项目当前已有代码，不凭空编造接口。

## 工具调用
- 如需 jq、tree 等工具，环境不存在但可以安装时，请先请示用户，用户会补充安装。
- 不主动安装系统依赖。

## Testing
- 修改 Python 代码后，优先运行相关测试。
- 如无现有测试，至少运行基本导入检查或启动检查。
- 推荐使用 pytest。
- 可选使用 pytest-cov 查看测试覆盖率。
- 不为了测试而大规模重构项目。

## Commands
- `agent_service` 相关操作先进入项目目录：
  ```bash
  cd agent_service
  ```
- 首次同步开发依赖：
  ```bash
  uv sync --group dev
  ```
- 运行测试优先使用：
  ```bash
  uv run pytest
  ```
- 启动服务：
  ```bash
  uv run python -m agent_service.main
  ```
