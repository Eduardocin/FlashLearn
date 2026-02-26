from django import forms
from rag.models import Collection


class CreateCardForm(forms.Form):
    collection = forms.ModelChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        label='Sessão de Estudo (opcional)',
        empty_label='Sem sessão',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md text-gray-700 bg-white focus:ring-2 focus:ring-orange-400 focus:border-orange-400 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-600'
        }),
    )
    file = forms.FileField(
        label='',
        widget=forms.ClearableFileInput(attrs={'class': 'w-full text-gray-400 font-semibold text-sm bg-white border file:cursor-pointer cursor-pointer file:border-0 file:py-3 file:px-4 file:mr-4 file:bg-gray-100 file:hover:bg-gray-200 file:text-gray-500 rounded'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['collection'].queryset = Collection.objects.filter(user=user)

    def clean_file(self):
        file = self.cleaned_data['file']
        if file.size > 5*1024*1024:
            raise forms.ValidationError("Arquivo muito grande (máximo 5MB)")
        if not file.name.lower().endswith(('.pdf', '.docx', '.txt')):
            raise forms.ValidationError("Formato não suportado")
        return file