"""Testes de integração dos endpoints principais."""

from fastapi.testclient import TestClient


def test_raiz_retorna_status_online(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_listar_eventos_vazio(client: TestClient):
    response = client.get("/eventos")
    assert response.status_code == 200
    assert response.json() == []


def test_criar_e_listar_evento(client: TestClient):
    payload = {
        "titulo": "Teste de alagamento",
        "tipo": "alagamento",
        "severidade": "alta",
        "status": "ativo",
        "latitude": -23.5505,
        "longitude": -46.6333,
    }
    criar = client.post("/eventos", json=payload)
    assert criar.status_code == 201
    criado = criar.json()
    assert criado["titulo"] == "Teste de alagamento"
    assert criado["latitude"] == -23.5505
    assert criado["longitude"] == -46.6333

    listar = client.get("/eventos")
    assert listar.status_code == 200
    assert len(listar.json()) == 1


def test_obter_evento_por_id(client: TestClient):
    payload = {
        "titulo": "Evento específico",
        "tipo": "transito",
        "latitude": -23.5614,
        "longitude": -46.6559,
    }
    criar = client.post("/eventos", json=payload)
    evento_id = criar.json()["id"]

    response = client.get(f"/eventos/{evento_id}")
    assert response.status_code == 200
    assert response.json()["id"] == evento_id


def test_obter_evento_inexistente_retorna_404(client: TestClient):
    response = client.get("/eventos/9999")
    assert response.status_code == 404


def test_criar_evento_sem_coordenadas_retorna_422(client: TestClient):
    payload = {
        "titulo": "Sem localização",
        "tipo": "transito",
    }
    response = client.post("/eventos", json=payload)
    assert response.status_code == 422


def test_filtrar_eventos_por_status(client: TestClient):
    for status in ["ativo", "resolvido"]:
        client.post(
            "/eventos",
            json={
                "titulo": f"Evento {status}",
                "tipo": "transito",
                "status": status,
                "latitude": -23.55,
                "longitude": -46.63,
            },
        )

    ativos = client.get("/eventos?status=ativo")
    assert len(ativos.json()) == 1
    assert ativos.json()[0]["status"] == "ativo"

    resolvidos = client.get("/eventos?status=resolvido")
    assert len(resolvidos.json()) == 1
    assert resolvidos.json()[0]["status"] == "resolvido"


def test_patch_atualiza_titulo(client: TestClient):
    criar = client.post(
        "/eventos",
        json={"titulo": "Antes", "tipo": "transito", "latitude": -23.55, "longitude": -46.63},
    )
    evento_id = criar.json()["id"]

    response = client.patch(f"/eventos/{evento_id}", json={"titulo": "Depois"})
    assert response.status_code == 200
    assert response.json()["titulo"] == "Depois"
    assert response.json()["tipo"] == "transito"


def test_patch_atualiza_status(client: TestClient):
    criar = client.post(
        "/eventos",
        json={"titulo": "Evento", "tipo": "alagamento", "latitude": -23.55, "longitude": -46.63},
    )
    evento_id = criar.json()["id"]

    response = client.patch(f"/eventos/{evento_id}", json={"status": "em_analise"})
    assert response.status_code == 200
    assert response.json()["status"] == "em_analise"


def test_patch_evento_inexistente_retorna_404(client: TestClient):
    response = client.patch("/eventos/9999", json={"titulo": "X"})
    assert response.status_code == 404


def test_delete_remove_evento(client: TestClient):
    criar = client.post(
        "/eventos",
        json={"titulo": "Para remover", "tipo": "incendio", "latitude": -23.55, "longitude": -46.63},
    )
    evento_id = criar.json()["id"]

    response = client.delete(f"/eventos/{evento_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == evento_id
    assert data["titulo"] == "Para remover"

    get_after = client.get(f"/eventos/{evento_id}")
    assert get_after.status_code == 404


def test_delete_evento_inexistente_retorna_404(client: TestClient):
    response = client.delete("/eventos/9999")
    assert response.status_code == 404


def test_patch_get_delete_lifecycle(client: TestClient):
    criar = client.post(
        "/eventos",
        json={"titulo": "Lifecycle", "tipo": "transito", "latitude": -23.55, "longitude": -46.63},
    )
    assert criar.status_code == 201
    evento_id = criar.json()["id"]

    get1 = client.get(f"/eventos/{evento_id}")
    assert get1.status_code == 200
    assert get1.json()["titulo"] == "Lifecycle"

    patch = client.patch(f"/eventos/{evento_id}", json={"titulo": "Lifecycle Atualizado", "severidade": "alta"})
    assert patch.status_code == 200
    assert patch.json()["titulo"] == "Lifecycle Atualizado"
    assert patch.json()["severidade"] == "alta"
    assert patch.json()["tipo"] == "transito"

    get2 = client.get(f"/eventos/{evento_id}")
    assert get2.status_code == 200
    assert get2.json()["titulo"] == "Lifecycle Atualizado"

    delete = client.delete(f"/eventos/{evento_id}")
    assert delete.status_code == 200

    get3 = client.get(f"/eventos/{evento_id}")
    assert get3.status_code == 404


def test_patch_com_payload_invalido_retorna_422(client: TestClient):
    criar = client.post(
        "/eventos",
        json={"titulo": "Valido", "tipo": "transito", "latitude": -23.55, "longitude": -46.63},
    )
    evento_id = criar.json()["id"]

    response = client.patch(f"/eventos/{evento_id}", json={"titulo": 12345})
    assert response.status_code == 422

    response2 = client.patch(f"/eventos/{evento_id}", json={"confianca": 999})
    assert response2.status_code == 422


def test_criar_evento_severidade_invalida_retorna_422(client: TestClient):
    response = client.post(
        "/eventos",
        json={
            "titulo": "Teste",
            "tipo": "transito",
            "severidade": "info",
            "latitude": -23.55,
            "longitude": -46.63,
        },
    )
    assert response.status_code == 422


def test_criar_evento_status_invalido_retorna_422(client: TestClient):
    response = client.post(
        "/eventos",
        json={
            "titulo": "Teste",
            "tipo": "transito",
            "status": "cancelado",
            "latitude": -23.55,
            "longitude": -46.63,
        },
    )
    assert response.status_code == 422


def test_patch_severidade_invalida_retorna_422(client: TestClient):
    criar = client.post(
        "/eventos",
        json={"titulo": "Ok", "tipo": "transito", "latitude": -23.55, "longitude": -46.63},
    )
    evento_id = criar.json()["id"]
    response = client.patch(f"/eventos/{evento_id}", json={"severidade": "info"})
    assert response.status_code == 422
