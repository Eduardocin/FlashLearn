from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from .services import FlashcardService, PDFService, SpacedRepetitionService
from .models import UserFlashcard
from .forms import CreateCardForm
from rag.models import Collection
from collections import defaultdict


@login_required
def create_flashcards(request):
    """
    Processes the file uploaded by the user and generates flashcards from its content.
    Allows the user to edit the generated flashcards via AJAX.
    """

    form = CreateCardForm(user=request.user)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'GET':
        if 'flashcards' in request.session:
            del request.session['flashcards']
        flashcards = []
        # Pré-selecionar sessão se vier por query param
        initial_collection = request.GET.get('collection')
        if initial_collection:
            form.fields['collection'].initial = initial_collection
    
    elif request.method == 'POST':
        
        if is_ajax:
            titles = request.POST.getlist('title')
            contents = request.POST.getlist('content')
            flashcard_ids = request.POST.getlist('flashcard_id')
            flashcards = FlashcardService.update_flashcards_from_data(request.user, titles, contents, flashcard_ids)
            request.session['flashcards'] = flashcards
            return JsonResponse({
                'status': 'success', 
                'message': 'Flashcards atualizados com sucesso',
            })
        
        elif 'file' in request.FILES:
            form = CreateCardForm(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                try:
                    collection = form.cleaned_data.get('collection')
                    flashcards = FlashcardService.create_flashcards_from_file(
                        request.user, request.FILES['file'], collection=collection
                    )
                    request.session['flashcards'] = flashcards
                except Exception as e:
                    form.add_error(None, f"Erro: {str(e)}")
                    print(f"DEBUG - Erro ao gerar flashcards: {str(e)}")
                    flashcards = []
            else:
                flashcards = []
        else:
            flashcards = request.session.get('flashcards', [])

    
    return render(request, 'create_flashcards.html', {
        'form': form,
        'flashcards': flashcards
    })


@login_required
def user_flashcards_home(request):
    """
    User's home page for flashcard management.
    """
    
    return render(
        request, 
        'home_user.html',
    )
    

@login_required
def meus_flashcards(request):
    """
    Exibe os flashcards do usuário agrupados por sessão, com dados de repetição espaçada.
    """

    all_flashcards = list(
        UserFlashcard.objects.filter(user=request.user).select_related('collection')
    )

    # Agrupar por sessão
    grouped = defaultdict(list)
    for fc in all_flashcards:
        grouped[fc.collection].append(fc)

    sessions = []
    no_session_cards = []

    for collection, cards in grouped.items():
        sr_summary = SpacedRepetitionService.session_sr_summary(cards)

        # Enriquecer cada card com dados SR individuais
        enriched_cards = []
        for card in cards:
            enriched_cards.append({
                'card': card,
                'sr': SpacedRepetitionService.card_sr_info(card),
            })

        if collection is None:
            no_session_cards = enriched_cards
        else:
            sessions.append({
                'collection': collection,
                'cards': enriched_cards,
                'count': len(cards),
                'sr': sr_summary,
            })

    sessions.sort(key=lambda s: s['collection'].name.lower())

    # Resumo global
    global_sr = {
        'overdue': sum(s['sr']['overdue'] for s in sessions),
        'due_today': sum(s['sr']['due_today'] for s in sessions),
        'upcoming': sum(s['sr']['upcoming'] for s in sessions),
        'never': sum(s['sr']['never'] for s in sessions),
        'total': len(all_flashcards),
    }

    return render(request, 'meus_flashcards.html', {
        'sessions': sessions,
        'no_session_cards': no_session_cards,
        'total_count': len(all_flashcards),
        'global_sr': global_sr,
    })

    
@login_required
def download_pdf(request):
    """
    Generates a PDF containing the user's flashcards for download.
    
    This view retrieves the latest 4 flashcards created by the user, generates a PDF
    document with these flashcards, and returns it as a downloadable file.
    
    If no flashcards are found for the user, an appropriate message is returned.
    """
    
    user_flashcards = UserFlashcard.objects.filter(user=request.user).order_by('-id')[:4]
    
    if not user_flashcards:
        return HttpResponse("Nenhum flashcard encontrado. Crie flashcards antes de fazer o download.", 
                        content_type='text/plain')
    
    try:
        buffer_pdf = PDFService.generate_flashcards_pdf(user_flashcards)
        
        response = HttpResponse(buffer_pdf.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="flashcards.pdf"'
        return response
    
    except Exception as e:
        return HttpResponse(f"Erro na geração do PDF: {str(e)}", status=500)
    
@login_required
def excluir_flashcard(request, flashcard_id):
    """
    Deletes a flashcard based on its ID.
    
    This view retrieves the flashcard with the given ID and deletes it from the database.
    If the flashcard is successfully deleted, a success message is returned.
    If the flashcard is not found, an error message is returned.
    """
    
    try:
        flashcard = UserFlashcard.objects.get(id=flashcard_id, user=request.user)
        titulo = flashcard.title
        flashcard.delete()
        
        # Verificar se é uma requisição AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': f'Flashcard "{titulo}" excluído com sucesso.'})
        else:
            # Para solicitações normais, adicione uma mensagem e redirecione
            messages.success(request, f'Flashcard "{titulo}" excluído com sucesso.')
            return redirect('flashcards:meus_flashcards')
    
    except UserFlashcard.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Flashcard não encontrado.'}, status=404)
        else:
            messages.error(request, 'Flashcard não encontrado.')
            return redirect('flashcards:meus_flashcards')
