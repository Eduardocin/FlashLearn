"""
Agente de chat para o modo estudo do FlashLearn.

Usa LangGraph (create_react_agent) com 4 ferramentas:
  - search_docs        — pesquisa semântica nos materiais do aluno
  - get_my_flashcards  — lista flashcards do aluno por tópico
  - create_flashcard   — cria novo flashcard durante a conversa
  - get_study_summary  — resumo de progresso e estatísticas de revisão

O contexto do usuário (user_id, collection_id) é injetado via
RunnableConfig['configurable'] de forma thread-safe, sem estado global.
"""

import logging
import os
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from .retriever import retrieve_relevant_chunks

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("RAG_LLM_MODEL", "gemini-2.5-flash-lite")

# ─── Ferramentas ─────────────────────────────────────────────────────────────

@tool
def search_docs(query: str, config: RunnableConfig) -> str:
    """
    Pesquisa informações relevantes nos materiais de estudo enviados pelo aluno.
    Use esta ferramenta sempre que a pergunta envolver conceitos, definições ou
    conteúdo que possa estar nos documentos do usuário.
    """
    cfg = config.get("configurable", {})
    user_id = cfg.get("user_id")
    collection_id = cfg.get("collection_id")

    if not user_id:
        return "Erro interno: contexto do usuário não disponível."

    chunks = retrieve_relevant_chunks(
        query=query,
        user_id=user_id,
        collection_id=collection_id,
        top_k=4,
    )

    if not chunks:
        return "Nenhum trecho relevante encontrado nos materiais para esta consulta."

    parts = []
    for c in chunks:
        title = c["metadata"].get("document_title", "Material")
        parts.append(f"[Fonte: {title}]\n{c['content']}")

    return "\n\n---\n\n".join(parts)


@tool
def get_my_flashcards(topic: str, config: RunnableConfig) -> str:
    """
    Lista os flashcards do aluno. Informe um tópico para filtrar por título ou
    conteúdo. Deixe em branco para listar os 10 mais recentes.
    """
    from flashcards.models import UserFlashcard  # import local p/ evitar import circular

    cfg = config.get("configurable", {})
    user_id = cfg.get("user_id")

    if not user_id:
        return "Erro interno: contexto do usuário não disponível."

    qs = UserFlashcard.objects.filter(user_id=user_id)
    if topic:
        from django.db.models import Q
        qs = qs.filter(Q(title__icontains=topic) | Q(content__icontains=topic))

    cards = list(qs[:10])

    if not cards:
        msg = f"Nenhum flashcard encontrado sobre '{topic}'." if topic else "Você ainda não tem flashcards."
        return msg

    lines = []
    for c in cards:
        excerpt = c.content[:100] + "…" if len(c.content) > 100 else c.content
        lines.append(f"• [{c.card_type}] {c.title}: {excerpt}")

    header = f"Flashcards encontrados ({len(lines)}):\n"
    return header + "\n".join(lines)


@tool
def create_flashcard(
    title: str,
    content: str,
    config: RunnableConfig,
    card_type: str = "standard",
) -> str:
    """
    Cria um novo flashcard para o aluno com título e conteúdo fornecidos.
    card_type pode ser: 'standard', 'cloze', 'reverse' ou 'mcq'.
    Use quando o aluno pedir para salvar algo como flashcard.
    """
    from django.contrib.auth.models import User
    from flashcards.models import UserFlashcard

    cfg = config.get("configurable", {})
    user_id = cfg.get("user_id")
    collection_id = cfg.get("collection_id")

    if not user_id:
        return "Erro interno: contexto do usuário não disponível."

    valid_types = {"standard", "cloze", "reverse", "mcq"}
    if card_type not in valid_types:
        card_type = "standard"

    try:
        user = User.objects.get(id=user_id)
        fc = UserFlashcard.objects.create(
            user=user,
            title=title,
            content=content,
            card_type=card_type,
            collection_id=collection_id if collection_id else None,
        )
        type_label = dict(UserFlashcard.CARD_TYPE_CHOICES).get(card_type, card_type)
        return (
            f"Flashcard criado com sucesso!\n"
            f"  Título: {fc.title}\n"
            f"  Tipo: {type_label}\n"
            f"  ID: {fc.id}"
        )
    except Exception as e:
        logger.error(f"Erro ao criar flashcard via agente: {e}")
        return "Não foi possível criar o flashcard. Tente novamente."


@tool
def get_study_summary(config: RunnableConfig) -> str:
    """
    Retorna um resumo do progresso de estudo do aluno: total de flashcards,
    revisões realizadas, taxa de acerto e flashcards não revisados.
    Use quando o aluno perguntar sobre seu progresso ou desempenho.
    """
    from flashcards.models import ReviewLog, UserFlashcard

    cfg = config.get("configurable", {})
    user_id = cfg.get("user_id")

    if not user_id:
        return "Erro interno: contexto do usuário não disponível."

    total = UserFlashcard.objects.filter(user_id=user_id).count()
    total_reviews = ReviewLog.objects.filter(user_id=user_id).count()
    correct = ReviewLog.objects.filter(user_id=user_id, is_correct=True).count()

    if total_reviews > 0:
        accuracy = f"{correct / total_reviews * 100:.1f}%"
        wrong = total_reviews - correct
    else:
        accuracy = "sem revisões ainda"
        wrong = 0

    return (
        f"Resumo do seu progresso:\n"
        f"  Flashcards cadastrados: {total}\n"
        f"  Revisões realizadas: {total_reviews}\n"
        f"  Acertos: {correct}  |  Erros: {wrong}\n"
        f"  Taxa de acerto: {accuracy}"
    )


# ─── Agente ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Você é um tutor inteligente do FlashLearn, especializado em ajudar alunos "
    "a estudar de forma eficaz e personalizada.\n\n"
    "Ferramentas disponíveis:\n"
    "  • search_docs — pesquisa nos materiais enviados pelo aluno\n"
    "  • get_my_flashcards — lista flashcards existentes por tópico\n"
    "  • create_flashcard — salva um novo flashcard para o aluno\n"
    "  • get_study_summary — exibe estatísticas de progresso\n\n"
    "Diretrizes:\n"
    "  - Sempre responda em português brasileiro, de forma clara e didática.\n"
    "  - Use search_docs antes de responder perguntas sobre conteúdo de estudo.\n"
    "  - Quando criar um flashcard, confirme ao aluno o título e um trecho do conteúdo.\n"
    "  - Se não houver material relevante, responda com seu conhecimento geral e avise.\n"
    "  - Mantenha respostas objetivas; aprofunde quando o aluno pedir."
)

_agent = None


def _build_agent():
    """Instancia o agente ReAct com Gemini + ferramentas."""
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0.4,
        max_output_tokens=800,
    )
    tools = [search_docs, get_my_flashcards, create_flashcard, get_study_summary]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def _get_agent():
    """Retorna instância singleton do agente (lazy init)."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


# ─── Interface pública ────────────────────────────────────────────────────────

def run_chat_agent(
    message: str,
    user_id: int,
    collection_id: Optional[int],
    history: list[dict],
) -> dict:
    """
    Executa o agente LangGraph para uma mensagem do aluno.

    Args:
        message: Mensagem atual do aluno.
        user_id: ID do usuário Django autenticado.
        collection_id: ID da coleção selecionada (ou None).
        history: Histórico anterior no formato [{'role': 'user'|'assistant', 'content': str}].

    Returns:
        {'answer': str, 'tools_used': list[str]}
    """
    # Converter histórico para mensagens LangChain
    messages = []
    for item in history[-8:]:  # limita a 8 trocas de histórico
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        else:
            messages.append(AIMessage(content=item["content"]))

    messages.append(HumanMessage(content=message))

    config = {
        "configurable": {
            "user_id": user_id,
            "collection_id": collection_id,
        }
    }

    agent = _get_agent()

    try:
        result = agent.invoke({"messages": messages}, config=config)
    except Exception as e:
        logger.error(f"Erro ao executar agente LangGraph: {e}")
        raise

    # Extrair resposta final (última mensagem AI)
    final_msg = result["messages"][-1]
    answer = final_msg.content if hasattr(final_msg, "content") else str(final_msg)

    # Coletar nomes das ferramentas usadas nesta rodada
    tools_used: list[str] = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if name and name not in tools_used:
                    tools_used.append(name)

    return {"answer": answer, "tools_used": tools_used}
