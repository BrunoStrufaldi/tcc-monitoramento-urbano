"""Testes end-to-end — fluxo completo do sistema de notificações urbanas."""

from fastapi.testclient import TestClient


def _criar_regiao(client: TestClient) -> int:
    r = client.post("/regioes", json={"nome": "Centro", "descricao": "Região central"})
    return r.json()["id"]


def _criar_localizacao(client: TestClient, regiao_id: int) -> int:
    r = client.post(
        "/localizacoes",
        json={"latitude": -23.55, "longitude": -46.63, "regiao_id": regiao_id},
    )
    return r.json()["id"]


def _criar_fonte(client: TestClient) -> int:
    r = client.post(
        "/fontes",
        json={"nome": "Câmera Via App", "tipo": "camera", "url": "http://exemplo.com/cam"},
    )
    return r.json()["id"]


def test_fluxo_completo_criar_evento_completo(client: TestClient):
    """Fluxo: criar evento com todos os relacionamentos e verificar dados."""
    regiao_id = _criar_regiao(client)
    localizacao_id = _criar_localizacao(client, regiao_id)
    fonte_id = _criar_fonte(client)

    # 1. Criar evento com todos os campos
    criar = client.post(
        "/eventos",
        json={
            "titulo": "Alagamento na Av. Paulista",
            "descricao": "Alagamento severo após chuva forte",
            "tipo": "alagamento",
            "severidade": "critica",
            "status": "ativo",
            "localizacao_id": localizacao_id,
            "regiao_id": regiao_id,
            "fonte_id": fonte_id,
            "confianca": 0.85,
        },
    )
    assert criar.status_code == 201
    evento = criar.json()
    evento_id = evento["id"]
    assert evento["titulo"] == "Alagamento na Av. Paulista"
    assert evento["severidade"] == "critica"
    assert float(evento["confianca"]) == 0.85

    # 2. Verificar que aparece na listagem
    listar = client.get("/eventos")
    assert any(e["id"] == evento_id for e in listar.json())

    # 3. Criar notificação para o evento
    notif = client.post(
        "/notificacoes",
        json={
            "evento_id": evento_id,
            "titulo": "Alerta: Alagamento",
            "mensagem": "Evite a região central",
            "canal": "push",
        },
    )
    assert notif.status_code == 201
    notif_id = notif.json()["id"]

    # 4. Criar evidência visual
    evid = client.post(
        "/evidencias",
        json={
            "evento_id": evento_id,
            "tipo": "imagem",
            "url": "http://exemplo.com/foto.jpg",
        },
    )
    assert evid.status_code == 201

    # 5. Criar dado contextual
    ctx = client.post(
        "/dados-contextuais",
        json={
            "evento_id": evento_id,
            "categoria": "clima",
            "chave": "precipitacao",
            "valor_texto": "Chuva de 45mm/h nas últimas 2 horas",
        },
    )
    assert ctx.status_code == 201

    # 6. Atualizar status do evento
    patch = client.patch(f"/eventos/{evento_id}", json={"status": "em_analise"})
    assert patch.status_code == 200
    assert patch.json()["status"] == "em_analise"

    # 7. Marcar notificação como lida
    lida = client.patch(f"/notificacoes/{notif_id}/lida")
    assert lida.status_code == 200
    assert lida.json()["status"] == "lida"

    # 8. Verificar dados contextuais filtrados
    ctx_list = client.get(f"/dados-contextuais?evento_id={evento_id}")
    assert len(ctx_list.json()) == 1

    # 9. Verificar evidências filtradas
    evid_list = client.get(f"/evidencias?evento_id={evento_id}")
    assert len(evid_list.json()) == 1

    # 10. Verificar logs foram criados
    logs = client.get(f"/logs?evento_id={evento_id}")
    assert logs.status_code == 200

    # 11. Resolver evento
    resolve = client.patch(
        f"/eventos/{evento_id}",
        json={"status": "resolvido"},
    )
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolvido"


def test_fluxo_deteccao_yolo_para_evento(client: TestClient):
    """Fluxo: simular detecção YOLO e criar evento a partir dela."""
    # 1. Simular detecção
    deteccao = client.post("/deteccao/simular", json={"num_deteccoes": 2})
    assert deteccao.status_code == 200
    resultados = deteccao.json()
    assert len(resultados) == 2

    # 2. Criar evento a partir da detecção
    det = resultados[0]
    regiao_id = _criar_regiao(client)
    localizacao_id = _criar_localizacao(client, regiao_id)
    fonte_id = _criar_fonte(client)

    criar = client.post(
        "/eventos",
        json={
            "titulo": f"Detectado: {det['nome']}",
            "tipo": det["tipo"],
            "severidade": det["severidade"],
            "localizacao_id": localizacao_id,
            "fonte_id": fonte_id,
            "confianca": det["confianca"],
        },
    )
    assert criar.status_code == 201
    assert criar.json()["severidade"] == det["severidade"]


def test_fluxo_fusao_dados(client: TestClient):
    """Fluxo: criar evento e verificar fusão de dados."""
    regiao_id = _criar_regiao(client)
    localizacao_id = _criar_localizacao(client, regiao_id)

    criar = client.post(
        "/eventos",
        json={
            "titulo": "Incêndio em prédio",
            "tipo": "incendio",
            "severidade": "critica",
            "localizacao_id": localizacao_id,
        },
    )
    evento_id = criar.json()["id"]

    # Consultar fusão
    fusao = client.get(f"/fusion/eventos/{evento_id}/confiabilidade")
    assert fusao.status_code == 200
    dados = fusao.json()
    assert "confiabilidade" in dados
    assert "nivel" in dados
    assert dados["nivel"] in ("alta", "media", "baixa")


def test_fluxo_notificacoes_lote(client: TestClient):
    """Fluxo: criar múltiplas notificações e filtrar por status."""
    regiao_id = _criar_regiao(client)
    localizacao_id = _criar_localizacao(client, regiao_id)

    evento = client.post(
        "/eventos",
        json={"titulo": "Teste lote", "tipo": "transito", "localizacao_id": localizacao_id},
    )
    evento_id = evento.json()["id"]

    # Criar 3 notificações
    for i in range(3):
        client.post(
            "/notificacoes",
            json={"evento_id": evento_id, "titulo": f"Notif {i}", "mensagem": "msg"},
        )

    # Listar todas
    todas = client.get("/notificacoes")
    assert len(todas.json()) >= 3

    # Filtrar por pendentes
    pendentes = client.get("/notificacoes?status=pendente")
    assert len(pendentes.json()) >= 3


def test_health_e_raiz(client: TestClient):
    """Verifica endpoints de saúde do sistema."""
    raiz = client.get("/")
    assert raiz.status_code == 200
    assert raiz.json()["status"] == "online"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    # SSE endpoint
    connected = client.get("/events/connected")
    assert connected.status_code == 200
    assert "connected" in connected.json()
