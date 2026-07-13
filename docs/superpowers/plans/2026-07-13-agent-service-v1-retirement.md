# Agent Service v1 退役实施计划

1. 添加 Backend 路由回归测试，先证明两个退役接口仍存在。
2. 删除画像对话补充 Router、schema、service 和对应测试。
3. 删除学习路径刷新 Router、service、未使用前端方法和对应测试。
4. 删除旧探针及 Backend 启动恢复列表中的废弃任务类型。
5. 删除 Git 跟踪的 `agent_service` 目录内容；保留被忽略的本地环境、PDF 和向量数据，不执行数据迁移。
6. 将根目录与子模块协作说明切换到 `agent_service_v2`，收口有效契约文档。
7. 运行前端、Backend、Agent Service v2 验证，修复回归。
8. 更新 `WorkLine.md`，检查接口漂移并提交中文 commit。
