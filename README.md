# FlashLearn
### Plataforma de Flashcards com IA e RAG

O **FlashLearn** é uma plataforma web de estudo que utiliza **Inteligência Artificial** e **Retrieval-Augmented Generation (RAG)** para gerar, organizar e revisar flashcards de forma contextualizada. Envie seus materiais de estudo, e a IA cria flashcards automaticamente — com modo de estudo interativo, revisão inteligente e explicações baseadas nos seus próprios documentos.

---

## 📃 Índice

1. [✨ Funcionalidades](#-funcionalidades)
2. [🏗️ Arquitetura](#️-arquitetura)
3. [🔧 Tecnologias Utilizadas](#-tecnologias-utilizadas)
4. [⚙️ Requisitos](#️-requisitos)
5. [📦 Instalação](#-instruções-de-instalação)
6. [🔑 Configuração da API](#-configuração-da-api)
7. [➡️ Instruções de Uso](#️-instruções-de-uso)
8. [📌 Status do Projeto](#-status-do-projeto)
9. [🤝 Diretrizes para Contribuição](#-diretrizes-para-contribuição)
10. [👥 Equipe de Desenvolvimento](#-equipe-de-desenvolvimento)

---

## ✨ Funcionalidades

### Geração de Flashcards com IA
- **Upload de arquivo** (PDF, TXT, DOCX) → IA gera flashcards automaticamente via Google Gemini
- Tipos de card: **padrão**, **cloze** (lacunas), **reverso** e **múltipla escolha**
- Edição inline com auto-save via AJAX
- Download dos flashcards em **PDF**
- Criação com ou sem sessão de estudo vinculada

### Sessões de Estudo (Coleções RAG)
- Organize materiais em **coleções temáticas** (ex: "Cálculo I", "Biologia")
- Faça **upload de documentos** (PDF, TXT, Markdown) por coleção
- Pipeline de ingestão: chunking → embeddings (Gemini) → ChromaDB
- Visualize chunks, status de processamento e metadados por documento

### Estudo com RAG
- **Modo Estudo**: sessão interativa com flip cards e avaliação de confiança
- **Revisão Inteligente**: ao errar, a IA busca contexto nos seus documentos e gera explicações detalhadas
- **Flashcards Corretivos**: a IA propõe novos cards para reforçar pontos fracos
- **IA Contextual**: gera flashcards diretamente a partir dos documentos de uma coleção
- **Chat de estudo**: converse com a IA sobre o conteúdo da coleção

### Chat com Agente IA (LangGraph)
- **Chat de estudo** com agente ReAct (LangGraph) integrado ao Gemini
- Ferramentas do agente: busca nos materiais (`search_docs`), busca na internet (`search_web`), listagem e criação de flashcards, resumo de progresso
- **Busca na internet** via Tavily (recomendado) com fallback automático para DuckDuckGo (gratuito, sem chave)
- Contexto injetado por sessão de forma thread-safe: acompanhe o desempenho por sessão com resumo de acertos/erros
- Listagem de flashcards agrupados por coleção
- Exclusão individual de flashcards

---

## 🏗️ Arquitetura

```
FlashLearn/
├── app/
│   ├── webapp/          # Configurações Django (settings, urls, wsgi)
│   ├── user/            # Autenticação, registro e login
│   ├── home/            # Landing page e página Sobre
│   ├── flashcards/      # Geração, edição, listagem e revisão de flashcards
│   │   ├── models.py    #   UserFlashcard, ReviewLog, ReviewAssist
│   │   ├── services.py  #   FlashcardService, PDFService, SpacedRepetitionService
│   │   └── templates/
│   ├── ai/              # Integração direta com Google Gemini API
│   ├── rag/             # Pipeline RAG completo
│   │   ├── models.py    #   Collection, Document, DocumentChunk
│   │   ├── services/
│   │   │   ├── ingestion.py   # Upload → Chunk → Embed → ChromaDB
│   │   │   ├── retriever.py   # Busca semântica com filtros
│   │   │   ├── chains.py      # Chains LCEL (explicações, corretivos)
│   │   │   └── chat_agent.py  # Agente LangGraph (ReAct) + 5 ferramentas
│   │   ├── views.py     #   Coleções, documentos, estudo, revisão, chat
│   │   └── templates/rag/    #   9 templates com Tailwind CSS
│   ├── theme/           # Configuração Tailwind CSS + dark/light mode
│   └── chroma_db/       # Banco vetorial ChromaDB (local)
├── requirements.txt
├── Dockerfile
└── README.md
```

### URLs principais

| Prefixo | App | Descrição |
|---------|-----|-----------|
| `/` | home | Landing page e sobre |
| `/user/` | user | Login, registro |
| `/flashcards/` | flashcards | Criar, listar, revisar flashcards |
| `/study/` | rag | Coleções, documentos, modo estudo, chat |
| `/admin/` | Django | Painel administrativo |

### Fluxo RAG
```
Documento → Loader (PDF/TXT/MD) → Chunking (800 chars, 200 overlap)
    → Embeddings (Gemini text-embedding-004) → ChromaDB (vetores + metadados)
    → Busca Semântica → Chains LCEL → Resposta Contextualizada
```

---

## 🔧 Tecnologias Utilizadas

### **Frontend**
- **Tailwind CSS** (via django-tailwind): Framework CSS responsivo com dark mode
- **Django Crispy Forms**: Renderização elegante de formulários

### **Backend**
- **Django 5.1+**: Framework web principal
- **SQLite**: Banco de dados relacional (desenvolvimento)
- **WhiteNoise**: Servir arquivos estáticos em produção
- **django-browser-reload**: Hot reload em desenvolvimento

### **IA e RAG**
- **Google Gemini API** (`google-genai`): LLM para geração de flashcards e explicações (`gemini-2.5-flash-lite`)
- **LangChain**: Orquestração de chains, loaders e text splitters
- **LangGraph**: Agente ReAct (`create_react_agent`) com 5 ferramentas para o chat de estudos
- **LangChain Google GenAI**: Integração LangChain ↔ Gemini (embeddings + chat)
- **ChromaDB**: Banco de dados vetorial para busca semântica
- **Tavily**: Motor de busca na internet para o agente (plano gratuito disponível)
- **DuckDuckGo**: Fallback gratuito de busca web (sem chave de API necessária)
- **Unstructured**: Parsing de documentos (PDF, Markdown)

### **Infraestrutura**
- **Docker**: Containerização da aplicação
- **python-dotenv**: Gerenciamento de variáveis de ambiente

---

## ⚙️ Requisitos

- **Sistema Operacional:** Linux, macOS ou Windows
- **Python:** 3.11 ou superior
- **Node.js:** 18+ (para Tailwind CSS)
- **Chave de API:** Google Gemini API Key ([obter aqui](https://aistudio.google.com/apikey))
- **Chave de API (opcional):** Tavily API Key ([obter aqui](https://app.tavily.com) — plano gratuito disponível) para busca web no agente
- **Espaço em disco:** ~500 MB para dependências + ChromaDB

---

## 📦 Instruções de Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seacello/flashlearn.git
   cd flashlearn
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   python -m venv venv
   ```
   - Linux/macOS: `source venv/bin/activate`
   - Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
   - Windows (CMD): `.\venv\Scripts\activate.bat`

3. **Instale as dependências Python:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as chaves de API:**
   Crie o arquivo `app/.env`:
   ```env
   GOOGLE_API_KEY=sua_chave_aqui
   TAVILY_API_KEY=sua_chave_aqui   # opcional — habilita busca web no agente
   ```

5. **Instale as dependências do Tailwind CSS:**
   ```bash
   python app/manage.py tailwind install
   ```

6. **Aplique as migrações:**
   ```bash
   python app/manage.py migrate
   ```

7. **Crie um superusuário** (opcional):
   ```bash
   python app/manage.py createsuperuser
   ```

8. **Inicie o Tailwind CSS** (terminal separado):
   ```bash
   python app/manage.py tailwind start
   ```

9. **Inicie o servidor:**
   ```bash
   python app/manage.py runserver
   ```

10. **Acesse:**
    - Aplicação: `http://127.0.0.1:8000/`
    - Painel admin: `http://127.0.0.1:8000/admin/`

### 🐳 Alternativa com Docker

```bash
docker build -t flashlearn .
docker run -p 8000:8000 --env GOOGLE_API_KEY=sua_chave flashlearn
```

---

## 🔑 Configuração da API

1. Acesse o [Google AI Studio](https://aistudio.google.com/apikey) e gere uma API Key
2. Crie o arquivo `app/.env`:
   ```env
   GOOGLE_API_KEY=AIzaSy...sua_chave
   ```
3. Configurações em `webapp/settings.py`:

   | Variável | Padrão | Descrição |
   |----------|--------|-----------|
   | `GOOGLE_API_KEY` | — | **Obrigatória.** Chave da API Google Gemini |
   | `TAVILY_API_KEY` | — | Opcional. Busca web no agente (fallback: DuckDuckGo) |
   | `RAG_LLM_MODEL` | `gemini-2.5-flash-lite` | Modelo LLM para geração de texto |
   | `RAG_EMBEDDING_MODEL` | `models/gemini-embedding-001` | Modelo de embeddings |
   | `RAG_CHUNK_SIZE` | `800` | Tamanho dos chunks de texto |
   | `RAG_CHUNK_OVERLAP` | `200` | Overlap entre chunks |
   | `RAG_CHROMA_COLLECTION` | `flashlearn_docs` | Nome da coleção ChromaDB |

---

## ➡️ Instruções de Uso

### 1. Criar Flashcards
1. Faça login ou registre-se
2. Na home, clique em **Criar Flashcards**
3. Faça upload de um PDF, TXT ou DOCX
4. Opcionalmente, selecione ou crie uma **sessão de estudo** no dropdown (ou deixe em branco)
5. Clique em **Gerar Flashcards** e edite o resultado

### 2. Chat com Agente IA
1. Na home, clique em **Estudar com IA** (ou acesse `/study/chat/`)
2. Selecione uma sessão para que a IA use seus materiais como contexto (opcional)
3. Faça perguntas livremente — o agente:
   - Primeiro busca nos seus documentos (`search_docs`)
   - Se não encontrar, busca na internet (`search_web`)
   - Pode criar flashcards durante a conversa e consultar seu progresso
4. O agente cita as fontes utilizadas na resposta

### 3. Estudo com Modo Estudo (flip cards + RAG)
1. Na sessão de estudo (`/study/collections/<id>/`), abra a aba **Estudar**
2. Clique em **Iniciar Estudo** para a sessão de flip cards
3. Avalie cada flashcard (acertou/errou + nível de confiança)
4. Ao errar, solicite **Ajuda ao RAG** para:
   - Receber explicação contextualizada baseada nos seus materiais
   - Ver os trechos fonte relevantes
   - Gerar **flashcards corretivos** automáticos

### 4. Enviar Materiais (para o RAG)
1. Acesse `/study/documents/upload/` ou clique em **Enviar Material** dentro de uma sessão
2. Faça upload de PDF, TXT ou Markdown
3. Aguarde o processamento (pendente → processando → concluído)
4. A IA passa a usar esse conteúdo nas respostas e no modo estudo

---

## 📌 Status do Projeto

**Versão atual:** Em desenvolvimento ativo  
**Última atualização:** 26/02/2026

### ✅ Implementado
- Autenticação e registro de usuários
- Geração de flashcards via upload de arquivo com Google Gemini
- Tipos de card: padrão, cloze, reverso e múltipla escolha
- Edição inline com auto-save (AJAX) e download em PDF
- Pipeline RAG completo: ingestão, embeddings, ChromaDB, busca semântica
- Sessões (coleções) para organizar materiais de estudo
- Modo Estudo interativo (flip cards + avaliação de confiança)
- Revisão com RAG: explicações contextualizadas + flashcards corretivos
- **Agente LangGraph (ReAct)** com 5 ferramentas: busca em documentos, busca na internet, flashcards, progresso
- **Busca na internet** no agente via Tavily (com fallback DuckDuckGo gratuito)
- Repetição espaçada com resumo de acertos/erros por sessão
- Dark mode / Light mode
- Containerização com Docker

### 🔜 Próximas melhorias
- Algoritmo SM-2 para repetição espaçada avançada
- Suporte a DOCX e PPTX no pipeline RAG
- Dashboard com estatísticas de desempenho
- GitHub Actions para CI/CD
- Deploy em produção com PostgreSQL

---

## 🤝 Diretrizes para Contribuição

1. Abra uma **issue** para sugerir funcionalidades ou reportar bugs
2. Crie uma branch para suas mudanças:
   ```bash
   git checkout -b feature/minha-contribuicao
   ```
3. Faça um **pull request** detalhando as alterações
4. Aguarde a revisão da equipe

---

## 👥 Equipe de Desenvolvimento

- **Marcello Menezes** — Líder Técnico
- **Eduardo Santana** — Fullstack Developer
