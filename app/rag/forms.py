from django import forms
from .models import Collection, Document


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
                'placeholder': 'Ex: Cálculo I, Biologia Celular...',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
                'placeholder': 'Descrição opcional da matéria...',
                'rows': 3,
            }),
        }


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file', 'collection']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
                'placeholder': 'Nome do documento...',
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'w-full text-gray-400 font-semibold text-sm bg-white border file:cursor-pointer cursor-pointer file:border-0 file:py-3 file:px-4 file:mr-4 file:bg-gray-100 file:hover:bg-gray-200 file:text-gray-500 rounded dark:bg-gray-700 dark:text-gray-300',
            }),
            'collection': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['collection'].queryset = Collection.objects.filter(user=user)
        self.fields['file'].label = 'Arquivo'
        self.fields['collection'].label = 'Coleção / Matéria'

    ALLOWED_EXTENSIONS = ('pdf', 'txt', 'md')
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            ext = file.name.rsplit('.', 1)[-1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise forms.ValidationError(
                    f"Formato não suportado. Use: {', '.join(self.ALLOWED_EXTENSIONS)}"
                )
            if file.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError("Arquivo muito grande (máximo 10MB).")
        return file


class ContextualFlashcardForm(forms.Form):
    """Form para gerar flashcards contextualizados a partir de materiais."""
    topic = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
            'placeholder': 'Ex: Derivadas parciais, Mitose e Meiose...',
        }),
        label='Tema / Assunto',
    )
    collection = forms.ModelChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
        }),
        label='Coleção (opcional)',
        help_text='Filtrar por matéria específica',
    )
    num_cards = forms.IntegerField(
        min_value=1, max_value=10, initial=4,
        widget=forms.NumberInput(attrs={
            'class': 'w-24 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-gray-700 dark:text-white dark:border-gray-600',
        }),
        label='Quantidade',
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['collection'].queryset = Collection.objects.filter(user=user)
