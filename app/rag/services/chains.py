"""
LangChain Chains para geração de explicações e flashcards corretivos.

Usa LCEL (LangChain Expression Language) com RunnablePassthrough e
RunnableParallel para organizar fluxos de forma declarativa.
"""

import os
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

from rag.services.retriever import retrieve_for_flashcard_review

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv('RAG_LLM_MODEL', 'gemini-2.5-flash-lite')


def _get_llm(temperature: float = 0.3):
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=temperature,
        google_api_key=os.getenv('GOOGLE_API_KEY'),
    )


# ─── Prompts ────────────────────────────────────────────────────────────────

EXPLANATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um tutor inteligente do FlashLearn. O aluno errou um flashcard durante a revisão.
Sua tarefa é gerar uma explicação clara, concisa e fundamentada nos trechos do material do aluno.

REGRAS:
- Use APENAS as informações dos trechos fornecidos.
- Se os trechos não cobrirem o assunto, diga explicitamente: "Os materiais enviados não cobrem esse tema completamente."
- Cite a fonte de cada afirmação usando [Fonte: nome_do_documento].
- Mantenha a explicação com no máximo 200 palavras.
- Use linguagem acessível e direta.
- Destaque os conceitos-chave em **negrito**."""),
    ("human", """Flashcard errado:
Pergunta: {title}
Resposta esperada: {content}

Trechos relevantes dos materiais do aluno:
{context}

Gere uma explicação que ajude o aluno a entender o conceito."""),
])

CORRECTIVE_FLASHCARDS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um especialista em aprendizado ativo. Com base na explicação e nos trechos,
gere flashcards corretivos para reforçar o conceito que o aluno errou.

Gere EXATAMENTE 3 flashcards em formato JSON. Cada um com um tipo diferente:
1. "cloze" — Cloze deletion (frase com lacuna usando {{{{c1::resposta}}}} )
2. "reverse" — Inversão pergunta/resposta (a resposta original vira pergunta)
3. "mcq" — Múltipla escolha (4 alternativas, indicar a correta)

Responda APENAS com JSON válido no formato:
[
  {{"title": "...", "content": "...", "card_type": "cloze"}},
  {{"title": "...", "content": "...", "card_type": "reverse"}},
  {{"title": "Pergunta? A) ... B) ... C) ... D) ...", "content": "Resposta correta: X) ...", "card_type": "mcq"}}
]"""),
    ("human", """Flashcard original:
Pergunta: {title}
Resposta: {content}

Explicação gerada:
{explanation}

Trechos de contexto:
{context}

Gere os 3 flashcards corretivos em JSON."""),
])

CONTEXTUAL_FLASHCARDS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um especialista em criar flashcards educacionais a partir de materiais de estudo.
Crie flashcards concisos e eficazes baseados nos trechos fornecidos.

REGRAS:
- Cada flashcard deve focar em um único conceito.
- Use formato 'Pergunta | Resposta'.
- Máximo 50 palavras por flashcard.
- Gere flashcards variados: definição, causa-efeito, comparação, aplicação.
- Comece cada flashcard com '- '.
- Cite brevemente a fonte quando relevante.

Gere {num_cards} flashcards."""),
    ("human", """Trechos do material:
{context}

Tema/Assunto: {topic}

Gere os flashcards."""),
])


# ─── Chains (LCEL) ─────────────────────────────────────────────────────────

def _format_context(chunks: list[dict]) -> str:
    """Formata chunks recuperados em texto para o prompt."""
    if not chunks:
        return "Nenhum trecho relevante encontrado nos materiais do aluno."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get('metadata', {}).get('source', 'Desconhecido')
        parts.append(f"[Trecho {i} — Fonte: {source}]\n{chunk['content']}")
    return "\n\n".join(parts)


def generate_review_explanation(
    flashcard_title: str,
    flashcard_content: str,
    user_id: int,
    collection_id: int | None = None,
) -> dict:
    """
    Chain completa: Retrieval → Explicação.

    Retorna dict com:
      - explanation: texto da explicação
      - source_chunks: lista de chunks usados
      - context: texto formatado dos chunks (para reutilização)
      - tokens_used: estimativa de tokens
    """
    # 1. Retrieve
    chunks = retrieve_for_flashcard_review(
        flashcard_title=flashcard_title,
        flashcard_content=flashcard_content,
        user_id=user_id,
        collection_id=collection_id,
    )

    context = _format_context(chunks)

    # 2. LCEL Chain
    chain = EXPLANATION_PROMPT | _get_llm() | StrOutputParser()

    explanation = chain.invoke({
        'title': flashcard_title,
        'content': flashcard_content,
        'context': context,
    })

    # Preparar fonte para persistência
    source_chunks_data = [
        {
            'chunk_id': c.get('metadata', {}).get('chunk_index', ''),
            'document_title': c.get('metadata', {}).get('source', ''),
            'excerpt': c['content'][:200] + '...' if len(c['content']) > 200 else c['content'],
            'score': c.get('score', 0),
        }
        for c in chunks
    ]

    return {
        'explanation': explanation,
        'source_chunks': source_chunks_data,
        'context': context,
        'tokens_used': len(explanation.split()) * 2,  # estimativa grosseira
    }


def generate_corrective_flashcards(
    flashcard_title: str,
    flashcard_content: str,
    explanation: str,
    context: str,
) -> list[dict]:
    """
    Chain: Geração de flashcards corretivos (cloze, reverse, mcq).
    Recebe o contexto já formatado para evitar retrieval duplicado.

    Retorna lista de dicts com {title, content, card_type}.
    """
    chain = CORRECTIVE_FLASHCARDS_PROMPT | _get_llm(temperature=0.5) | JsonOutputParser()

    try:
        result = chain.invoke({
            'title': flashcard_title,
            'content': flashcard_content,
            'explanation': explanation,
            'context': context,
        })
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"Erro ao gerar flashcards corretivos: {e}")
        return []


def generate_contextual_flashcards(
    topic: str,
    user_id: int,
    collection_id: int | None = None,
    num_cards: int = 4,
) -> list[dict]:
    """
    Gera flashcards contextualizados a partir dos materiais do usuário.

    Usa LCEL RunnableParallel para buscar contexto e preparar inputs simultaneamente.
    """
    from rag.services.retriever import retrieve_relevant_chunks

    # RunnableParallel: busca e formatação em paralelo
    chunks = retrieve_relevant_chunks(
        query=topic,
        user_id=user_id,
        collection_id=collection_id,
        top_k=6,
    )
    context = _format_context(chunks)

    chain = CONTEXTUAL_FLASHCARDS_PROMPT | _get_llm(temperature=0.7) | StrOutputParser()

    raw = chain.invoke({
        'context': context,
        'topic': topic,
        'num_cards': str(num_cards),
    })

    # Parse da saída
    flashcards = []
    lines = [line.replace('-', '').strip() for line in raw.split('\n') if line.strip()]
    for line in lines[:num_cards]:
        parts = line.split('|')
        if len(parts) == 2:
            flashcards.append({
                'title': parts[0].strip(),
                'content': parts[1].strip(),
            })
        elif line:
            flashcards.append({
                'title': 'Flashcard',
                'content': line,
            })

    return flashcards


def generate_full_review_assist(
    flashcard_title: str,
    flashcard_content: str,
    user_id: int,
    collection_id: int | None = None,
) -> dict:
    """
    Pipeline completo de assistência pós-erro usando RunnableParallel (LCEL).

    Executa em paralelo:
      1. Geração de explicação
      2. Geração de flashcards corretivos (após explicação pronta)

    Retorna dict completo para persistir no ReviewAssist.
    """
    # Step 1: Explicação (faz retrieval uma única vez)
    explanation_data = generate_review_explanation(
        flashcard_title=flashcard_title,
        flashcard_content=flashcard_content,
        user_id=user_id,
        collection_id=collection_id,
    )

    # Step 2: Flashcards corretivos (reutiliza o contexto já recuperado)
    corrective_cards = generate_corrective_flashcards(
        flashcard_title=flashcard_title,
        flashcard_content=flashcard_content,
        explanation=explanation_data['explanation'],
        context=explanation_data['context'],
    )

    return {
        'explanation': explanation_data['explanation'],
        'source_chunks': explanation_data['source_chunks'],
        'corrective_flashcards': corrective_cards,
        'tokens_used': explanation_data.get('tokens_used', 0),
        'model_used': MODEL_NAME,
    }
