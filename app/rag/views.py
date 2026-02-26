import os
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from google import genai as google_genai

from .models import Collection, Document, DocumentChunk
from .forms import CollectionForm, DocumentUploadForm, ContextualFlashcardForm
from .services.ingestion import ingest_document, delete_document_vectors
from .services.chains import (
    generate_review_explanation,
    generate_full_review_assist,
    generate_contextual_flashcards,
    _format_context,
)
from .services.retriever import retrieve_relevant_chunks
from .services.chat_agent import run_chat_agent
from flashcards.models import UserFlashcard, ReviewLog, ReviewAssist

logger = logging.getLogger(__name__)
_gemini_client = google_genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
GEMINI_MODEL = os.getenv('RAG_LLM_MODEL', 'gemini-2.5-flash-lite')


# ─── Coleções ───────────────────────────────────────────────────────────────

@login_required
def collection_list(request):
    """Lista todas as coleções do usuário."""
    collections = Collection.objects.filter(user=request.user)
    return render(request, 'rag/collection_list.html', {
        'collections': collections,
    })


@login_required
def collection_create(request):
    """Cria uma nova coleção."""
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.user = request.user
            collection.save()
            messages.success(request, f'Sessão "{collection.name}" criada com sucesso!')
            return redirect('flashcards:create_flashcards')
    else:
        form = CollectionForm()

    return render(request, 'rag/collection_form.html', {
        'form': form,
        'title': 'Nova Sessão de Estudo',
    })


@login_required
def collection_detail(request, pk):
    """Detalhe de uma coleção com seus documentos e flashcards."""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)
    documents = collection.documents.all()
    flashcards = UserFlashcard.objects.filter(
        user=request.user, collection=collection
    ).order_by('-create_at')
    return render(request, 'rag/collection_detail.html', {
        'collection': collection,
        'documents': documents,
        'flashcards': flashcards,
        'flashcard_count': flashcards.count(),
    })


@login_required
def collection_delete(request, pk):
    """Exclui uma coleção e todos seus documentos/chunks."""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)
    if request.method == 'POST':
        # Remover vetores do ChromaDB primeiro
        for doc in collection.documents.all():
            delete_document_vectors(doc)
        name = collection.name
        collection.delete()
        messages.success(request, f'Sessão "{name}" excluída com sucesso!')
        return redirect('flashcards:home_flashcards')
    return render(request, 'rag/collection_confirm_delete.html', {
        'collection': collection,
    })


# ─── Upload de Documentos ──────────────────────────────────────────────────

@login_required
def document_upload(request):
    """Upload e ingestão de documento no pipeline RAG."""
    initial_collection = request.GET.get('collection')

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.file_type = document.file.name.rsplit('.', 1)[-1].lower()
            document.file_size = document.file.size
            document.save()

            try:
                num_chunks = ingest_document(document)
                messages.success(
                    request,
                    f'Documento "{document.title}" processado com sucesso! '
                    f'{num_chunks} trechos indexados.'
                )
            except Exception as e:
                messages.error(request, f'Erro ao processar documento: {str(e)}')
                logger.error(f'Erro na ingestão do documento {document.id}: {e}')

            return redirect('rag:collection_detail', pk=document.collection_id)
    else:
        form = DocumentUploadForm(user=request.user)
        if initial_collection:
            form.fields['collection'].initial = initial_collection

    return render(request, 'rag/document_upload.html', {
        'form': form,
    })


@login_required
def document_detail(request, pk):
    """Detalhe de um documento com seus chunks."""
    document = get_object_or_404(Document, pk=pk, user=request.user)
    chunks = document.chunks.all()[:20]  # Limitar para performance
    return render(request, 'rag/document_detail.html', {
        'document': document,
        'chunks': chunks,
    })


@login_required
def document_delete(request, pk):
    """Exclui um documento e seus vetores."""
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if request.method == 'POST':
        collection_id = document.collection_id
        delete_document_vectors(document)
        title = document.title
        document.delete()
        messages.success(request, f'Documento "{title}" excluído com sucesso!')
        return redirect('rag:collection_detail', pk=collection_id)
    return render(request, 'rag/document_confirm_delete.html', {
        'document': document,
    })


# ─── Revisão com Contexto RAG ──────────────────────────────────────────────

@login_required
@require_POST
def review_flashcard(request, flashcard_id):
    """
    Registra resposta do usuário a um flashcard.
    Se errou, dispara o pipeline RAG para assistência.
    Retorna JSON para uso via AJAX.
    """
    flashcard = get_object_or_404(UserFlashcard, pk=flashcard_id, user=request.user)
    is_correct = request.POST.get('is_correct') == 'true'
    confidence = int(request.POST.get('confidence', 0))

    # 1. Registrar no ReviewLog
    review_log = ReviewLog.objects.create(
        user=request.user,
        flashcard=flashcard,
        is_correct=is_correct,
        confidence=confidence,
    )

    response_data = {
        'status': 'success',
        'is_correct': is_correct,
        'review_id': review_log.id,
    }

    # 2. Se errou, gerar assistência RAG
    if not is_correct:
        try:
            assist_data = generate_full_review_assist(
                flashcard_title=flashcard.title,
                flashcard_content=flashcard.content,
                user_id=request.user.id,
                collection_id=flashcard.collection_id,
            )

            # Persistir assistência
            review_assist = ReviewAssist.objects.create(
                review_log=review_log,
                explanation=assist_data['explanation'],
                source_chunks=assist_data['source_chunks'],
                corrective_flashcards=assist_data['corrective_flashcards'],
                model_used=assist_data.get('model_used', 'gemini-2.5-flash-lite'),
                tokens_used=assist_data.get('tokens_used', 0),
            )

            response_data['assist'] = {
                'explanation': assist_data['explanation'],
                'sources': assist_data['source_chunks'],
                'corrective_flashcards': assist_data['corrective_flashcards'],
            }

        except Exception as e:
            logger.error(f"Erro ao gerar assistência RAG: {e}")
            response_data['assist'] = {
                'explanation': 'Não foi possível gerar explicação baseada em seus materiais.',
                'sources': [],
                'corrective_flashcards': [],
            }

    return JsonResponse(response_data)


@login_required
@require_POST
def save_corrective_flashcards(request, review_id):
    """
    Salva flashcards corretivos sugeridos pelo RAG como flashcards do usuário.
    """
    review_log = get_object_or_404(ReviewLog, pk=review_id, user=request.user)

    try:
        assist = review_log.assist
    except ReviewAssist.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Assistência não encontrada.'}, status=404)

    created = []
    for card_data in assist.corrective_flashcards:
        card = UserFlashcard.objects.create(
            user=request.user,
            title=card_data.get('title', 'Flashcard Corretivo'),
            content=card_data.get('content', ''),
            card_type=card_data.get('card_type', 'standard'),
            collection=review_log.flashcard.collection,
            source_document=review_log.flashcard.source_document,
            is_corrective=True,
        )
        created.append({'id': card.id, 'title': card.title})

    return JsonResponse({
        'status': 'success',
        'message': f'{len(created)} flashcards corretivos salvos!',
        'flashcards': created,
    })


# ─── Flashcards Contextualizados ───────────────────────────────────────────

@login_required
def contextual_flashcards(request):
    """
    Gera flashcards baseados nos materiais do usuário.
    """
    initial_collection = request.GET.get('collection')
    form = ContextualFlashcardForm(user=request.user)
    if initial_collection:
        form.fields['collection'].initial = initial_collection
    flashcards = []

    if request.method == 'POST':
        form = ContextualFlashcardForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                flashcards = generate_contextual_flashcards(
                    topic=form.cleaned_data['topic'],
                    user_id=request.user.id,
                    collection_id=(
                        form.cleaned_data['collection'].id
                        if form.cleaned_data.get('collection') else None
                    ),
                    num_cards=form.cleaned_data['num_cards'],
                )
                if flashcards:
                    messages.success(request, f'{len(flashcards)} flashcards gerados com base nos seus materiais!')
                else:
                    messages.warning(request, 'Nenhum flashcard gerado. Verifique se há materiais enviados.')
            except Exception as e:
                messages.error(request, f'Erro ao gerar flashcards: {str(e)}')
                logger.error(f'Erro contextual flashcards: {e}')

    return render(request, 'rag/contextual_flashcards.html', {
        'form': form,
        'flashcards': flashcards,
    })


# ─── Study Mode (Revisão Ativa) ────────────────────────────────────────────

@login_required
def study_mode(request, collection_id=None):
    """
    Modo estudo: mostra flashcards para revisão ativa com integração RAG.
    """
    query = UserFlashcard.objects.filter(user=request.user)
    collection = None

    if collection_id:
        collection = get_object_or_404(Collection, pk=collection_id, user=request.user)
        query = query.filter(collection=collection)

    flashcards = list(query.values('id', 'title', 'content', 'card_type', 'collection_id'))

    # Limpar histórico de chat ao iniciar nova sessão de estudo
    request.session.pop('study_chat_history', None)

    return render(request, 'rag/study_mode.html', {
        'flashcards_json': flashcards,
        'collection': collection,
        'collection_id': collection_id,
        'total': len(flashcards),
    })


# ─── Chat Agent (Modo Estudo) ───────────────────────────────────────────────

@login_required
def study_chat(request):
    """
    Agente de chat para tirar dúvidas durante o estudo.
    GET: renderiza a página standalone do chat.
    POST (AJAX): retorna resposta da IA em JSON.
    """
    if request.method == 'GET':
        collections = Collection.objects.filter(user=request.user)
        selected_id = request.GET.get('collection')
        return render(request, 'rag/chat.html', {
            'collections': collections,
            'selected_id': selected_id,
        })

    message = request.POST.get('message', '').strip()
    collection_id = request.POST.get('collection_id')

    if not message:
        return JsonResponse({'error': 'Mensagem vazia.'}, status=400)

    # Histórico da sessão (últimas 16 mensagens = 8 trocas)
    history = request.session.get('study_chat_history', [])

    try:
        result = run_chat_agent(
            message=message,
            user_id=request.user.id,
            collection_id=int(collection_id) if collection_id else None,
            history=history,
        )
        answer = result['answer']
        tools_used = result.get('tools_used', [])

        # Atualizar histórico na sessão
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': answer})
        request.session['study_chat_history'] = history[-16:]

        return JsonResponse({'answer': answer, 'tools_used': tools_used})

    except Exception as e:
        logger.error(f"Erro no chat de estudo (agente): {e}")
        return JsonResponse({'error': 'Não foi possível gerar resposta no momento.'}, status=500)
