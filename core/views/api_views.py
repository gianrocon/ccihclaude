"""API JSON autenticada por token (leitura + um endpoint de importação).

Existe para o agente ``consultor-infecto`` obter culturas, antibiograma e
antibióticos em uso sem raspar a interface HTML. Sem DRF de propósito: são
quatro endpoints GET e a camada de serviço já está pronta em
``core.services.patient_service``.

Notas de projeto:

* **Sem sessão.** O ``HospitalAtualMiddleware`` deixa ``request.hospital_atual``
  como ``None`` para requisições anônimas, sem levantar exceção — por isso não
  precisa ser alterado. Aqui o hospital vem sempre do query param ``hospital``.
* **Só GET**, portanto CSRF não se aplica.
* **Falha fechada:** sem ``API_TOKEN`` configurado no ``.env``, a API responde
  503 em vez de liberar acesso.
"""

from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from decouple import config
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.models import Hospital
from core.services import importer_service
from core.services import patient_service as svc

MAX_BUSCA = 50


# --------------------------------------------------------------------------- #
# Autenticação e resolução de hospital
# --------------------------------------------------------------------------- #

def _erro(mensagem, status, **extra):
    return JsonResponse({"erro": mensagem, **extra}, status=status)


def _token_valido(request) -> bool:
    esperado = config("API_TOKEN", default="")
    if not esperado:
        return False
    header = request.headers.get("Authorization", "")
    prefixo = "Bearer "
    if not header.startswith(prefixo):
        return False
    return secrets.compare_digest(header[len(prefixo):].strip(), esperado)


def api_view(func):
    """Exige token válido e responde erros em JSON."""

    @require_GET
    def wrapper(request, *args, **kwargs):
        if not config("API_TOKEN", default=""):
            return _erro("API_TOKEN nao configurado no servidor", 503)
        if not _token_valido(request):
            return _erro("token ausente ou invalido", 401)
        return func(request, *args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _resolver_hospital(request):
    """Devolve ``(hospital, resposta_de_erro)``. Exatamente um dos dois é None."""
    sigla = (request.GET.get("hospital") or "").strip()
    if not sigla:
        disponiveis = list(Hospital.objects.filter(ativo=True).values_list("sigla", flat=True))
        return None, _erro("parametro 'hospital' e obrigatorio", 400, hospitais=disponiveis)

    hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
    if hospital is None:
        disponiveis = list(Hospital.objects.filter(ativo=True).values_list("sigla", flat=True))
        return None, _erro("hospital '%s' nao encontrado" % sigla, 404, hospitais=disponiveis)

    return hospital, None


# --------------------------------------------------------------------------- #
# Serialização
# --------------------------------------------------------------------------- #

def _ser_cultura(cultura):
    return {
        "os": cultura.os,
        "unidade": cultura.unidade,
        "dt_coleta": cultura.dt_coleta,
        "dt_assinatura": cultura.dt_assinatura,
        # 'procedimento' e o material/sitio da coleta, apesar do nome
        "sitio": cultura.procedimento,
        "microrganismo": cultura.microrganismo,
        "obs": cultura.obs,
        "antibiograma": [
            {"antibiotico": a.antibiotico, "sensibilidade": a.sensibilidade}
            for a in svc.get_antibiograma(cultura)
        ],
    }


def _ser_atb_raw(registro):
    """Registro cru de prescrição.

    Devolvido ao lado dos períodos fundidos porque ``get_periodos_atb`` normaliza
    o nome cortando no primeiro token com dígito — "MEROPENEM 1G" e
    "MEROPENEM 2G" viram um período só, e um escalonamento de dose desaparece.
    Quem precisa da dose corrente deve usar estes registros (ou o Sumário do
    prontuário), nunca os períodos.
    """
    return {
        "medicamento": registro.medicamento,
        "acomodacao": registro.acomodacao,
        "dt_inicio": registro.dt_inicio,
        "dias_solic": registro.dias_solic,
        "dias_ccih": registro.dias_ccih,
        # Foto da data de importacao, NAO o dia de tratamento de hoje.
        "dias_em_uso_na_importacao": registro.dias_em_uso,
        "medico": registro.medico,
        "importado_em": registro.importado_em,
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@api_view
def hospitais(request):
    """GET /api/v1/hospitais/ — siglas disponíveis, para validar a configuração."""
    return JsonResponse({
        "hospitais": [
            {"sigla": h.sigla, "nome": h.nome}
            for h in Hospital.objects.filter(ativo=True).order_by("sigla")
        ]
    })


@api_view
def pacientes(request):
    """GET /api/v1/pacientes/?q=&hospital= — desambiguação por nome ou prontuário."""
    hospital, erro = _resolver_hospital(request)
    if erro:
        return erro

    termo = (request.GET.get("q") or "").strip()
    if not termo:
        return _erro("parametro 'q' e obrigatorio", 400)

    achados = svc.buscar_pacientes(termo, hospital)[:MAX_BUSCA]
    return JsonResponse({
        "hospital": hospital.sigla,
        "termo": termo,
        "total": len(achados),
        "pacientes": [
            {"id": p.pk, "prontuario": p.prontuario, "nome": p.nome} for p in achados
        ],
    })


@api_view
def paciente(request):
    """GET /api/v1/paciente/?prontuario=&hospital=

    Endpoint gordo de propósito: devolve tudo que o dossiê precisa numa chamada.
    """
    hospital, erro = _resolver_hospital(request)
    if erro:
        return erro

    prontuario = (request.GET.get("prontuario") or "").strip()
    if not prontuario:
        return _erro("parametro 'prontuario' e obrigatorio", 400)

    pac = hospital.pacientes.filter(prontuario=prontuario).first()
    if pac is None:
        # Prontuario e string no banco ("620", "13986"), populado por planilha.
        # Tentar sem zeros a esquerda antes de desistir.
        alternativo = prontuario.lstrip("0")
        if alternativo and alternativo != prontuario:
            pac = hospital.pacientes.filter(prontuario=alternativo).first()

    if pac is None:
        return _erro(
            "paciente nao encontrado",
            404,
            prontuario=prontuario,
            hospital=hospital.sigla,
            dica="conferir se a numeracao do prontuario do SMPEP e a mesma importada no ccih",
        )

    culturas = list(svc.get_culturas(pac))
    atb_raw = pac.controle_atb.order_by("dt_inicio", "medicamento")

    return JsonResponse({
        "hospital": hospital.sigla,
        "paciente": {"id": pac.pk, "prontuario": pac.prontuario, "nome": pac.nome},
        "internamentos": svc.get_internamentos(pac),
        "culturas": [_ser_cultura(c) for c in culturas],
        "atb_raw": [_ser_atb_raw(r) for r in atb_raw],
        "atb_periodos": svc.get_periodos_atb(pac),
        "resistentes_na_ultima_cultura": sorted(
            svc.get_antibioticos_resistentes_recentes(pac)
        ),
        "_avisos": [
            "atb_periodos funde registros com gap<=1 dia e normaliza o nome cortando no "
            "primeiro token com digito; escalonamento de dose nao aparece. Para dose "
            "corrente use atb_raw ou o Sumario do prontuario.",
            "dias_em_uso_na_importacao e foto da data de importacao, nao o dia de "
            "tratamento de hoje.",
        ],
    })


@api_view
def cobertura(request):
    """GET /api/v1/cobertura/?hospital=

    Mesmo dado do ``relatorio_consultor`` sem prontuários: intervalos de
    cobertura clínica (micro por ``dt_coleta``, ATB por ``dt_inicio``; gap > 14
    dias separa intervalos) e a data do último upload de cada tipo. Um cliente
    usa o fim do último intervalo para decidir o período do próximo relatec.
    """
    hospital, erro = _resolver_hospital(request)
    if erro:
        return erro

    def intervalos(lista):
        return [{"inicio": ini, "fim": fim} for ini, fim in lista]

    return JsonResponse({
        "hospital": hospital.sigla,
        "microbiologia": {
            "cobertura": intervalos(svc.get_cobertura_culturas(hospital)),
            "ultimo_upload": svc.get_ultima_importacao(hospital, "microbiologia"),
        },
        "antimicrobianos": {
            "cobertura": intervalos(svc.get_cobertura_atb(hospital)),
            "ultimo_upload": svc.get_ultima_importacao(hospital, "controle_atb"),
        },
    })


# --------------------------------------------------------------------------- #
# Escrita: importação de planilha (único endpoint que grava)
# --------------------------------------------------------------------------- #

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
TIPOS_IMPORTACAO = {"microbiologia": (".xlsx",), "controle_atb": (".xls", ".xlsx")}


@csrf_exempt
@require_POST
def importar(request):
    """POST /api/v1/importar/?hospital=SIGLA&tipo=microbiologia|controle_atb

    Corpo multipart com o campo ``arquivo`` (o .xlsx/.xls do Relatec). Mesmo
    caminho dos comandos ``importar_microbiologia_ssh`` / ``importar_atb_ssh``
    (``importer_service.importar_com_validacao``): recusa tipo errado e planilha
    de outro hospital (CNES/Origem). Existe para o cliente automatizado
    (playwright-cli-smpep) atualizar o ccih sem SSH. CSRF não se aplica: a
    autenticação é o token Bearer, não cookie de sessão.

    Respostas: 200 ``{tipo, hospital, registros}``; 400 parâmetro/arquivo
    inválido ou recusado pela validação; 401/503 como os GET.
    """
    if not config("API_TOKEN", default=""):
        return _erro("API_TOKEN nao configurado no servidor", 503)
    if not _token_valido(request):
        return _erro("token ausente ou invalido", 401)

    hospital, erro = _resolver_hospital(request)
    if erro:
        return erro

    tipo = (request.GET.get("tipo") or "").strip()
    if tipo not in TIPOS_IMPORTACAO:
        return _erro("parametro 'tipo' deve ser microbiologia ou controle_atb", 400)

    arquivo = request.FILES.get("arquivo")
    if arquivo is None:
        return _erro("campo multipart 'arquivo' e obrigatorio", 400)
    sufixo = Path(arquivo.name).suffix.lower()
    if sufixo not in TIPOS_IMPORTACAO[tipo]:
        return _erro("extensao %s invalida para %s" % (sufixo, tipo), 400)
    if arquivo.size > MAX_UPLOAD_BYTES:
        return _erro("arquivo maior que %d MB" % (MAX_UPLOAD_BYTES // 2**20), 400)

    # nome original preservado (vai para Importacao.arquivo); pasta temporaria propria
    with tempfile.TemporaryDirectory(prefix="ccih_api_") as tmp:
        destino = Path(tmp) / Path(arquivo.name).name
        with open(destino, "wb") as fh:
            for parte in arquivo.chunks():
                fh.write(parte)
        try:
            n = importer_service.importar_com_validacao(destino, hospital, None, tipo)
        except ValueError as exc:
            return _erro(str(exc), 400)

    return JsonResponse({"tipo": tipo, "hospital": hospital.sigla, "registros": n})


@api_view
def formulario(request):
    """GET /api/v1/formulario/?hospital=

    Antimicrobianos que já foram efetivamente prescritos neste hospital — a
    aproximação disponível do formulário da farmácia. É a lista da qual o agente
    pode sugerir; o antibiograma diz o que funciona, isto diz o que existe.
    """
    hospital, erro = _resolver_hospital(request)
    if erro:
        return erro

    itens = svc.get_formulario(hospital)
    return JsonResponse({
        "hospital": hospital.sigla,
        "total": len(itens),
        "antimicrobianos": itens,
        "_origem": (
            "DISTINCT de ControleAtbRaw.medicamento normalizado, sobre todo o historico "
            "importado. Nao e o formulario oficial da farmacia: e o que ja foi prescrito."
        ),
    })
