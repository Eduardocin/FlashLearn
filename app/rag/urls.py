from django.urls import path
from . import views

app_name = 'rag'

urlpatterns = [
    # Coleções (a listagem foi removida — coleções são geridas via criar flashcards)
    path('collections/new/', views.collection_create, name='collection_create'),
    path('collections/<int:pk>/', views.collection_detail, name='collection_detail'),
    path('collections/<int:pk>/delete/', views.collection_delete, name='collection_delete'),

    # Documentos
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),

    # Revisão com RAG
    path('review/<int:flashcard_id>/', views.review_flashcard, name='review_flashcard'),
    path('review/<int:review_id>/save-corrective/', views.save_corrective_flashcards, name='save_corrective'),

    # Flashcards contextualizados
    path('contextual/', views.contextual_flashcards, name='contextual_flashcards'),

    # Modo estudo
    path('study/', views.study_mode, name='study_mode'),
    path('study/<int:collection_id>/', views.study_mode, name='study_mode_collection'),

    # Chat de estudo
    path('chat/', views.study_chat, name='study_chat'),
]
