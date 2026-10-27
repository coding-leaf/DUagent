from __future__ import annotations

import asyncio
import hashlib
import math
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from agentscope.embedding._embedding_base import EmbeddingResponse
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.tools.rag import (
    CatalogKnowledgeContextEmpty,
    TokenAwareRecursiveChunker,
    build_catalog_kg_context,
    estimate_token_count,
    get_course_knowledge_collection_name,
    ingest_course_material,
    retrieve_course_context,
)


class DeterministicTestEmbeddingModel:
    """确定性本地测试 Embedding 实现，输出固定 1024 维归一化向量，彻底摆脱对外部付费 API 的依赖。"""

    supports_multimodal: bool = False

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension

    def _embed_text(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(self.dimension):
            b = h[i % len(h)]
            val = ((b + i * 31) % 256) / 255.0 - 0.5
            vec.append(val)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def __call__(self, inputs: list, **kwargs) -> EmbeddingResponse:
        embeddings = []
        for item in inputs:
            text = item.text if hasattr(item, "text") else str(item)
            embeddings.append(self._embed_text(text))
        return EmbeddingResponse(embeddings=embeddings)


@pytest.fixture(autouse=True)
def deterministic_embedding_env(monkeypatch):
    """为集成测试注入确定性的本地测试 Embedding 模型实现，无需任何外部 API Key。"""
    dummy_model = DeterministicTestEmbeddingModel(1024)
    monkeypatch.setattr(
        "agent_service_v2.tools.rag.build_embedding_model_from_settings",
        lambda settings=None: dummy_model,
    )
    return dummy_model


def _is_qdrant_running(url: str = "http://127.0.0.1:6333") -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"{url}/", timeout=1) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def _get_test_settings(coll_prefix: str, tmp_path: Path) -> AgentModelSettings:
    """构建真实 Qdrant 测试环境配置。"""
    unique_name = f"{coll_prefix}_{uuid.uuid4().hex[:8]}"
    return AgentModelSettings(
        QDRANT_URL="http://127.0.0.1:6333",
        QDRANT_COURSE_KNOWLEDGE_COLLECTION=unique_name,
        EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5",
        EMBEDDING_DIMENSION=1024,
    )


@pytest.fixture
def real_settings(tmp_path: Path):
    if not _is_qdrant_running():
        pytest.skip("Real Qdrant service is not running on http://127.0.0.1:6333")

    settings = _get_test_settings("test_pipeline", tmp_path)
    client = AsyncQdrantClient(url=settings.QDRANT_URL, check_compatibility=False)

    yield settings

    # 清理测试创建的集合
    async def _cleanup():
        derived_name = get_course_knowledge_collection_name(settings)
        for name in [derived_name, settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION]:
            try:
                if await client.collection_exists(name):
                    await client.delete_collection(name)
            except Exception:
                pass
        try:
            await client.close()
        except Exception:
            pass

    try:
        asyncio.run(_cleanup())
    except Exception:
        pass


def test_token_aware_recursive_chunker_handles_extreme_prefix_and_budget() -> None:
    """验证极端深层或超长章节前缀下，生成的全部 Chunk 最终 Token 均严格 <= safe_threshold (400)。"""
    chunker = TokenAwareRecursiveChunker(
        chunk_size=512,
        overlap=30,
        model_name="BAAI/bge-large-zh-v1.5",
        safe_threshold=400,
    )

    from agentscope.message import TextBlock
    from agentscope.rag import Section

    # 构造极长标题与深层大纲
    long_h1 = "# 第1章 " + "计算机体系结构与指令集深入分析" * 8
    long_h2 = "## 1.1 " + "寄存器传输级设计与硬件描述语言实现规范" * 8
    long_body = (
        "流水线冒险是指由于流水线结构、数据相关或控制转移导致的流水线暂停。"
        "数据冒险包括写后读(RAW)、读后写(WAR)和写后写(WAW)。"
        "结构冒险是指多条指令同时争用同一硬件资源。"
        "分支预测算法可以减少控制冒险带来的性能惩罚。"
    ) * 15

    raw_text = f"{long_h1}\n\n{long_h2}\n\n{long_body}"
    sections = [Section(content=TextBlock(text=raw_text), source="extreme_book.txt")]

    chunks = asyncio.run(chunker.chunk(sections))
    assert len(chunks) > 0

    for idx, c in enumerate(chunks):
        text = c.content.text
        tokens = estimate_token_count(text)
        assert tokens <= 400, f"Chunk {idx} exceeded 400 tokens: {tokens} tokens -> {text[:60]}..."
        # 验证大纲前缀被合理折叠或裁剪
        assert text.startswith("[")


def test_real_qdrant_multiple_materials_same_course_isolation(
    real_settings: AgentModelSettings,
    tmp_path: Path,
) -> None:
    """1. 同一课程多教材连续入库与教材级隔离测试：

    同一课程连续入库教材 A 与教材 B，教材 A 的切片在教材 B 入库后保持完好；
    再次入库教材 A 新版本时，仅淘汰教材 A 旧版本，教材 B 毫发无损。
    """
    course_id = f"course_iso_{uuid.uuid4().hex[:6]}"

    # 入库教材 A (v1)
    file_a = tmp_path / "math_analysis.txt"
    file_a.write_text("第一章 微积分学\n\n导数与微分定义，极限运算法则与连续函数性质。", encoding="utf-8")
    cnt_a1 = asyncio.run(ingest_course_material(file_a, course_id, real_settings))
    assert cnt_a1 >= 1

    # 入库教材 B (v1)
    file_b = tmp_path / "linear_algebra.txt"
    file_b.write_text("第一章 线性空间\n\n向量组的线性相关性与极大无关组与矩阵特征值。", encoding="utf-8")
    cnt_b1 = asyncio.run(ingest_course_material(file_b, course_id, real_settings))
    assert cnt_b1 >= 1

    # 验证两个教材的数据在同一课程下并存且均生效
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)
    coll_name = get_course_knowledge_collection_name(real_settings)

    filter_a = Filter(
        must=[
            FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
            FieldCondition(key="chunk.metadata.material_id", match=MatchValue(value="math_analysis.txt")),
            FieldCondition(key="chunk.metadata.is_active", match=MatchValue(value=True)),
        ]
    )
    filter_b = Filter(
        must=[
            FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
            FieldCondition(key="chunk.metadata.material_id", match=MatchValue(value="linear_algebra.txt")),
            FieldCondition(key="chunk.metadata.is_active", match=MatchValue(value=True)),
        ]
    )

    res_a = asyncio.run(client.count(coll_name, count_filter=filter_a))
    res_b = asyncio.run(client.count(coll_name, count_filter=filter_b))
    assert res_a.count == cnt_a1
    assert res_b.count == cnt_b1

    # 再次入库教材 A 的新版本 (v2)
    file_a.write_text("第一章 微积分学修订版\n\n全量引入多元微分与隐函数定理。", encoding="utf-8")
    cnt_a2 = asyncio.run(ingest_course_material(file_a, course_id, real_settings))
    assert cnt_a2 >= 1

    # 验证：教材 A 的点位已切换至新版本（总数等于新版本切片数），而教材 B 的点位完全不受影响！
    try:
        res_a_after = asyncio.run(client.count(coll_name, count_filter=filter_a))
        res_b_after = asyncio.run(client.count(coll_name, count_filter=filter_b))
        assert res_a_after.count == cnt_a2
        assert res_b_after.count == cnt_b1
    finally:
        asyncio.run(client.close())


def test_real_qdrant_write_or_count_failure_rollback(
    real_settings: AgentModelSettings,
    tmp_path: Path,
) -> None:
    """2. 写入或数量校验失败时新数据回滚测试：

    模拟 Qdrant 数量校验不匹配，触发回滚并抛出异常，点位被清空。
    """
    course_id = f"course_count_fail_{uuid.uuid4().hex[:6]}"
    file_doc = tmp_path / "algorithm.txt"
    file_doc.write_text("第一章 动态规划\n\n状态转移方程与最优子结构性质分析。", encoding="utf-8")

    coll_name = get_course_knowledge_collection_name(real_settings)
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)

    # 模拟第一次 count 调用（写入强校验）返回数量不匹配 (比如预期 1，返回 0)
    original_count = AsyncQdrantClient.count
    call_idx = 0

    async def fake_count(self, *args, **kwargs):
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            # 模拟数量校验失败
            from qdrant_client.http.models.models import CountResult
            return CountResult(count=999)
        return await original_count(self, *args, **kwargs)

    with patch.object(AsyncQdrantClient, "count", new=fake_count):
        with pytest.raises(RuntimeError, match="Ingestion count verification failed"):
            asyncio.run(ingest_course_material(file_doc, course_id, real_settings))

    # 验证新版本的临时切片被完全回滚清理，没有任何切片残留
    try:
        total = asyncio.run(client.count(coll_name, count_filter=Filter(must=[FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id))])))
        assert total.count == 0
    finally:
        asyncio.run(client.close())


def test_real_qdrant_activation_failure_rollback_and_preserve_old(
    real_settings: AgentModelSettings,
    tmp_path: Path,
) -> None:
    """3. 激活失败回滚且旧版本教材数据完好保留测试：

    新版本切片写入后，在 set_payload 阶段模拟失败报错；
    验证新版本临时切片被全部清理，旧版本切片完好无损。
    """
    course_id = f"course_act_fail_{uuid.uuid4().hex[:6]}"
    file_doc = tmp_path / "network.txt"
    file_doc.write_text("第一章 物理层\n\n调制解调与曼彻斯特编码技术详解。", encoding="utf-8")

    # 先成功入库第一版
    cnt1 = asyncio.run(ingest_course_material(file_doc, course_id, real_settings))
    assert cnt1 >= 1

    coll_name = get_course_knowledge_collection_name(real_settings)
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)

    # 验证旧版本已生效
    active_filter = Filter(
        must=[
            FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
            FieldCondition(key="chunk.metadata.is_active", match=MatchValue(value=True)),
        ]
    )
    res_before = asyncio.run(client.count(coll_name, count_filter=active_filter))
    assert res_before.count == cnt1

    # 准备入库第二版，并在 set_payload 激活时注入异常
    file_doc.write_text("第一章 物理层第二版\n\n新增差分曼彻斯特编码与正交频分复用。", encoding="utf-8")

    async def fail_set_payload(self, *args, **kwargs):
        raise ConnectionResetError("Simulated network timeout during set_payload")

    with patch.object(AsyncQdrantClient, "set_payload", new=fail_set_payload):
        with pytest.raises(RuntimeError, match="Failed to activate ingestion version"):
            asyncio.run(ingest_course_material(file_doc, course_id, real_settings))

    # 验证：旧版本切片 100% 完好无损保留！
    try:
        res_after = asyncio.run(client.count(coll_name, count_filter=active_filter))
        assert res_after.count == cnt1

        # 验证：新版本的所有临时切片均已被回滚清除
        inactive_filter = Filter(
            must=[
                FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
                FieldCondition(key="chunk.metadata.is_active", match=MatchValue(value=False)),
            ]
        )
        res_inactive = asyncio.run(client.count(coll_name, count_filter=inactive_filter))
        assert res_inactive.count == 0
    finally:
        asyncio.run(client.close())


def test_real_qdrant_retrieval_strictly_excludes_unactivated_chunks(
    real_settings: AgentModelSettings,
) -> None:
    """4. 检索严格隔离未激活临时切片测试：

    正在写入（is_active=False）的数据绝不被 build_catalog_kg_context 或 retrieve_course_context 召回。
    """
    course_id = f"course_leak_test_{uuid.uuid4().hex[:6]}"
    coll_name = get_course_knowledge_collection_name(real_settings)
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)

    # 确保集合存在
    if not asyncio.run(client.collection_exists(coll_name)):
        asyncio.run(client.create_collection(coll_name, vectors_config=VectorParams(size=real_settings.EMBEDDING_DIMENSION, distance=Distance.COSINE)))

    dummy_vector = DeterministicTestEmbeddingModel(real_settings.EMBEDDING_DIMENSION)._embed_text("考试答案")
    unactivated_id = str(uuid.uuid4())

    # 插入一条明确 is_active=False 的临时点位
    asyncio.run(
        client.upsert(
            coll_name,
            points=[
                PointStruct(
                    id=unactivated_id,
                    vector=dummy_vector,
                    payload={
                        "document_id": "secret_doc_id",
                        "is_active": False,
                        "course_id": course_id,
                        "catalog_id": course_id,
                        "material_id": "secret.txt",
                        "ingestion_version": "unactivated_version_xyz",
                        "chunk": {
                            "content": {"type": "text", "text": "机密未发布考试答案解析段落"},
                            "source": "secret.txt",
                            "chunk_index": 0,
                            "total_chunks": 1,
                            "metadata": {
                                "course_id": course_id,
                                "is_active": False,
                                "ingestion_version": "unactivated_version_xyz",
                                "filename": "secret.txt",
                            },
                        },
                    },
                )
            ],
        )
    )

    # 1. 验证 build_catalog_kg_context 绝不召回未激活数据，而是抛出 CatalogKnowledgeContextEmpty
    with pytest.raises(CatalogKnowledgeContextEmpty):
        asyncio.run(build_catalog_kg_context(course_id, settings=real_settings))

    # 2. 验证 retrieve_course_context 绝不泄露未激活数据，返回 status="empty"
    ret = asyncio.run(retrieve_course_context("考试答案", course_id, settings=real_settings))
    assert ret["status"] == "empty"
    assert ret["sources"] == []
    assert "机密未发布" not in ret["context_text"]

    # 激活该切片后，能够正常检索
    asyncio.run(
        client.set_payload(
            coll_name,
            payload={"is_active": True},
            key="chunk.metadata",
            points=[unactivated_id],
        )
    )
    asyncio.run(
        client.set_payload(
            coll_name,
            payload={"is_active": True},
            points=[unactivated_id],
        )
    )

    try:
        kg_ctx = asyncio.run(build_catalog_kg_context(course_id, settings=real_settings))
        assert "机密未发布考试答案解析段落" in kg_ctx

        ret_after = asyncio.run(retrieve_course_context("考试答案", course_id, settings=real_settings))
        assert ret_after["status"] == "available"
        assert len(ret_after["sources"]) >= 1
        assert "机密未发布考试答案解析段落" in ret_after["sources"][0]["snippet"]
    finally:
        asyncio.run(client.close())


def test_real_qdrant_historical_collection_fallback_query(
    real_settings: AgentModelSettings,
) -> None:
    """5. 历史 Collection 兼容读取测试：

    当模型派生集合未命中，且历史集合（如 course_knowledge_v1_1024）存在且维度匹配时，
    支持透明回退检索。若维度不匹配，则严格拒绝回退。
    """
    course_id = f"course_hist_{uuid.uuid4().hex[:6]}"
    legacy_coll_name = f"course_knowledge_legacy_{uuid.uuid4().hex[:6]}"
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)

    # 1. 创建维度一致 (1024) 的历史集合并写入 legacy 数据
    asyncio.run(
        client.create_collection(
            legacy_coll_name,
            vectors_config=VectorParams(size=real_settings.EMBEDDING_DIMENSION, distance=Distance.COSINE),
        )
    )

    dummy_vector = DeterministicTestEmbeddingModel(real_settings.EMBEDDING_DIMENSION)._embed_text("重要资料")
    asyncio.run(
        client.upsert(
            legacy_coll_name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=dummy_vector,
                    payload={
                        "document_id": "hist_doc_id",
                        "course_id": course_id,
                        "chunk": {
                            "content": {"type": "text", "text": "来自历史旧集合 course_knowledge 的重要资料段落"},
                            "source": "historical_textbook.txt",
                            "chunk_index": 0,
                            "total_chunks": 1,
                            "metadata": {
                                "course_id": course_id,
                                "filename": "historical_textbook.txt",
                            },
                        },
                    },
                )
            ],
        )
    )

    # 配置 settings 的原集合名指向该 legacy 集合
    test_settings = AgentModelSettings(
        QDRANT_URL=real_settings.QDRANT_URL,
        QDRANT_COURSE_KNOWLEDGE_COLLECTION=legacy_coll_name,
        EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5",
        EMBEDDING_DIMENSION=1024,
    )

    # 此时动态派生集合名与 legacy 集合名不同，且派生集合中无数据
    derived_name = get_course_knowledge_collection_name(test_settings)
    assert derived_name != legacy_coll_name

    # 确保派生集合存在但为空
    if not asyncio.run(client.collection_exists(derived_name)):
        asyncio.run(client.create_collection(derived_name, vectors_config=VectorParams(size=1024, distance=Distance.COSINE)))

    try:
        # 验证 build_catalog_kg_context 能够透明回退至历史集合中读取内容
        kg_ctx = asyncio.run(build_catalog_kg_context(course_id, settings=test_settings))
        assert "来自历史旧集合" in kg_ctx

        # 验证 retrieve_course_context 能够透明回退至历史集合检索出引文
        ret = asyncio.run(retrieve_course_context("重要资料", course_id, settings=test_settings))
        assert ret["status"] == "available"
        assert len(ret["sources"]) >= 1
        assert "来自历史旧集合" in ret["sources"][0]["snippet"]

        # 清理历史集合
        asyncio.run(client.delete_collection(legacy_coll_name))
        asyncio.run(client.delete_collection(derived_name))
    finally:
        asyncio.run(client.close())


def test_real_qdrant_same_filename_different_material_id_isolation(
    real_settings: AgentModelSettings,
    tmp_path: Path,
) -> None:
    """6. 同一 Catalog 下同名但 material_id 不同的教材物理隔离测试：

    同一 Catalog 下入库两份物理文件名相同但 material_id 不同的教材，
    两份教材的切片互不影响，各自更新时不误删另一份教材的向量。
    """
    course_id = f"course_same_name_{uuid.uuid4().hex[:6]}"

    dir_a = tmp_path / "mat_a"
    dir_b = tmp_path / "mat_b"
    dir_a.mkdir()
    dir_b.mkdir()

    file_a = dir_a / "textbook.txt"
    file_b = dir_b / "textbook.txt"
    file_a.write_text("第一章 微积分 极限理论与导数计算。", encoding="utf-8")
    file_b.write_text("第一章 线性代数 矩阵行列式与秩计算。", encoding="utf-8")

    mat_id_a = "cmat_001_aaa"
    mat_id_b = "cmat_002_bbb"

    cnt_a = asyncio.run(
        ingest_course_material(file_a, course_id, real_settings, material_id=mat_id_a)
    )
    cnt_b = asyncio.run(
        ingest_course_material(file_b, course_id, real_settings, material_id=mat_id_b)
    )
    assert cnt_a >= 1
    assert cnt_b >= 1

    coll_name = get_course_knowledge_collection_name(real_settings)
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)

    filter_a = Filter(
        must=[
            FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
            FieldCondition(key="chunk.metadata.material_id", match=MatchValue(value=mat_id_a)),
            FieldCondition(key="chunk.metadata.is_active", match=MatchValue(value=True)),
        ]
    )
    filter_b = Filter(
        must=[
            FieldCondition(key="chunk.metadata.course_id", match=MatchValue(value=course_id)),
            FieldCondition(key="chunk.metadata.material_id", match=MatchValue(value=mat_id_b)),
            FieldCondition(key="chunk.metadata.is_active", match=MatchValue(value=True)),
        ]
    )

    res_a = asyncio.run(client.count(coll_name, count_filter=filter_a))
    res_b = asyncio.run(client.count(coll_name, count_filter=filter_b))
    assert res_a.count == cnt_a
    assert res_b.count == cnt_b

    # 更新教材 A 新版本
    file_a.write_text("第一章 微积分修订版 多元微积分与偏导数计算。", encoding="utf-8")
    cnt_a_new = asyncio.run(
        ingest_course_material(file_a, course_id, real_settings, material_id=mat_id_a)
    )
    assert cnt_a_new >= 1

    try:
        # 教材 A 点位数更新为新版本切片数
        res_a_after = asyncio.run(client.count(coll_name, count_filter=filter_a))
        assert res_a_after.count == cnt_a_new

        # 教材 B 点位数保持完好，毫发无损！
        res_b_after = asyncio.run(client.count(coll_name, count_filter=filter_b))
        assert res_b_after.count == cnt_b
    finally:
        asyncio.run(client.close())


def test_historical_collection_rejects_incompatible_model_even_same_dimension(
    real_settings: AgentModelSettings,
) -> None:
    """7. 历史 Collection 回退逻辑在维度相同但模型不同时严格拒绝回退。"""
    from agent_service_v2.tools.rag import _get_historical_fallback_collection

    legacy_coll_name = f"course_knowledge_v1_{uuid.uuid4().hex[:6]}"
    client = AsyncQdrantClient(url=real_settings.QDRANT_URL, check_compatibility=False)

    # 创建 1024 维历史集合
    asyncio.run(
        client.create_collection(
            legacy_coll_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
    )

    try:
        # 1. 维度同为 1024，但模型不兼容（如 custom-1024 / bge-m3），拒绝回退返回 None
        incompatible_settings = AgentModelSettings(
            QDRANT_URL=real_settings.QDRANT_URL,
            QDRANT_COURSE_KNOWLEDGE_COLLECTION=legacy_coll_name,
            EMBEDDING_MODEL="custom-incompatible-model-1024",
            EMBEDDING_DIMENSION=1024,
        )
        target_name = get_course_knowledge_collection_name(incompatible_settings)
        fallback = asyncio.run(
            _get_historical_fallback_collection(client, incompatible_settings, target_name)
        )
        assert fallback is None, "Incompatible model must be rejected from historical fallback"

        # 2. 模型为兼容 baseline 模型（BAAI/bge-large-zh-v1.5），允许回退
        compatible_settings = AgentModelSettings(
            QDRANT_URL=real_settings.QDRANT_URL,
            QDRANT_COURSE_KNOWLEDGE_COLLECTION=legacy_coll_name,
            EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5",
            EMBEDDING_DIMENSION=1024,
        )
        comp_target_name = get_course_knowledge_collection_name(compatible_settings)
        fallback_ok = asyncio.run(
            _get_historical_fallback_collection(client, compatible_settings, comp_target_name)
        )
        assert fallback_ok == legacy_coll_name

        # 3. 显式白名单机制生效
        whitelist_settings = AgentModelSettings(
            QDRANT_URL=real_settings.QDRANT_URL,
            QDRANT_COURSE_KNOWLEDGE_COLLECTION=legacy_coll_name,
            EMBEDDING_MODEL="custom-incompatible-model-1024",
            EMBEDDING_DIMENSION=1024,
            HISTORICAL_FALLBACK_COMPATIBLE_MODELS=["custom-incompatible-model-1024"],
        )
        fallback_wl = asyncio.run(
            _get_historical_fallback_collection(client, whitelist_settings, target_name)
        )
        assert fallback_wl == legacy_coll_name
    finally:
        asyncio.run(client.delete_collection(legacy_coll_name))
        asyncio.run(client.close())
