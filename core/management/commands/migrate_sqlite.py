import sqlite3
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from core.models import Hospital, Paciente, Cultura, Antibiograma, ControleAtbRaw, Internamento


def _parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except Exception:
        return None


class Command(BaseCommand):
    help = "Migra dados do SQLite legado (desktop) para o banco Django."

    def add_arguments(self, parser):
        parser.add_argument("--db-path", required=True, help="Caminho para o atb.db legado")
        parser.add_argument("--hospital-sigla", required=True, help="Sigla do hospital já criado no Django")

    def handle(self, *args, **options):
        db_path = options["db_path"]
        sigla   = options["hospital_sigla"]

        try:
            hospital = Hospital.objects.get(sigla=sigla)
        except Hospital.DoesNotExist:
            raise CommandError(f"Hospital com sigla '{sigla}' não encontrado. Crie-o no admin primeiro.")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        self.stdout.write(f"Conectado ao banco: {db_path}")
        self.stdout.write(f"Hospital alvo: {hospital}")

        # ── Pacientes ─────────────────────────────────────────────────────────
        pac_id_map = {}
        pac_rows = conn.execute("SELECT * FROM pacientes").fetchall()
        self.stdout.write(f"Migrando {len(pac_rows)} pacientes...")
        for row in pac_rows:
            pac, _ = Paciente.objects.update_or_create(
                hospital=hospital,
                prontuario=row["prontuario"],
                defaults={"nome": row["nome"] or ""},
            )
            pac_id_map[row["id"]] = pac
        self.stdout.write(self.style.SUCCESS(f"  {len(pac_id_map)} pacientes prontos."))

        # ── Culturas ──────────────────────────────────────────────────────────
        cult_id_map = {}
        cult_rows = conn.execute("SELECT * FROM culturas").fetchall()
        self.stdout.write(f"Migrando {len(cult_rows)} culturas...")
        cult_ok = 0
        for row in cult_rows:
            pac = pac_id_map.get(row["paciente_id"])
            if not pac:
                continue
            cultura, _ = Cultura.objects.update_or_create(
                paciente=pac,
                os=row["os"] or "",
                procedimento=row["procedimento"] or "",
                dt_assinatura=_parse_date(row["dt_assinatura"]),
                defaults={
                    "unidade":       row["unidade"] or "",
                    "dt_coleta":     _parse_date(row["dt_coleta"]),
                    "microrganismo": row["microrganismo"] or "",
                    "obs":           row["obs"] or "",
                    "trat_respir":   row["trat_respir"] or "",
                },
            )
            cult_id_map[row["id"]] = cultura
            cult_ok += 1
        self.stdout.write(self.style.SUCCESS(f"  {cult_ok} culturas prontas."))

        # ── Antibiograma ──────────────────────────────────────────────────────
        atb_rows = conn.execute("SELECT * FROM antibiograma").fetchall()
        self.stdout.write(f"Migrando {len(atb_rows)} entradas de antibiograma...")
        atb_ok = 0
        for row in atb_rows:
            cultura = cult_id_map.get(row["cultura_id"])
            if not cultura:
                continue
            Antibiograma.objects.get_or_create(
                cultura=cultura,
                antibiotico=row["antibiotico"],
                sensibilidade=row["sensibilidade"],
            )
            atb_ok += 1
        self.stdout.write(self.style.SUCCESS(f"  {atb_ok} antibiogramas prontos."))

        # ── Controle ATB ──────────────────────────────────────────────────────
        catb_rows = conn.execute("SELECT * FROM controle_atb_raw").fetchall()
        self.stdout.write(f"Migrando {len(catb_rows)} registros de controle ATB...")
        catb_ok = 0
        for row in catb_rows:
            pac = pac_id_map.get(row["paciente_id"])
            if not pac:
                continue
            ControleAtbRaw.objects.update_or_create(
                paciente=pac,
                medicamento=row["medicamento"] or "",
                dt_inicio=_parse_date(row["dt_inicio"]),
                defaults={
                    "acomodacao":  row["acomodacao"] or "",
                    "dias_solic":  row["dias_solic"]  or 0,
                    "dias_ccih":   row["dias_ccih"]   or 0,
                    "dias_em_uso": row["dias_em_uso"] or 0,
                    "medico":      row["medico"] or "",
                },
            )
            catb_ok += 1
        self.stdout.write(self.style.SUCCESS(f"  {catb_ok} registros ATB prontos."))

        # ── Internamentos ─────────────────────────────────────────────────────
        int_rows = conn.execute("SELECT * FROM internamentos").fetchall()
        self.stdout.write(f"Migrando {len(int_rows)} internamentos...")
        int_ok = 0
        for row in int_rows:
            pac = pac_id_map.get(row["paciente_id"])
            if not pac:
                continue
            Internamento.objects.update_or_create(
                paciente=pac,
                dt_entrada=_parse_date(row["dt_entrada"]),
                defaults={
                    "dt_alta": _parse_date(row["dt_alta"]),
                    "dias":    row["dias"] or 0,
                },
            )
            int_ok += 1
        self.stdout.write(self.style.SUCCESS(f"  {int_ok} internamentos prontos."))

        conn.close()
        self.stdout.write(self.style.SUCCESS(
            f"\nMigração concluída para o hospital {hospital.sigla}!"
        ))
