"""
Pipeline de ingestão de documentos para RAG.

Responsabilidades:
  1. Carregar texto de arquivos (PDF, TXT, Markdown) usando LangChain loaders
  2. Dividir texto em chunks com overlap
  3. Gerar embeddings via Google Gemini
  4. Armazenar vetores no ChromaDB
  5. Persistir metadados no Django ORM (Document, DocumentChunk)
"""

import os
import uuid
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from langchain_community.document_loaders import (
    PyMuPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

from rag.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

# ─── Configurações ──────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = getattr(
    settings, 'CHROMA_PERSIST_DIR',
    os.path.join(settings.BASE_DIR, 'chroma_db')
)

CHUNK_SIZE = getattr(settings, 'RAG_CHUNK_SIZE', 800)
CHUNK_OVERLAP = getattr(settings, 'RAG_CHUNK_OVERLAP', 200)
EMBEDDING_MODEL = getattr(settings, 'RAG_EMBEDDING_MODEL', 'models/gemini-embedding-001')
CHROMA_COLLECTION = getattr(settings, 'RAG_CHROMA_COLLECTION', 'flashlearn_docs')


# ─── Helpers ────────────────────────────────────────────────────────────────

def _get_embeddings():
    """Retorna instância de GoogleGenerativeAIEmbeddings."""
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=os.getenv('GOOGLE_API_KEY'),
    )


def _get_vectorstore():
    """Retorna instância do Chroma com persistência local."""
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


def _get_loader(file_path: str, file_type: str):
    """Seleciona o loader LangChain adequado ao tipo de arquivo."""
    loaders = {
        'pdf': PyMuPDFLoader,
        'txt': TextLoader,
        'md': UnstructuredMarkdownLoader,
    }
    loader_cls = loaders.get(file_type)
    if not loader_cls:
        raise ValueError(f"Tipo de arquivo não suportado: {file_type}")

    if file_type == 'txt':
        return loader_cls(file_path, encoding='utf-8', autodetect_encoding=True)
    return loader_cls(file_path)


def _get_text_splitter():
    """Retorna o text splitter configurado com chunk_size e overlap."""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


# ─── Pipeline Principal ────────────────────────────────────────────────────

def ingest_document(document: Document) -> int:
    """
    Pipeline completo de ingestão de um documento.

    1. Atualiza status para 'processing'
    2. Carrega texto com LangChain loader
    3. Divide em chunks
    4. Gera embeddings e armazena no ChromaDB
    5. Salva metadados dos chunks no Django ORM
    6. Atualiza status para 'completed'

    Args:
        document: instância do model Document já salva com arquivo em disco

    Returns:
        Número de chunks criados

    Raises:
        Exception: qualquer erro durante a ingestão (status muda para 'failed')
    """
    document.status = 'processing'
    document.save(update_fields=['status'])

    try:
        # 1. Carregar texto
        file_path = document.file.path
        loader = _get_loader(file_path, document.file_type)
        raw_docs = loader.load()

        if not raw_docs:
            raise ValueError("Nenhum conteúdo extraído do documento.")

        # 2. Split em chunks
        splitter = _get_text_splitter()
        chunks = splitter.split_documents(raw_docs)

        if not chunks:
            raise ValueError("Nenhum chunk gerado após splitting.")

        # 3. Preparar dados para ChromaDB
        vectorstore = _get_vectorstore()
        texts = []
        metadatas = []
        ids = []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"doc_{document.id}_chunk_{idx}_{uuid.uuid4().hex[:8]}"
            texts.append(chunk.page_content)
            metadatas.append({
                'document_id': document.id,
                'collection_id': document.collection_id,
                'user_id': document.user_id,
                'chunk_index': idx,
                'source': document.title,
                'file_type': document.file_type,
            })
            ids.append(chunk_id)

        # 4. Adicionar ao ChromaDB em uma única chamada
        vectorstore = _get_vectorstore()
        vectorstore.add_texts(
            texts=texts,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Adicionados {len(texts)} chunks ao ChromaDB.")

        # 5. Salvar chunks no ORM
        chunk_objects = []
        for idx, (text, chunk_id) in enumerate(zip(texts, ids)):
            chunk_objects.append(
                DocumentChunk(
                    document=document,
                    chunk_index=idx,
                    content=text,
                    char_count=len(text),
                    embedding_id=chunk_id,
                    metadata=metadatas[idx],
                )
            )
        DocumentChunk.objects.bulk_create(chunk_objects)

        # 6. Atualizar documento
        document.status = 'completed'
        document.total_chunks = len(chunks)
        document.processed_at = timezone.now()
        document.save(update_fields=['status', 'total_chunks', 'processed_at'])

        logger.info(
            f"Documento '{document.title}' ingerido: {len(chunks)} chunks criados."
        )
        return len(chunks)

    except Exception as e:
        document.status = 'failed'
        document.error_message = str(e)
        document.save(update_fields=['status', 'error_message'])
        logger.error(f"Erro ao ingerir documento '{document.title}': {e}")
        raise


def delete_document_vectors(document: Document):
    """
    Remove todos os vetores de um documento do ChromaDB.
    Chamado antes de deletar o documento no ORM.
    """
    try:
        vectorstore = _get_vectorstore()
        chunk_ids = list(
            document.chunks.values_list('embedding_id', flat=True)
        )
        if chunk_ids:
            vectorstore._collection.delete(ids=chunk_ids)
            logger.info(f"Removidos {len(chunk_ids)} vetores do documento '{document.title}'.")
    except Exception as e:
        logger.error(f"Erro ao remover vetores do documento '{document.title}': {e}")


def reprocess_document(document: Document) -> int:
    """
    Reprocessa um documento: remove chunks antigos e executa ingestão novamente.
    """
    delete_document_vectors(document)
    document.chunks.all().delete()
    return ingest_document(document)
