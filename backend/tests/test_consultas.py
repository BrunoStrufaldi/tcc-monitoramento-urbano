"""Testes das rotas de consulta do painel.

O painel só consulta. Os dados são gravados direto no banco pelas funções do
conftest, do mesmo jeito que a detecção faz.
"""

from fastapi.testclient import TestClient

from app.models.dado_contextual import DadoContextual
from app.models.fonte_dados import FonteDados
from app.models.localizacao import Localizacao
from app.models.regiao import Regiao


def _gravar(db_session, *objetos):
    db_session.add_all(objetos)
    db_session.commit()
    return objetos


def test_listar_e_filtrar_eventos(client: TestClient, criar_evento):
    assert client.get("/eventos").json() == []

    alagamento = criar_evento(
        titulo="Teste de alagamento",
        tipo="alagamento",
        severidade="alta",
        status="ativo",
        latitude=-23.5505,
        longitude=-46.6333,
    )
    criar_evento(titulo="Trânsito", tipo="transito", status="em_analise")

    dados = client.get("/eventos").json()
    assert len(dados) == 2
    item = next(d for d in dados if d["id"] == alagamento.id)
    assert item["titulo"] == "Teste de alagamento"
    assert item["latitude"] == -23.5505
    assert item["longitude"] == -46.6333

    assert client.get(f"/eventos/{alagamento.id}").json()["id"] == alagamento.id
    assert [e["status"] for e in client.get("/eventos?status=em_analise").json()] == ["em_analise"]
    assert [e["tipo"] for e in client.get("/eventos?tipo=alagamento").json()] == ["alagamento"]


def test_filtros_das_tabelas_ligadas_ao_evento(client: TestClient, db_session, criar_evento, criar_evidencia):
    evento = criar_evento()
    outro = criar_evento(titulo="Outro evento")
    evidencia = criar_evidencia(evento.id, tipo="imagem", classe_detectada="carro", confianca=0.91)
    criar_evidencia(evento.id, tipo="video")
    criar_evidencia(outro.id)

    assert client.get(f"/evidencias/{evidencia.id}").json()["classe_detectada"] == "carro"
    assert len(client.get(f"/evidencias?evento_id={evento.id}").json()) == 2
    assert [e["tipo"] for e in client.get("/evidencias?tipo=video").json()] == ["video"]

    chuva, _, _ = _gravar(
        db_session,
        DadoContextual(evento_id=evento.id, categoria="contexto", chave="precipitacao_mm_h", valor_numerico=45.2, unidade="mm/h"),
        DadoContextual(evento_id=evento.id, categoria="contexto", chave="umidade", valor_numerico=80),
        DadoContextual(categoria="outra", chave="sem_evento"),
    )
    assert client.get(f"/dados-contextuais/{chuva.id}").json()["valor_numerico"] == 45.2
    assert len(client.get(f"/dados-contextuais?evento_id={evento.id}").json()) == 2
    assert [d["chave"] for d in client.get("/dados-contextuais?categoria=outra").json()] == ["sem_evento"]


def test_filtros_dos_cadastros(client: TestClient, db_session):
    zona_leste, _ = _gravar(db_session, Regiao(nome="Zona Leste", codigo="ZL"), Regiao(nome="Inativa", ativo=False))
    _gravar(
        db_session,
        Localizacao(latitude=-23.5505, longitude=-46.6333, endereco="Av. Paulista, 1000", regiao_id=zona_leste.id),
        Localizacao(latitude=-23.56, longitude=-46.64),
        FonteDados(nome="Câmera", tipo="yolo"),
        FonteDados(nome="INMET", tipo="clima"),
    )

    assert [r["nome"] for r in client.get("/regioes?ativo=true").json()] == ["Zona Leste"]
    assert client.get(f"/regioes/{zona_leste.id}").json()["codigo"] == "ZL"

    localizacoes = client.get(f"/localizacoes?regiao_id={zona_leste.id}").json()
    assert [loc["endereco"] for loc in localizacoes] == ["Av. Paulista, 1000"]
    assert localizacoes[0]["cidade"] == "São Paulo"

    assert [f["nome"] for f in client.get("/fontes?tipo=clima").json()] == ["INMET"]
    assert client.get("/logs").status_code == 200


def test_id_inexistente_retorna_404(client: TestClient):
    for rota in ("eventos", "evidencias", "dados-contextuais", "regioes", "localizacoes", "fontes"):
        assert client.get(f"/{rota}/9999").status_code == 404, rota


def test_rotas_de_escrita_nao_existem(client: TestClient):
    """Sem login, uma rota pública de escrita deixaria qualquer um alterar os dados."""
    for rota in ("eventos", "evidencias", "dados-contextuais", "regioes", "localizacoes", "fontes"):
        assert client.post(f"/{rota}", json={}).status_code == 405, rota
        assert client.patch(f"/{rota}/1", json={}).status_code == 405, rota
        assert client.delete(f"/{rota}/1").status_code == 405, rota

    # Rotas antigas da detecção que gravavam pelo painel. 405 porque o painel
    # está em "/" e só aceita GET.
    for rota in ("/deteccao/confirmar", "/deteccao/frame", "/deteccao/simular", "/deteccao/video"):
        assert client.post(rota).status_code in (404, 405), rota
