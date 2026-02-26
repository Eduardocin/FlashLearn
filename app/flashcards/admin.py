from django.contrib import admin
from .models import UserFlashcard, ReviewLog, ReviewAssist

@admin.register(UserFlashcard)
class UserFlashcardAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'card_type', 'collection', 'is_corrective', 'create_at')
    list_filter = ('user', 'card_type', 'is_corrective', 'create_at')
    search_fields = ('user__username', 'content', 'title')
    date_hierarchy = 'create_at'


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard', 'is_correct', 'confidence', 'reviewed_at')
    list_filter = ('is_correct', 'user', 'reviewed_at')
    date_hierarchy = 'reviewed_at'


@admin.register(ReviewAssist)
class ReviewAssistAdmin(admin.ModelAdmin):
    list_display = ('review_log', 'model_used', 'tokens_used', 'created_at')
    list_filter = ('model_used', 'created_at')
    readonly_fields = ('source_chunks', 'corrective_flashcards')