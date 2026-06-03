# Agent Service Glossary

## `structured output`

指 Agent 产出必须符合 schema 约束的结构化 JSON 结果，而不是任意文本。

## `fallback`

指当 LLM、RAG、工具调用或 critic 失败时，回退到规则版、骨架版或较弱路径，保证接口不崩。

## `course_knowledge`

课程知识向量数据。用于 tutoring、assessment、resources 等链路的课程知识检索。

## `user_memory`

从历史对话中提炼出的长期语义记忆 facts，按用户维度检索。

## `readiness`

面向部署和联调的依赖检查，重点回答 provider 和 Qdrant 是否可构建、可探测。

## `smoke`

最小可用验证。目标不是业务质量验收，而是快速证明主链可跑。

## `best-effort persistence`

例如 memory/compress 中对 Qdrant facts 的写入，失败时记录日志但不一定让整个接口失败。
