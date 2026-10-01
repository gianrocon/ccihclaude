from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_imagemexame"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospital",
            name="cnes",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Usado para recusar planilhas de outro hospital (o relatório de ATB traz o CNES no cabeçalho).",
                max_length=10,
                verbose_name="CNES",
            ),
        ),
    ]
