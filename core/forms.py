from django import forms


class ImportacaoForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo Excel",
        help_text="Formatos aceitos: .xlsx (Microbiologia, Controle ATB, Passagens) e .xls (Controle ATB, formato antigo). "
                  "O tipo é detectado automaticamente.",
    )
