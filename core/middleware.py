SESSION_KEY = "hospital_atual_id"


class HospitalAtualMiddleware:
    """Resolve o hospital ativo da sessão e o expõe em ``request``.

    Como um usuário pode estar vinculado a vários hospitais (cada um com seu
    papel), as views e templates precisam de um hospital "ativo". Ele fica
    guardado na sessão e pode ser trocado pelo seletor da navbar.

    Atributos adicionados ao request:
      - ``hospital_atual``: instância de Hospital ou None
      - ``papel_atual``: papel do usuário nesse hospital ou None
      - ``hospitais_disponiveis``: lista de hospitais a que o usuário tem acesso
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.hospital_atual = None
        request.papel_atual = None
        request.hospitais_disponiveis = []

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            disponiveis = list(user.hospitais_disponiveis())
            request.hospitais_disponiveis = disponiveis

            atual = None
            hid = request.session.get(SESSION_KEY)
            if hid is not None:
                atual = next((h for h in disponiveis if h.pk == hid), None)
            if atual is None and disponiveis:
                atual = disponiveis[0]
                request.session[SESSION_KEY] = atual.pk

            request.hospital_atual = atual
            if atual is not None:
                request.papel_atual = user.papel_em(atual)

        return self.get_response(request)
