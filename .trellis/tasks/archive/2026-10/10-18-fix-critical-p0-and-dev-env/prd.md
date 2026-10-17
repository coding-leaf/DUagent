# 修复全局致命 P0 缺陷与本地开发环境基线

## Goal

修复代码审计报告中揭示的 5 项致命级 (P0) 隐患与本地联调阻塞缺陷，建立安全、健康的重构基准。

## Requirements

1. **后端测验判分安全 (Backend P0-2)**：
   - 彻底移除 `backend/app/services/quiz_service.py` 中对 `correct_answer` 和 `correct_for_agent` 的 `eval()` 调用。
   - 改用 `json.loads` 安全解析 JSON 字符串；对逗号分隔的非 JSON 格式使用 `[s.strip() for s in text.split(",") if s.strip()]` 解析。
   - 增加辅助解析函数 `_parse_answer_list(raw_ans)`，杜绝代码注入风险。

2. **后端特权提升防范 (Backend P0-1)**：
   - 检查 `backend/app/api/v1/auth.py`，对默认永久码进行收紧。若保留开发便捷性，限制仅在非生产开发环境生效或通过环境变量配置，杜绝生产硬编码默认教师权限提权。

3. **前端聊天停止生成死锁修复 (Frontend P0-1)**：
   - 在 `frontend/src/context/ChatContext.jsx` 的 `cancelStream` 中，必须重置 `isSending` 状态 (`setIsSending(false)`)，并将当前 in-flight 的消息标记为 `loading: false`。
   - 确保用户点击“停止生成”后，输入框立即恢复可输入状态，发送按钮恢复正常。

4. **前端登录 401 拦截器自毁修复 (Frontend P0-2)**：
   - 修改 `frontend/src/api/client.js` 的响应拦截器：当 HTTP 状态码为 401 时，如果当前请求是 `/api/v1/auth/login` 或当前页面处于 `/login`，不执行全局清空与强制重定向，将错误正常传递给页面的 catch 块，以正常展示“邮箱或密码错误”提示。

5. **本地开发环境 Token 对齐 (Integration P0-1)**：
   - 在 `start_all.sh` 启动 Agent Service 时，映射 `BACKEND_INTERNAL_AGENT_TOKEN="${INTERNAL_AGENT_TOKEN:-$BACKEND_INTERNAL_AGENT_TOKEN}"`。
   - 在 `agent_service_v2` 配置中支持兼容读取 `INTERNAL_AGENT_TOKEN`，确保本地一键启动时所有内部 AI-Chat 工具正常工作。

## Acceptance Criteria

- [x] `quiz_service.py` 中没有任何 `eval()` 调用，多选题与 JSON 答案安全解析并通过测试。
- [x] 注册逻辑无法在缺少配置或生产环境下通过明文提权为教师。
- [x] 前端 `cancelStream()` 调用后，`isSending` 正确重置为 `false`，输入框不锁死。
- [x] 前端在 `/login` 接口返回 401 时不会整页刷新跳出，能正常捕获错误并在界面展示。
- [x] 本地启动配置中 `INTERNAL_AGENT_TOKEN` 与 `BACKEND_INTERNAL_AGENT_TOKEN` 互通，Agent 能够成功连接 Backend 内部工具。
