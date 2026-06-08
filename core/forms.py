from django import forms


class ImportacaoForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo Excel",
        help_text="Formatos aceitos: .xlsx (Microbiologia, Passagens) e .xls (Controle ATB). "
                  "O tipo é detectado automaticamente.",
    )
