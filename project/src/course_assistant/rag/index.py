"""Chunk the course knowledge base and persist its local FAISS vector index."""

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from course_assistant.rag.config import load_config, load_environment, project_root
from course_assistant.rag.knowledge import (
    knowledge_base_path,
    load_knowledge_data,
)

if TYPE_CHECKING:
    from langchain_openai import OpenAIEmbeddings
    from langchain_community.vectorstores import FAISS

_DOCUMENT_STRATEGY = "course_sections_v1"


def _embeddings(config: dict[str, Any]) -> "OpenAIEmbeddings":
    from langchain_openai import OpenAIEmbeddings

    load_environment()
    return OpenAIEmbeddings(model=config["embedding_model"])


def _index_path(config: dict[str, Any]) -> Path:
    configured_path = Path(config["index_path"])
    if not configured_path.is_absolute():
        configured_path = project_root() / configured_path
    return configured_path


def _manifest(config: dict[str, Any]) -> dict[str, Any]:
    source_hash = hashlib.sha256(knowledge_base_path().read_bytes()).hexdigest()
    return {
        "knowledge_base_sha256": source_hash,
        "embedding_model": config["embedding_model"],
        "document_strategy": _DOCUMENT_STRATEGY,
    }


def _build_vector_store(
    kb_data: Dict[str, Any],
    index_dir: Optional[Union[str, Path]] = None,
    *,
    config: Optional[dict[str, Any]] = None,
) -> "FAISS":
    """Create one semantically grouped vector document per knowledge-base item."""
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document

    documents: list[Document] = []

    course = kb_data.get("course_info", {})
    if course:
        documents.append(
            Document(
                page_content=(
                    f"Thông tin môn học {course.get('course_name')} "
                    f"({course.get('course_id')}): "
                    f"Số tín chỉ: {course.get('credits')}. "
                    f"Giảng viên: {course.get('instructor')}. "
                    f"Mô tả: {course.get('course_description')}"
                ),
                metadata={"source": "course_info"},
            )
        )

    weeks = kb_data.get("schedule", {}).get("weeks", {})
    for week_id, week in weeks.items():
        topics = ", ".join(week.get("topics", []))
        text = (
            f"Lịch học Tuần {week_id} (Chương {week.get('chapter', '')}): "
            f"Chủ đề học bao gồm {topics}."
        )
        if week.get("milestone"):
            text += f" Cột mốc quan trọng: {week['milestone']}."
        documents.append(
            Document(
                page_content=text,
                metadata={"source": "schedule", "week": str(week_id)},
            )
        )

    for chapter_id, chapter in kb_data.get("topics", {}).items():
        keywords = ", ".join(chapter.get("keywords", []))
        documents.append(
            Document(
                page_content=(
                    f"Chương {chapter.get('num')}: {chapter.get('title')}. "
                    f"Từ khóa: {keywords}. "
                    f"Tóm tắt: {chapter.get('summary')}"
                ),
                metadata={"source": "topics", "chapter": chapter_id},
            )
        )

    assignment = kb_data.get("assignments", {})
    overview = assignment.get("overview", {})
    if overview:
        documents.append(
            Document(
                page_content=(
                    f"Thông tin Bài tập lớn ({overview.get('assignment_id')}): "
                    f"Tên: {overview.get('title')}. "
                    f"Hạn nộp/Deadline: {overview.get('deadline')}. "
                    f"Nhóm: {overview.get('team_size')}. "
                    f"Mục tiêu: {overview.get('goal')}"
                ),
                metadata={"source": "assignments_overview"},
            )
        )

    for part_id, part in assignment.get("parts", {}).items():
        requirements = part.get(
            "requirements",
            part.get("minimum_requirements", []),
        )
        requirement_text = ", ".join(str(item) for item in requirements)
        documents.append(
            Document(
                page_content=(
                    f"Bài tập lớn Phần {part.get('roman', '')} - "
                    f"{part.get('title')}: Yêu cầu gồm {requirement_text}."
                ),
                metadata={"source": "assignments_part", "part": part_id},
            )
        )

    for item in kb_data.get("faq", []):
        documents.append(
            Document(
                page_content=(
                    f"Câu hỏi: {item.get('question')}\n"
                    f"Trả lời: {item.get('answer')}"
                ),
                metadata={"source": "faq", "id": item.get("id")},
            )
        )

    for regulation_key, regulation_value in kb_data.get("regulations", {}).items():
        documents.append(
            Document(
                page_content=(
                    f"Quy định môn học về {regulation_key}: {regulation_value}"
                ),
                metadata={"source": "regulations", "key": regulation_key},
            )
        )

    if not documents:
        raise ValueError("Cannot build a vector index from an empty knowledge base.")

    vector_store = FAISS.from_documents(
        documents=documents,
        embedding=_embeddings(config or load_config()),
    )
    if index_dir is not None:
        index_path = Path(index_dir)
        index_path.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(index_path))
    return vector_store


def build_index(config: dict[str, Any] | None = None) -> "FAISS":
    """Build and persist a fresh FAISS index from the current knowledge base."""
    config = config or load_config()
    index_path = _index_path(config)
    vector_store = _build_vector_store(
        dict(load_knowledge_data()),
        index_path,
        config=config,
    )
    (index_path / "manifest.json").write_text(
        json.dumps(_manifest(config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return vector_store


def load_index(config: dict[str, Any] | None = None) -> "FAISS":
    """Load a current local index, rebuilding it when its source/config changed."""
    from langchain_community.vectorstores import FAISS

    config = config or load_config()
    index_path = _index_path(config)
    manifest_path = index_path / "manifest.json"
    index_files_exist = (index_path / "index.faiss").is_file() and (
        index_path / "index.pkl"
    ).is_file()

    if manifest_path.is_file() and index_files_exist:
        with manifest_path.open(encoding="utf-8") as manifest_file:
            saved_manifest = json.load(manifest_file)
        if saved_manifest == _manifest(config):
            return FAISS.load_local(
                str(index_path),
                _embeddings(config),
                allow_dangerous_deserialization=True,
            )

    return build_index(config)
