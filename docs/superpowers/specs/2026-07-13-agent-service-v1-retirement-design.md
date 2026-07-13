# Agent Service v1 退役设计

## 背景

当前默认运行入口只启动 `agent_service_v2`。实际前端、Backend 运行日志与数据库任务记录表明，旧 `agent_service` 已不承接产品流量；Backend 剩余的 v1 画像对话和学习路径刷新接口没有前端入口，也没有任务记录。

## 目标

- `agent_service_v2` 成为唯一 Agent Service 运行时。
- 删除 Git 跟踪的 `agent_service` v1 源码、测试和模块文档。
- 删除无实际入口的画像对话补充和学习路径刷新链路。
- 保留学习路径读取、节点资源、画像规则刷新和全部 v2 能力。
- 对齐仍有效的协作说明和 Agent API 文档。

## 功能取舍

| v1 能力 | 当前承接方式 | 处理 |
|---|---|---|
| tutoring | v2 Workbench | 删除 v1 |
| knowledge / resources / questions | v2 Knowledge | 删除 v1 |
| evaluation / assessment | v2 Evaluation | 删除 v1 |
| profile generate | Backend 规则刷新 | 删除 v1 |
| profile dialogue update | 无 UI 入口 | 删除 Backend 死接口 |
| learning path generate | Backend 实时 KG 路径 | 删除 Backend 刷新死接口 |
| memory compress | v2 Workbench/Mem0 | 删除 v1 |
| health / probes | 非产品能力 | 删除旧探针并更新说明 |

## 架构选择

不引入新设计模式或兼容适配层。旧服务没有运行责任，继续增加 v1→v2 代理只会延长双轨状态。保留现有 `Frontend -> Backend -> agent_service_v2` HTTP 边界。

## 数据与环境边界

- 不修改或删除任何 `.env`。
- 不删除本地 `knowledge_base`、`qdrant_data`、`.venv` 或用户数据。
- 不删除 MySQL 中的历史表或执行破坏性迁移。
- 仅删除 Git 跟踪的 v1 源码；被忽略的本地目录由用户另行处理。

实际核查确认：旧目录包含一个约 19MB、未登记到当前课程资料库的 PDF，以及 264KB 本地 Qdrant 数据。两者均不迁入 v2：PDF 保留待用户通过 Backend 上传链路按需登记，向量检索继续使用独立 Qdrant 服务。v2 配置只读取自身 `.env`，不再依赖旧目录环境文件。

## 契约变化

- Client API 删除 `POST /api/v1/profile/dialogue-update`。
- Client API 删除 `POST /api/v1/learning-path/refresh`。
- 保留 `GET /api/v1/learning-path` 和节点资源接口。
- Agent API 删除全部 `/agent/v1/*`，只保留 `/agent/v2/*`。

## 验收

- Backend 路由表不包含两个退役 Client API。
- 全仓运行代码不引用 `/agent/v1/*` 或导入 `agent_service`。
- 前端 lint/build、Backend 相关测试、Agent Service v2 全量测试通过。
- `start_all.sh` 继续只启动 v2。
