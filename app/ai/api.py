import os
import logging
from google import genai

logger = logging.getLogger(__name__)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# ─── Limites de tokens para economia ────────────────────────────────────
MAX_INPUT_CHARS = 3000      # ~750 tokens — suficiente para extrair 4 flashcards
MAX_OUTPUT_TOKENS = 400     # 4 flashcards cabem em ~200 tokens


def generate_flashcards(text: str) -> list[dict]:
    """
    Gera flashcards a partir de um texto usando a API do Google Gemini.
    O texto de entrada é truncado para economizar tokens.
    """
    # Truncar texto para limitar custo
    text = text[:MAX_INPUT_CHARS].strip()

    if not text:
        raise ValueError("Texto vazio — envie um arquivo com conteúdo.")

    prompt = (
        "Crie exatamente 4 flashcards a partir do texto abaixo.\n"
        "Regras:\n"
        "- Formato: 'Pergunta | Resposta'\n"
        "- Cada flashcard em uma linha, começando com '- '\n"
        "- Máximo 50 palavras por flashcard\n"
        "- Uma única ideia principal por flashcard\n"
        "- Linguagem simples e direta\n\n"
        f"Texto:\n{text}"
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config={
                'temperature': 0.7,
                'max_output_tokens': MAX_OUTPUT_TOKENS,
            },
        )

        return _parse_flashcards(response.text)

    except Exception as e:
        raise Exception(f"Erro ao gerar flashcards: {e}")


def _parse_flashcards(raw: str) -> list[dict]:
    """Faz o parse da resposta da API em uma lista de dicts {title, content}."""
    lines = [
        line.lstrip('-').strip()
        for line in raw.split('\n')
        if line.strip()
    ][:4]

    flashcards = []
    for line in lines:
        parts = line.split('|', 1)
        if len(parts) == 2:
            flashcards.append({
                'title': parts[0].strip(),
                'content': parts[1].strip(),
            })
        else:
            flashcards.append({
                'title': 'Flashcard',
                'content': line,
            })

    return flashcards
