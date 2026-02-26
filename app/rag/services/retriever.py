"""
Retriever com filtros por usuário e coleção.

Encapsula a busca vetorial no ChromaDB com filtros de metadados,
permitindo recuperar apenas chunks relevantes ao contexto do usuário.
"""

import os
import logging
from typing import Optional

from django.conf import settings

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

logger = logging.getLogger(__name__)

CHROMA_PERSIST_DIR = getattr(
    settings, 'CHROMA_PERSIST_DIR',
    os.path.join(settings.BASE_DIR, 'chroma_db')
)
EMBEDDING_MODEL = getattr(settings, 'RAG_EMBEDDING_MODEL', 'models/gemini-embedding-001')
CHROMA_COLLECTION = getattr(settings, 'RAG_CHROMA_COLLECTION', 'flashlearn_docs')


def _get_vectorstore():
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=os.getenv('GOOGLE_API_KEY'),
    )
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )


def retrieve_relevant_chunks(
    query: str,
    user_id: int,
    collection_id: Optional[int] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Busca os chunks mais relevantes para uma query, filtrados por usuário e coleção.

    Args:
        query: texto da pergunta/flashcard.
        user_id: ID do usuário (filtro obrigatório).
        collection_id: ID da coleção (filtro opcional, restringe a uma matéria).
        top_k: número máximo de resultados.

    Returns:
        Lista de dicts com:
          - content: texto do chunk
          - metadata: metadados do ChromaDB
          - score: similaridade (menor = mais relevante no L2)
    """
    vectorstore = _get_vectorstore()

    # Montar filtro de metadados para o ChromaDB
    where_filter = {"user_id": user_id}
    if collection_id:
        where_filter = {
            "$and": [
                {"user_id": user_id},
                {"collection_id": collection_id},
            ]
        }

    try:
        results = vectorstore.similarity_search_with_score(
            query=query,
            k=top_k,
            filter=where_filter,
        )

        retrieved = []
        for doc, score in results:
            retrieved.append({
                'content': doc.page_content,
                'metadata': doc.metadata,
                'score': float(score),
            })

        logger.info(
            f"Recuperados {len(retrieved)} chunks para user_id={user_id}, "
            f"collection_id={collection_id}"
        )
        return retrieved

    except Exception as e:
        logger.error(f"Erro na recuperação de chunks: {e}")
        return []


def retrieve_for_flashcard_review(
    flashcard_title: str,
    flashcard_content: str,
    user_id: int,
    collection_id: Optional[int] = None,
    top_k: int = 4,
) -> list[dict]:
    """
    Recupera chunks relevantes para assistência pós-erro em flashcard.
    Combina título e conteúdo do flashcard como query de busca.
    """
    query = f"{flashcard_title}\n{flashcard_content}"
    return retrieve_relevant_chunks(
        query=query,
        user_id=user_id,
        collection_id=collection_id,
        top_k=top_k,
    )
