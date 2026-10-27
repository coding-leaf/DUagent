from __future__ import annotations

import asyncio
import inspect
import logging
import math
import re
import uuid
from pathlib import Path
from typing import Any

from agentscope.message import TextBlock
from agentscope.rag import (
    ApproxTokenChunker,  # noqa: F401
    Chunk,
    ChunkerBase,
    KnowledgeBase,
    PDFParser,
    QdrantStore,
    Section,
    TextParser,
)

from agent_service_v2.agents.model_provider import (
    AgentModelSettings,
    build_embedding_model_from_settings,
    build_reranker_model_from_settings,
)


logger = logging.getLogger(__name__)


class CatalogKnowledgeContextEmpty(ValueError):
    pass


# ---------------------------------------------------------------------------
# 1. 语法保护型文本清洗模块 (clean_text_preserving_syntax)
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)")
_DISPLAY_MATH_RE = re.compile(r"(\$\$[\s\S]*?\$\$)")
_INLINE_CODE_RE = re.compile(r"(`[^`\n]+`)")
_INLINE_MATH_RE = re.compile(r"((?<!\$)\$(?!\$)(?:\\.|[^$\\\n])+(?<!\$)\$(?!\$))")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CATALOG_DOTS_RE = re.compile(r"[ \t]*(?:[\.·•…][ \t]*){3,}")
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")


def clean_text_preserving_syntax(text: str) -> str:
    """语法保护型预处理器。

    区分代码块、数学公式、目录引导点和普通段落：
    1. 提取并替换代码块与 LaTeX 公式为唯一占位符，完整保护缩进、注释与语法；
    2. 清洗控制符（如换页符 \\f）与无意义字符，压缩目录长连点（如 '.......' -> ' ... '）；
    3. 规范连续换行（保留最多 2 个换行）；
    4. 准确还原保护区内容。
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    if not text:
        return ""

    protected: dict[str, str] = {}
    counter = 0

    def _protect(match: re.Match) -> str:
        nonlocal counter
        key = f"__SYNTAX_PROTECTED_BLOCK_{counter}__"
        counter += 1
        protected[key] = match.group(0)
        return key

    # 1. 保护区提取
    # 块级代码
    text = _CODE_FENCE_RE.sub(_protect, text)
    # 块级公式
    text = _DISPLAY_MATH_RE.sub(_protect, text)
    # 行内代码
    text = _INLINE_CODE_RE.sub(_protect, text)
    # 行内公式
    text = _INLINE_MATH_RE.sub(_protect, text)

    # 2. 文本清洗
    # 移除换页符 \f 与控制字符（保留 \t, \n, \r）
    text = _CONTROL_CHARS_RE.sub("", text)
    # 折叠目录长连点及点阵符号
    text = _CATALOG_DOTS_RE.sub(" ... ", text)
    # 压缩连续冗余空行
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)

    # 3. 还原保护区
    for key, val in protected.items():
        text = text.replace(key, val)

    return text.strip()


# ---------------------------------------------------------------------------
# 2. Token 感知自适应递归二次切片模块 (TokenAwareRecursiveChunker)
# ---------------------------------------------------------------------------

_NUMBERED_UNIT_RE = re.compile(
    r"^(?:第\s*[0-9一二三四五六七八九十百零两]+\s*[章节讲单元篇]"
    r"|chapter\s*\d+|part\s*\d+|section\s*\d+)",
    re.IGNORECASE,
)
_DOTTED_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)+)\.?\s+\S")
_SPECIAL_HEADING_RE = re.compile(
    r"^(序言?|前言|引言|出版者的话|附录\s*[A-Za-z0-9一二三四五六七八九十]+|Appendix\s*[A-Za-z0-9]+)\b"
)
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_SENTENCE_END_RE = re.compile(r"[。！？；.!?;]$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；\n])|(?<=[.!?])\s+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_WORD_RE = re.compile(r"\b\w+\b")
_PUNCT_RE = re.compile(r"[^\w\s]")


def estimate_token_count(text: str) -> int:
    """保守估算文本的 Token 消耗，确保绝不低估触发模型 400 溢出。

    中文字符按 ~1.3 token/字，英文单词按 ~1.35 token/词，标点按 1.0 token。
    同时保底不少于字符长度的 0.5 倍。
    """
    if not text:
        return 0

    cjk_count = len(_CJK_RE.findall(text))
    non_cjk = _CJK_RE.sub(" ", text)
    word_count = len(_WORD_RE.findall(non_cjk))
    punct_count = len(_PUNCT_RE.findall(non_cjk))

    estimate = int(math.ceil(cjk_count * 1.3 + word_count * 1.35 + punct_count * 1.0))
    return max(estimate, int(math.ceil(len(text) * 0.5)), 1)


def get_safe_token_threshold(
    model_name: str | None = None,
    chunk_size: int = 512,
) -> int:
    """根据配置的 Embedding 模型动态获取安全 Token 上限阈值。

    - BAAI/bge-large-zh-v1.5 / 512 窗口模型：安全阈值设为 400（预留 112 Token 裕度防御 20015 错误）；
    - BAAI/bge-m3 / 8192 窗口模型：安全阈值设为 1200；
    - 其它默认以 400 与 chunk_size 取较小值。
    """
    if not model_name:
        return min(chunk_size, 400)
    name = model_name.lower()
    if "bge-m3" in name:
        return min(chunk_size, 1200)
    return min(chunk_size, 400)


def detect_heading(line: str) -> tuple[int, str] | None:
    """检测单行是否为大纲章节标题，返回 (层级, 标题文本) 或 None。"""
    text = line.strip()
    if not text:
        return None
    if _SENTENCE_END_RE.search(text):
        return None

    # 排除 C 语言预处理指令或宏定义防误判
    if re.match(
        r"^#\s*(include|define|undef|ifdef|ifndef|if|elif|else|endif|line|error|pragma)\b",
        text,
    ):
        return None

    m_atx = _ATX_HEADING_RE.match(text)
    if m_atx:
        return min(len(m_atx.group(1)), 3), m_atx.group(2).strip()

    # 针对非 ATX 样式的启发式标题匹配，限制长度避免正文长单句误判
    if len(text) > 80:
        return None

    if _NUMBERED_UNIT_RE.match(text):
        return 1, text

    m_dot = _DOTTED_NUMBER_RE.match(text)
    if m_dot:
        depth = m_dot.group(1).count(".") + 1
        return min(max(depth, 2), 3), text

    if _SPECIAL_HEADING_RE.match(text):
        return 1, text

    return None


def split_paragraphs_preserving_blocks(text: str) -> list[str]:
    """按双换行切分段落，但严格保护代码块与数学块内部的换行与缩进。"""
    if not text:
        return []

    protected: dict[str, str] = {}
    counter = 0

    def _protect(match: re.Match) -> str:
        nonlocal counter
        key = f"__PARAGRAPH_SPLIT_BLOCK_{counter}__"
        counter += 1
        protected[key] = match.group(0)
        return key

    masked = _CODE_FENCE_RE.sub(_protect, text)
    masked = _DISPLAY_MATH_RE.sub(_protect, masked)

    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", masked) if p.strip()]
    paragraphs: list[str] = []
    for para in raw_paras:
        for key, val in protected.items():
            if key in para:
                para = para.replace(key, val)
        paragraphs.append(para)

    return paragraphs


def recursive_split_text(
    text: str,
    max_tokens: int,
    overlap_tokens: int = 50,
) -> list[str]:
    """递归自适应子分块，绝无静默截断。

    优先级：双换行（段落） -> 标点/单换行（句子） -> 滑动窗口兜底。
    保证所有切片 estimated_token_count <= max_tokens。
    """
    text = text.strip()
    if not text:
        return []

    if estimate_token_count(text) <= max_tokens:
        return [text]

    # Level 1: 段落切分（双换行，且保护代码块/公式完整性）
    paragraphs = split_paragraphs_preserving_blocks(text)
    if len(paragraphs) > 1:
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0
        for p in paragraphs:
            p_tokens = estimate_token_count(p)
            if p_tokens > max_tokens:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                chunks.extend(recursive_split_text(p, max_tokens, overlap_tokens))
            elif current_tokens + p_tokens + 2 <= max_tokens:
                current_chunk.append(p)
                current_tokens += p_tokens + 2
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [p]
                current_tokens = p_tokens
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        return chunks

    # Level 2: 句子与单换行切分
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) > 1:
        chunks = []
        current_chunk = []
        current_tokens = 0
        for s in sentences:
            s_tokens = estimate_token_count(s)
            if s_tokens > max_tokens:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                chunks.extend(recursive_split_text(s, max_tokens, overlap_tokens))
            elif current_tokens + s_tokens + 1 <= max_tokens:
                current_chunk.append(s)
                current_tokens += s_tokens + 1
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [s]
                current_tokens = s_tokens
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    # Level 3: 滑动窗口字符级安全拆分（兜底极端超长单句或单行，绝不丢失任何字符）
    chars_per_token = len(text) / max(estimate_token_count(text), 1)
    step_chars = max(int(max_tokens * chars_per_token * 0.8), 20)
    overlap_chars = min(int(overlap_tokens * chars_per_token), step_chars // 2)

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + step_chars, len(text))
        piece = text[start:end].strip()
        while piece and estimate_token_count(piece) > max_tokens and end > start + 10:
            end -= 10
            piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += max(end - start - overlap_chars, 1)

    return chunks


class TokenAwareRecursiveChunker(ChunkerBase):
    """Token 感知自适应递归二次切片器。

    特性：
    - 读取模型安全 Token 窗口（防御 20015 参数超限）；
    - 结构化大纲上下文继承（Breadcrumbs 注入 metadata 与前缀）；
    - 递归分块：自然段落 -> 语句 -> 滑动窗口，取消静默硬截断；
    - 严格遵循 AgentScope ChunkerBase 规范。
    """

    chunker_type = "token_aware_recursive"

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        model_name: str | None = None,
        safe_threshold: int | None = None,
    ) -> None:
        super().__init__()
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.model_name = model_name
        self.safe_threshold = safe_threshold or get_safe_token_threshold(model_name, chunk_size)

    async def chunk(self, sections: list[Section]) -> list[Chunk]:
        """对 sections 列表执行高质量切片。"""
        breadcrumbs: list[str] = []
        raw_chunks: list[dict[str, Any]] = []

        for section in sections:
            # 保护多模态 DataBlock 原样透传
            if not hasattr(section.content, "text"):
                raw_chunks.append({
                    "content": section.content,
                    "source": section.source,
                    "metadata": section.metadata or {},
                })
                continue

            raw_text = section.content.text
            if not raw_text or not raw_text.strip():
                continue

            cleaned_text = clean_text_preserving_syntax(raw_text)
            if not cleaned_text.strip():
                continue

            # 段落级处理并维护层级大纲 Breadcrumbs
            paragraphs = split_paragraphs_preserving_blocks(cleaned_text)
            for para in paragraphs:
                lines = [line.strip() for line in para.splitlines() if line.strip()]
                if not lines:
                    continue

                # 标题感知
                heading_info = detect_heading(lines[0])
                if heading_info is not None:
                    lvl, heading_title = heading_info
                    if lvl == 1:
                        breadcrumbs = [heading_title]
                    elif lvl == 2:
                        breadcrumbs = breadcrumbs[:1] + [heading_title]
                    else:
                        breadcrumbs = breadcrumbs[:2] + [heading_title]

                    # 若段落仅包含标题自身，跳过正文拆分（大纲已挂载至后续切片）
                    if len(lines) == 1:
                        continue
                    # 保护后续正文行（包括代码缩进）完整性
                    raw_lines = para.splitlines()
                    body_text = "\n".join(raw_lines[1:]).strip()
                else:
                    body_text = para

                if not body_text:
                    continue

                chapter_path = " > ".join(breadcrumbs)
                prefix = f"[{chapter_path}]\n" if chapter_path else ""
                prefix_tokens = estimate_token_count(prefix)

                # 1. 前缀预算约束：若 prefix_tokens 过长，动态折叠或裁剪章节路径
                max_allowed_prefix = max(self.safe_threshold // 3, 20)
                if prefix_tokens > max_allowed_prefix and len(breadcrumbs) > 1:
                    for k in range(1, len(breadcrumbs)):
                        folded_crumbs = ["..."] + breadcrumbs[k:]
                        cand_path = " > ".join(folded_crumbs)
                        cand_prefix = f"[{cand_path}]\n"
                        if estimate_token_count(cand_prefix) <= max_allowed_prefix:
                            chapter_path = cand_path
                            prefix = cand_prefix
                            prefix_tokens = estimate_token_count(prefix)
                            break
                    else:
                        cand_path = f"... > {breadcrumbs[-1]}"
                        cand_prefix = f"[{cand_path}]\n"
                        chapter_path = cand_path
                        prefix = cand_prefix
                        prefix_tokens = estimate_token_count(prefix)

                if prefix_tokens > max_allowed_prefix:
                    # 单级标题或折叠后仍超限，截断末尾字符以硬性保障前缀在预算内
                    while chapter_path and estimate_token_count(f"[{chapter_path}...]\n") > max_allowed_prefix:
                        chapter_path = chapter_path[:-4].rstrip()
                    if chapter_path:
                        chapter_path = f"{chapter_path}..."
                        prefix = f"[{chapter_path}]\n"
                        prefix_tokens = estimate_token_count(prefix)
                    else:
                        prefix = ""
                        prefix_tokens = 0

                # 2. 动态正文预算计算
                max_body_tokens = max(self.safe_threshold - prefix_tokens - 10, self.chunk_size // 2)

                # 3. 初步切片
                pieces = recursive_split_text(body_text, max_tokens=max_body_tokens, overlap_tokens=self.overlap)

                # 4. 最终文本双重预算检查：确保 full_text <= safe_threshold
                def _split_into_safe_pieces(p: str) -> list[str]:
                    cand = f"{prefix}{p}" if prefix else p
                    if estimate_token_count(cand) <= self.safe_threshold:
                        return [p]
                    strict_budget = max(self.safe_threshold - prefix_tokens - 10, 20)
                    sub_pieces = recursive_split_text(
                        p,
                        max_tokens=strict_budget,
                        overlap_tokens=min(self.overlap, strict_budget // 4),
                    )
                    safe_list: list[str] = []
                    for sp in sub_pieces:
                        if estimate_token_count(f"{prefix}{sp}" if prefix else sp) <= self.safe_threshold:
                            safe_list.append(sp)
                        else:
                            # 字符级滑动窗口保底二次降级
                            avail_tokens = max(self.safe_threshold - prefix_tokens - 5, 10)
                            chars_per_tok = len(sp) / max(estimate_token_count(sp), 1)
                            step = max(int(avail_tokens * chars_per_tok * 0.7), 10)
                            st = 0
                            while st < len(sp):
                                ed = min(st + step, len(sp))
                                sub_sp = sp[st:ed].strip()
                                while (
                                    sub_sp
                                    and estimate_token_count(
                                        f"{prefix}{sub_sp}" if prefix else sub_sp
                                    ) > self.safe_threshold
                                    and ed > st + 5
                                ):
                                    ed -= 5
                                    sub_sp = sp[st:ed].strip()
                                if sub_sp:
                                    safe_list.append(sub_sp)
                                if ed >= len(sp):
                                    break
                                st = ed
                    return safe_list

                for piece in pieces:
                    for safe_piece in _split_into_safe_pieces(piece):
                        full_text = f"{prefix}{safe_piece}" if prefix else safe_piece
                        chunk_meta = dict(section.metadata) if section.metadata else {}
                        chunk_meta["chapter_path"] = chapter_path
                        chunk_meta["headings"] = list(breadcrumbs)
                        chunk_meta["raw_text"] = safe_piece
                        raw_chunks.append({
                            "content": TextBlock(text=full_text),
                            "source": section.source,
                            "metadata": chunk_meta,
                        })

        total = len(raw_chunks)
        chunks: list[Chunk] = []
        for idx, item in enumerate(raw_chunks):
            chunks.append(
                Chunk(
                    content=item["content"],
                    source=item["source"],
                    chunk_index=idx,
                    total_chunks=total,
                    metadata=item["metadata"],
                )
            )
        return chunks


# ---------------------------------------------------------------------------
# 3. 向量空间物理隔离与 Qdrant 蓝绿版本化入库
# ---------------------------------------------------------------------------


async def _safe_call(method: Any, *args: Any, **kwargs: Any) -> Any:
    """安全调用方法，若返回可等待对象则 await，同时包容同步 Mock 实例。"""
    if not callable(method):
        return None
    res = method(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res


def get_course_knowledge_collection_name(settings: AgentModelSettings) -> str:
    """根据配置的 Embedding 模型与维度动态派生隔离的集合名称。

    严禁不同模型或不同维度的向量混在同一个集合中。
    """
    raw_collection = settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION
    if not settings.EMBEDDING_MODEL:
        return raw_collection

    model_name = settings.EMBEDDING_MODEL.strip()
    model_slug = re.sub(r"[^a-zA-Z0-9]+", "_", model_name).strip("_").lower()

    if model_slug in raw_collection.lower():
        return raw_collection

    if raw_collection == "course_knowledge_v1_1024":
        return f"course_knowledge_{model_slug}_{settings.EMBEDDING_DIMENSION}"

    return f"{raw_collection}_{model_slug}_{settings.EMBEDDING_DIMENSION}"


def _matches_vector_dim(info: Any, expected_dim: int) -> bool:
    """检查集合向量维度是否与预期配置一致。"""
    if not info or not hasattr(info, "config") or not hasattr(info.config, "params"):
        return False
    vectors = getattr(info.config.params, "vectors", None)
    if hasattr(vectors, "size"):
        return bool(vectors.size == expected_dim)
    if isinstance(vectors, dict):
        return any(getattr(v, "size", None) == expected_dim for v in vectors.values())
    return False


def _is_historical_collection_model_compatible(
    candidate: str,
    settings: AgentModelSettings,
) -> bool:
    """严格校验历史 Qdrant 集合与当前 Embedding 模型的语义空间兼容性。

    严禁仅凭向量维度相同即静默回退。对模型来源无法确认或模型不匹配的 Legacy 集合，
    采取保守策略，拒绝回退查询。
    """
    current_model = (settings.EMBEDDING_MODEL or "").strip()
    if not current_model:
        return False

    current_slug = re.sub(r"[^a-zA-Z0-9]+", "_", current_model).strip("_").lower()

    # 1. 显式白名单配置
    whitelist = getattr(settings, "HISTORICAL_FALLBACK_COMPATIBLE_MODELS", None)
    if whitelist:
        if isinstance(whitelist, str):
            allowed = [m.strip().lower() for m in whitelist.split(",") if m.strip()]
        else:
            allowed = [str(m).strip().lower() for m in whitelist if str(m).strip()]
        if any(
            m in current_model.lower()
            or re.sub(r"[^a-zA-Z0-9]+", "_", m).strip("_").lower() == current_slug
            for m in allowed
        ):
            return True

    # 2. 候选集合名称中明确包含当前模型标识
    if current_slug in candidate.lower():
        return True

    # 3. 历史 v1 约定基准集合（course_knowledge_v1_1024 / course_knowledge_v1 / course_knowledge_legacy）
    if (
        "course_knowledge_v1" in candidate
        or "course_knowledge_legacy" in candidate
        or candidate == "course_knowledge_v1_1024"
    ):
        # DUagent 历史基准模型约定为 BAAI/bge-large-zh-v1.5
        if "bge_large_zh" in current_slug:
            return True
        return False

    return False


async def _get_historical_fallback_collection(
    client: Any,
    settings: AgentModelSettings,
    target_collection: str,
) -> str | None:
    """检查是否存在兼容的历史默认集合（如 course_knowledge_v1_1024）。

    仅在集合存在、语义空间模型兼容且向量维度与配置一致时返回集合名称，支持透明只读回退。
    """
    if not client:
        return None

    raw_collection = settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION
    candidates: list[str] = []
    if raw_collection and raw_collection != target_collection:
        candidates.append(raw_collection)
    if (
        "course_knowledge_v1_1024" != target_collection
        and "course_knowledge_v1_1024" not in candidates
    ):
        candidates.append("course_knowledge_v1_1024")

    for candidate in candidates:
        try:
            exists = False
            if hasattr(client, "collection_exists"):
                exists = await _safe_call(client.collection_exists, collection_name=candidate)
            elif hasattr(client, "get_collections"):
                collections = await _safe_call(client.get_collections)
                names = {c.name for c in getattr(collections, "collections", [])}
                exists = candidate in names
            else:
                exists = True

            if not exists:
                continue

            # 语义空间兼容性强校验：模型不匹配严格拒绝回退
            if not _is_historical_collection_model_compatible(candidate, settings):
                logger.debug(
                    "Candidate fallback collection %s rejected: model %s incompatible",
                    candidate,
                    settings.EMBEDDING_MODEL,
                )
                continue

            info = await _safe_call(client.get_collection, collection_name=candidate)
            if _matches_vector_dim(info, settings.EMBEDDING_DIMENSION):
                return candidate
        except Exception as exc:
            logger.debug("Candidate fallback collection %s check failed: %s", candidate, exc)
            continue

    return None


def build_qdrant_store(settings: AgentModelSettings) -> QdrantStore:
    """实例化并返回 AgentScope QdrantStore，用于教材向量化存储。"""
    client_kwargs = {"check_compatibility": False}
    url = settings.QDRANT_URL
    path = settings.QDRANT_PATH
    api_key = getattr(settings, "QDRANT_API_KEY", None)

    return QdrantStore(
        url=url,
        path=path if not url else None,
        api_key=api_key,
        client_kwargs=client_kwargs,
    )


async def ensure_qdrant_collection_exists(
    store: QdrantStore,
    settings: AgentModelSettings,
    collection_name: str | None = None,
) -> None:
    """确保 Qdrant collection 存在，使用隔离的集合名称。"""
    from qdrant_client.models import Distance, VectorParams

    collection = collection_name or get_course_knowledge_collection_name(settings)
    client = store.get_client()
    try:
        collections = await _safe_call(client.get_collections)
        if collections and hasattr(collections, "collections"):
            names = {c.name for c in collections.collections}
            if collection in names:
                return
    except Exception as exc:
        logger.warning("Failed to check Qdrant collections: %s", exc)

    try:
        await _safe_call(
            client.create_collection,
            collection_name=collection,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
    except Exception as exc:
        logger.warning("Failed to create collection %s: %s", collection, exc)


def get_course_knowledge_base(
    course_id: str,
    settings: AgentModelSettings,
    collection_name: str | None = None,
) -> KnowledgeBase:
    """根据 course_id 构建隔离的 KnowledgeBase 实例。"""
    embedding_model = build_embedding_model_from_settings(settings)
    vector_store = build_qdrant_store(settings)
    collection = collection_name or get_course_knowledge_collection_name(settings)

    # 隔离性设计：在 KB 级别绑定 course_id 过滤
    return KnowledgeBase(
        name=f"course_kb_{course_id}",
        description=f"Knowledge base for course catalog {course_id}",
        embedding_model=embedding_model,
        vector_store=vector_store,
        collection=collection,
        metadata_filter={"course_id": course_id},
    )


async def ingest_course_material(
    file_path: Path | str,
    course_id: str,
    settings: AgentModelSettings,
    chunk_size: int = 512,
    overlap: int = 50,
    material_id: str | None = None,
) -> int:
    """对课本教材进行语法防误伤预处理、递归二次分块与 Qdrant 蓝绿版本化幂等入库。

    严禁先删后写：
    1. 生成唯一批次号 ingestion_version；
    2. 新版本切片附带 is_active=False 分批写入 Qdrant；
    3. 全量切片写入并完成数量校验后，原子切换 is_active=True；
    4. 异步清理旧版本淘汰切片；
    5. 若中途失败，安全回滚当前批次，现有生效数据零受损。

    返回生成的 Chunk 数量。
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Course material file not found: {path}")

    effective_material_id = material_id or path.name

    # 1. 选用对应 Parser 解析，提供平滑容错降级
    sections: list[Section] = []
    if path.suffix.lower() == ".pdf":
        try:
            parser = PDFParser()
            sections = await parser.parse(str(path), path.name)
        except Exception as exc:
            logger.warning(
                "PDFParser failed for %s: %s. Falling back to plain text slide window.",
                path.name,
                exc,
            )
            sections = []
    else:
        try:
            parser = TextParser()
            sections = await parser.parse(str(path), path.name)
        except Exception as exc:
            logger.warning(
                "TextParser failed for %s: %s. Falling back to plain text slide window.",
                path.name,
                exc,
            )
            sections = []

    # 降级兜底：Parser 抛出异常或返回空时，尝试直接按普通文本降级处理
    if not sections:
        try:
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            raw_text = ""
        if raw_text.strip():
            sections = [
                Section(
                    content=TextBlock(text=raw_text),
                    source=path.name,
                    metadata={"page": 1},
                )
            ]

    if not sections:
        return 0

    # 2. Token 感知递归二次切片
    chunker = TokenAwareRecursiveChunker(
        chunk_size=chunk_size,
        overlap=overlap,
        model_name=settings.EMBEDDING_MODEL,
    )
    raw_chunks = await chunker.chunk(sections)

    # 3. 构造原生 Chunk 列表并绑定蓝绿版本标识
    ingestion_version = uuid.uuid4().hex
    chunks: list[Chunk] = []

    for idx, raw_chunk in enumerate(raw_chunks):
        content_text = (
            raw_chunk.content.text
            if hasattr(raw_chunk.content, "text")
            else str(raw_chunk.content)
        )
        if not content_text.strip():
            continue

        meta = dict(raw_chunk.metadata) if raw_chunk.metadata else {}
        meta.update({
            "course_id": course_id,
            "catalog_id": course_id,
            "material_id": effective_material_id,
            "ingestion_version": ingestion_version,
            "is_active": False,
            "filename": path.name,
        })

        chunks.append(
            Chunk(
                content=raw_chunk.content,
                source=path.name,
                chunk_index=idx,
                total_chunks=len(raw_chunks),
                metadata=meta,
            )
        )

    if not chunks:
        return 0

    # 重新修正 total_chunks
    for chunk in chunks:
        chunk.total_chunks = len(chunks)

    # 4. 获取物理隔离的 Collection 并确保其存在
    collection_name = get_course_knowledge_collection_name(settings)
    kb = get_course_knowledge_base(course_id, settings, collection_name=collection_name)
    await ensure_qdrant_collection_exists(kb.vector_store, settings, collection_name=collection_name)

    client = getattr(getattr(kb, "vector_store", None), "get_client", lambda: None)()

    # 5. 分批（16块）安全写入，带指数退避重试，防御临时网络抖动
    async def _rollback_batch() -> None:
        if client and hasattr(client, "delete"):
            try:
                rollback_filter = Filter(
                    must=[
                        FieldCondition(
                            key="chunk.metadata.ingestion_version",
                            match=MatchValue(value=ingestion_version),
                        )
                    ]
                )
                await _safe_call(
                    client.delete,
                    collection_name=collection_name,
                    points_selector=rollback_filter,
                )
            except Exception as rollback_err:
                logger.warning("Failed to rollback version %s: %s", ingestion_version, rollback_err)

    batch_size = 16
    try:
        for i in range(0, len(chunks), batch_size):
            chunk_batch = chunks[i : i + batch_size]
            for attempt in range(3):
                try:
                    await kb.insert_document(
                        chunk_batch,
                        document_id=ingestion_version,
                        document_metadata={
                            "course_id": course_id,
                            "catalog_id": course_id,
                            "material_id": effective_material_id,
                            "ingestion_version": ingestion_version,
                            "is_active": False,
                        },
                    )
                    break
                except Exception as exc:
                    if attempt < 2:
                        logger.warning(
                            "Transient failure during insert batch (attempt %d/3): %s. Retrying...",
                            attempt + 1,
                            exc,
                        )
                        await asyncio.sleep(0.5 * (2 ** attempt))
                    else:
                        raise
    except Exception as exc:
        logger.error(
            "Ingestion failed during writing version %s: %s. Rolling back uncompleted points.",
            ingestion_version,
            exc,
        )
        await _rollback_batch()
        raise

    # 6. 完整性校验：验证实际写入切片总数（强校验：数量不一致或客户端异常立即阻断回滚）
    if client and hasattr(client, "count"):
        try:
            count_filter = Filter(
                must=[
                    FieldCondition(
                        key="chunk.metadata.course_id",
                        match=MatchValue(value=course_id),
                    ),
                    FieldCondition(
                        key="chunk.metadata.material_id",
                        match=MatchValue(value=effective_material_id),
                    ),
                    FieldCondition(
                        key="chunk.metadata.ingestion_version",
                        match=MatchValue(value=ingestion_version),
                    ),
                ]
            )
            count_res = await _safe_call(
                client.count,
                collection_name=collection_name,
                count_filter=count_filter,
                exact=True,
            )
            inserted_count = getattr(count_res, "count", None)
            if not isinstance(inserted_count, int) or inserted_count != len(chunks):
                raise RuntimeError(
                    f"Ingestion count verification failed: expected {len(chunks)}, got {inserted_count}"
                )
        except Exception as exc:
            await _rollback_batch()
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(
                f"Qdrant count check failed for version {ingestion_version}: {exc}"
            ) from exc

    # 7. 原子生效切换：更新 is_active = True（强前置：激活失败必须立即回滚，严禁清理旧版本）
    if client and hasattr(client, "set_payload"):
        try:
            activate_filter = Filter(
                must=[
                    FieldCondition(
                        key="chunk.metadata.ingestion_version",
                        match=MatchValue(value=ingestion_version),
                    )
                ]
            )
            # 嵌套更新 chunk.metadata.is_active
            await _safe_call(
                client.set_payload,
                collection_name=collection_name,
                payload={"is_active": True},
                key="chunk.metadata",
                points=activate_filter,
            )
            # 顶层设置 is_active 及三层标识
            await _safe_call(
                client.set_payload,
                collection_name=collection_name,
                payload={
                    "is_active": True,
                    "course_id": course_id,
                    "catalog_id": course_id,
                    "material_id": effective_material_id,
                    "ingestion_version": ingestion_version,
                },
                points=activate_filter,
            )
        except Exception as exc:
            logger.error(
                "Failed to activate ingestion version %s: %s. Rolling back uncompleted points.",
                ingestion_version,
                exc,
            )
            await _rollback_batch()
            raise RuntimeError(
                f"Failed to activate ingestion version {ingestion_version}: {exc}"
            ) from exc

    # 8. 激活验证：验证实际激活点位数是否等于写入切片总数
    if client and hasattr(client, "count"):
        try:
            active_verify_filter = Filter(
                must=[
                    FieldCondition(
                        key="chunk.metadata.course_id",
                        match=MatchValue(value=course_id),
                    ),
                    FieldCondition(
                        key="chunk.metadata.material_id",
                        match=MatchValue(value=effective_material_id),
                    ),
                    FieldCondition(
                        key="chunk.metadata.ingestion_version",
                        match=MatchValue(value=ingestion_version),
                    ),
                    FieldCondition(
                        key="chunk.metadata.is_active",
                        match=MatchValue(value=True),
                    ),
                ]
            )
            active_res = await _safe_call(
                client.count,
                collection_name=collection_name,
                count_filter=active_verify_filter,
                exact=True,
            )
            active_count = getattr(active_res, "count", None)
            if not isinstance(active_count, int) or active_count != len(chunks):
                raise RuntimeError(
                    f"Activation verification failed: expected {len(chunks)} active points, got {active_count}"
                )
        except Exception as exc:
            await _rollback_batch()
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(
                f"Activation verification check failed for version {ingestion_version}: {exc}"
            ) from exc

    # 9. 淘汰清理旧版本：仅在激活校验成功后执行，且必须同时指定 course_id 与 material_id
    if client and hasattr(client, "delete"):
        try:
            cleanup_filter = Filter(
                must=[
                    FieldCondition(
                        key="chunk.metadata.course_id",
                        match=MatchValue(value=course_id),
                    ),
                    FieldCondition(
                        key="chunk.metadata.material_id",
                        match=MatchValue(value=effective_material_id),
                    ),
                ],
                must_not=[
                    FieldCondition(
                        key="chunk.metadata.ingestion_version",
                        match=MatchValue(value=ingestion_version),
                    )
                ],
            )
            await _safe_call(
                client.delete,
                collection_name=collection_name,
                points_selector=cleanup_filter,
            )
        except Exception as exc:
            logger.warning(
                "Failed to cleanup obsolete points for course %s material %s: %s",
                course_id,
                effective_material_id,
                exc,
            )

    return len(chunks)


def _text_from_agentscope_payload(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    chunk = payload.get("chunk")
    if isinstance(chunk, dict):
        content = chunk.get("content")
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        elif isinstance(content, str) and content.strip():
            return content.strip()
        text = chunk.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


def _truncate_chunk(text: str, max_chars: int = 1200) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _is_payload_active(payload: dict[str, Any]) -> bool:
    """判断 Payload 是否属于已生效的切片。"""
    if not isinstance(payload, dict):
        return False
    chunk = payload.get("chunk") or {}
    meta = chunk.get("metadata") if isinstance(chunk, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    is_active = meta.get("is_active", payload.get("is_active"))
    return is_active is True


def _is_payload_legacy_compatible(payload: dict[str, Any]) -> bool:
    """判断 Payload 是否属于合法的历史遗留切片（无 is_active 且无 ingestion_version）。"""
    if not isinstance(payload, dict):
        return False
    chunk = payload.get("chunk") or {}
    meta = chunk.get("metadata") if isinstance(chunk, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    is_active = meta.get("is_active", payload.get("is_active"))
    ingestion_version = meta.get("ingestion_version", payload.get("ingestion_version"))
    return is_active is not False and ingestion_version is None


async def _fetch_kg_records_from_collection(
    client: Any,
    collection_name: str,
    catalog_id: str,
    limit: int,
) -> list[Any]:
    """从指定集合检索符合条件的知识切片点位，防泄露未激活数据。"""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    if not client:
        return []

    # 1. 主检索：显式限定 must: [course_id == catalog_id, is_active == True]
    active_filter = Filter(
        must=[
            FieldCondition(
                key="chunk.metadata.course_id",
                match=MatchValue(value=catalog_id),
            ),
            FieldCondition(
                key="chunk.metadata.is_active",
                match=MatchValue(value=True),
            ),
        ]
    )
    scroll_res = await _safe_call(
        client.scroll,
        collection_name=collection_name,
        scroll_filter=active_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    records = scroll_res[0] if scroll_res else []
    valid_records = [
        rec for rec in records
        if _is_payload_active(getattr(rec, "payload", {}) or {})
    ]
    if valid_records:
        return valid_records

    # 2. 历史 Legacy 兜底：仅当主检索未命中且存在无版本标记的老数据时回退
    legacy_filter = Filter(
        must=[
            FieldCondition(
                key="chunk.metadata.course_id",
                match=MatchValue(value=catalog_id),
            )
        ],
        must_not=[
            FieldCondition(
                key="chunk.metadata.is_active",
                match=MatchValue(value=False),
            )
        ],
    )
    scroll_res = await _safe_call(
        client.scroll,
        collection_name=collection_name,
        scroll_filter=legacy_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    candidate_records = scroll_res[0] if scroll_res else []
    valid_legacy = [
        rec for rec in candidate_records
        if _is_payload_legacy_compatible(getattr(rec, "payload", {}) or {})
    ]
    return valid_legacy


async def build_catalog_kg_context(
    catalog_id: str,
    *,
    settings: AgentModelSettings | None = None,
    limit: int = 24,
    max_chars: int = 18000,
) -> str:
    """Build KG generation context from AgentScope 2.x Qdrant chunks.

    具有蓝绿版本感知与向后兼容支持：
    - 优先匹配已生效版本（排除 is_active=False 的正在入库切片）；
    - 向后兼容无版本标记的老数据；
    - 目标集合无切片时支持历史兼容 Collection 透明回退。
    """
    settings = settings or AgentModelSettings()
    collection_name = get_course_knowledge_collection_name(settings)
    store = build_qdrant_store(settings)
    client = store.get_client()

    records = await _fetch_kg_records_from_collection(client, collection_name, catalog_id, limit)

    # 兜底：若目标模型派生集合未命中任何切片，尝试历史 Collection 回退读取
    if not records:
        fallback_col = await _get_historical_fallback_collection(client, settings, collection_name)
        if fallback_col:
            records = await _fetch_kg_records_from_collection(client, fallback_col, catalog_id, limit)

    chunks: list[str] = []
    used_chars = 0
    for record in records:
        payload = getattr(record, "payload", None)
        if not isinstance(payload, dict):
            continue
        text = _truncate_chunk(_text_from_agentscope_payload(payload))
        if not text:
            continue
        if used_chars + len(text) > max_chars:
            remaining = max_chars - used_chars
            if remaining <= 200:
                break
            text = _truncate_chunk(text, remaining)
        chunks.append(text)
        used_chars += len(text)
        if used_chars >= max_chars:
            break

    if not chunks:
        raise CatalogKnowledgeContextEmpty(
            "No catalog knowledge chunks found for KG generation"
        )
    return "\n---\n".join(chunks)


async def retrieve_course_context(
    query: str,
    course_id: str,
    limit: int = 3,
    settings: AgentModelSettings | None = None,
) -> dict[str, Any]:
    """Agent RAG 检索工具：检索当前课程相关的课本段落，执行重排并返回引文。"""
    settings = settings or AgentModelSettings()
    kb = get_course_knowledge_base(course_id, settings)

    def _is_chunk_valid_and_active(chunk: Any) -> bool:
        if not chunk:
            return False
        meta = getattr(chunk, "metadata", None)
        if not isinstance(meta, dict):
            meta = {}
        is_active = meta.get("is_active")
        ingestion_version = meta.get("ingestion_version")
        if is_active is False:
            return False
        if is_active is True:
            return True
        return ingestion_version is None

    # 1. 使用绑定了 course_id 的 KB.search 执行向量检索
    raw_results = await kb.search(queries=[query], top_k=limit * 2)
    active_results = [
        res
        for res in (raw_results or [])
        if _is_chunk_valid_and_active(getattr(res, "chunk", None))
    ]

    # 2. 若目标派生集合未命中，尝试历史 Collection 透明只读回退
    if not active_results:
        client = getattr(getattr(kb, "vector_store", None), "get_client", lambda: None)()
        current_collection = get_course_knowledge_collection_name(settings)
        fallback_col = await _get_historical_fallback_collection(client, settings, current_collection)
        if fallback_col:
            fallback_kb = get_course_knowledge_base(course_id, settings, collection_name=fallback_col)
            fallback_raw = await fallback_kb.search(queries=[query], top_k=limit * 2)
            active_results = [
                res
                for res in (fallback_raw or [])
                if _is_chunk_valid_and_active(getattr(res, "chunk", None))
            ]

    if not active_results:
        return {
            "outcome": "neutral",
            "status": "empty",
            "reason": None,
            "summary": "No relevant course material found.",
            "retryable": False,
            "data": {"context_text": ""},
            "context_text": "",
            "sources": [],
        }

    def _extract_chunk_text(c: Any) -> str:
        if not c:
            return ""
        content = getattr(c, "content", None)
        if hasattr(content, "text") and isinstance(content.text, str):
            return content.text
        if isinstance(content, str):
            return content
        return str(content) if content is not None else ""

    # 3. 提取文本，进行语义重排（Rerank）提升质量
    reranker = build_reranker_model_from_settings(settings)
    documents = [_extract_chunk_text(res.chunk) for res in active_results]

    if reranker and documents:
        try:
            scores = await reranker.score(query, documents)
            # 根据 Reranker 重新排序
            scored_results = sorted(
                zip(active_results, scores, strict=True),
                key=lambda x: x[1],
                reverse=True,
            )
            filtered_results = scored_results[:limit]
        except Exception as exc:
            logger.warning("Reranking failed: %s. Falling back to vector search order.", exc)
            filtered_results = [(res, res.score or 0.0) for res in active_results[:limit]]
    else:
        filtered_results = [(res, res.score or 0.0) for res in active_results[:limit]]

    # 4. 组装最终检索结果和引文 citations
    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []

    for idx, (res, score) in enumerate(filtered_results):
        chunk = res.chunk
        payload = chunk.metadata or {}
        filename = payload.get("filename") or chunk.source or "unknown_textbook"
        chunk_text = _extract_chunk_text(chunk)

        context_parts.append(f"[{idx+1}] File: {filename}\nContent: {chunk_text}\n")
        sources.append(
            {
                "source_file": filename,
                "snippet": chunk_text,
                "score": float(score),
            }
        )

    context_text = "\n".join(context_parts)
    return {
        "outcome": "success",
        "status": "available",
        "reason": None,
        "summary": {"returned_count": len(sources)},
        "retryable": False,
        "data": {"context_text": context_text},
        "context_text": context_text,
        "sources": sources,
    }
