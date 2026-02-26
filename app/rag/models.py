from django.db import models
from django.contrib.auth.models import User


class Collection(models.Model):
    """
    Coleção/matéria do usuário para agrupar documentos.
    Cada coleção representa um tema de estudo (ex: 'Cálculo I', 'Biologia Celular').
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def document_count(self):
        return self.documents.count()

    @property
    def total_chunks(self):
        return sum(doc.total_chunks for doc in self.documents.all())


class Document(models.Model):
    """
    Documento enviado pelo usuário para ingestão no pipeline RAG.
    Suporta PDF, TXT e Markdown.
    """
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('txt', 'Texto'),
        ('md', 'Markdown'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('completed', 'Concluído'),
        ('failed', 'Falhou'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name='documents'
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveIntegerField(default=0, help_text='Tamanho em bytes')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    total_chunks = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    @property
    def file_extension(self):
        return self.file.name.rsplit('.', 1)[-1].lower() if self.file else ''


class DocumentChunk(models.Model):
    """
    Fragmento de texto de um documento, pronto para embedding e busca vetorial.
    Cada chunk é armazenado no banco relacional (metadados) e no ChromaDB (embedding).
    """
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    char_count = models.PositiveIntegerField(default=0)
    embedding_id = models.CharField(
        max_length=255, blank=True,
        help_text='ID do vetor no ChromaDB'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']

    def __str__(self):
        return f"Chunk {self.chunk_index} de '{self.document.title}'"
