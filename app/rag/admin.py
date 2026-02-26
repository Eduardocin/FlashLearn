from django.contrib import admin
from .models import Collection, Document, DocumentChunk


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'document_count', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('name', 'user__username')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'collection', 'file_type', 'status', 'total_chunks', 'uploaded_at')
    list_filter = ('status', 'file_type', 'user')
    search_fields = ('title', 'user__username', 'collection__name')
    readonly_fields = ('total_chunks', 'processed_at', 'error_message')


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'chunk_index', 'char_count', 'embedding_id', 'created_at')
    list_filter = ('document__collection',)
    search_fields = ('content', 'document__title')
    readonly_fields = ('embedding_id', 'metadata')
