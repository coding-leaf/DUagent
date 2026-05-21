# Documentation Guide

项目正式文档统一放在根目录 `docs/` 下。当前开发、联调和代码实现应优先参考 `docs/` 下的非归档文档，不要把 `archive/` 中的历史材料当成当前真相源。

## Current Sources of Truth

- `10-client-api/`：Frontend 与 Backend 的正式接口契约
- `20-agent-api/`：Backend 与 Agent Service 的正式内部接口契约
- `30-dev-guide/`：开发导读、分层说明和协作补充
- `90-review/`：接口一致性审查结论，用于确认文档是否已经对齐

## How To Read

如果你在看整体项目：

1. `00-overview/README.md`
2. `10-client-api/API_前端接口规范.md`
3. `20-agent-api/API_Agent内部接口规范.md`
4. `30-dev-guide/Agent-Service_开发导读.md`
5. `90-review/API一致性最终审查.md`

如果你在做前后端联调：

1. `10-client-api/`
2. `20-agent-api/`
3. `90-review/`

如果你在开发 `agent_service`：

1. `20-agent-api/API_Agent内部接口规范.md`
2. `20-agent-api/Agent-Service.openapi.json`
3. `30-dev-guide/Agent-Service_开发导读.md`
4. `90-review/API一致性最终审查.md`

## Directory Map

- `00-overview/`：项目总览、背景介绍和需求原件
- `10-client-api/`：前端与 Backend 的正式 API 文档和 OpenAPI 文件
- `20-agent-api/`：Backend 与 Agent Service 的正式 API 文档和 OpenAPI 文件
- `30-dev-guide/`：开发导读、实现边界、协作说明
- `90-review/`：接口一致性审查和最终结论
- `archive/`：历史归档，仅作留档，不参与当前开发决策

## Archive Policy

- `archive/` 只保留历史版本、分析过程和废弃材料
- 当前字段定义、接口路径、状态码、请求响应结构，一律以非归档目录中的正式文档为准
- 如果归档内容与当前文档冲突，默认视为过期信息
