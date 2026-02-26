from django.db import models
from django.contrib.auth.models import User



class UserFlashcard(models.Model):
    CARD_TYPE_CHOICES = [
        ('standard', 'Padrão'),
        ('cloze', 'Cloze Deletion'),
        ('reverse', 'Inversão P/R'),
        ('mcq', 'Múltipla Escolha'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_flashcards')
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES, default='standard')
    collection = models.ForeignKey(
        'rag.Collection', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='flashcards',
        help_text='Coleção/matéria associada'
    )
    source_document = models.ForeignKey(
        'rag.Document', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='flashcards',
        help_text='Documento de origem (se gerado via RAG)'
    )
    is_corrective = models.BooleanField(
        default=False,
        help_text='Flashcard gerado automaticamente após erro em revisão'
    )
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-create_at']
        
    def __str__(self):
        return f"Flashcard de {self.user.username} - {self.create_at.strftime('%d/%m/%Y')}"


class ReviewLog(models.Model):
    """
    Registro de cada tentativa de revisão de um flashcard.
    Alimenta o sistema de repetição espaçada e dispara assistência RAG.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_logs')
    flashcard = models.ForeignKey(
        UserFlashcard, on_delete=models.CASCADE, related_name='review_logs'
    )
    is_correct = models.BooleanField()
    confidence = models.PositiveSmallIntegerField(
        default=0,
        help_text='Auto-avaliação de confiança (0-5)'
    )
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reviewed_at']

    def __str__(self):
        status = '✓' if self.is_correct else '✗'
        return f"{status} {self.flashcard.title} - {self.reviewed_at.strftime('%d/%m/%Y %H:%M')}"


class ReviewAssist(models.Model):
    """
    Assistência gerada por IA quando o usuário erra um flashcard.
    Contém explicação fundamentada nos documentos do usuário (RAG),
    citações das fontes e flashcards corretivos sugeridos.
    """
    review_log = models.OneToOneField(
        ReviewLog, on_delete=models.CASCADE, related_name='assist'
    )
    explanation = models.TextField(
        help_text='Explicação gerada pela IA com base nos documentos do usuário'
    )
    source_chunks = models.JSONField(
        default=list,
        help_text='Lista de chunks usados como fonte: [{chunk_id, document_title, excerpt}]'
    )
    corrective_flashcards = models.JSONField(
        default=list, blank=True,
        help_text='Flashcards corretivos sugeridos: [{title, content, card_type}]'
    )
    model_used = models.CharField(max_length=50, default='gemini-2.5-flash-lite')
    tokens_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Assistência para {self.review_log}"