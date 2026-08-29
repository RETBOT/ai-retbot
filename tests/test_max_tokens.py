"""
Tests para el soporte de max_tokens en los endpoints de chat

- build_ollama_payload: agrega options.num_predict SOLO si es valido, nunca 0
  (en Ollama num_predict=0 significa "sin limite")
- _parse_max_tokens: 400 uniforme para valores invalidos
- El endpoint de streaming valida ANTES de tocar Ollama (el 400 no genera SSE)
"""
import pytest
from fastapi import HTTPException

from core.models import build_ollama_payload, _parse_max_tokens


def test_payload_sin_max_tokens_es_como_antes():
    """Sin max_tokens no aparece num_predict (comportamiento identico)"""
    payload = build_ollama_payload(
        model="mi_modelo",
        messages=[{"role": "user", "content": "hola"}],
        stream=True,
    )
    assert payload["model"] == "mi_modelo"
    assert payload["stream"] is True
    assert payload["options"]["keep_alive"] == 300
    assert "num_predict" not in payload["options"]


def test_payload_con_max_tokens_incluye_num_predict():
    payload = build_ollama_payload(
        model="m", messages=[], stream=True, num_predict=10
    )
    assert payload["options"]["num_predict"] == 10


def test_payload_nunca_envia_num_predict_cero():
    """num_predict=0 en Ollama significa 'sin limite': nunca debe llegar"""
    for invalido in (0, -1):
        payload = build_ollama_payload(
            model="m", messages=[], stream=True, num_predict=invalido
        )
        assert "num_predict" not in payload["options"]


def test_payload_keep_alive_configurable():
    payload = build_ollama_payload(
        model="m", messages=[], stream=False, keep_alive=600, num_predict=5
    )
    assert payload["options"]["keep_alive"] == 600
    assert payload["options"]["num_predict"] == 5


def test_parse_max_tokens_ausente_es_none():
    assert _parse_max_tokens({}) is None
    assert _parse_max_tokens({"messages": []}) is None


@pytest.mark.parametrize("invalido", [0, -1, True, "abc", "100", 1.5])
def test_parse_max_tokens_rechaza_invalidos(invalido):
    with pytest.raises(HTTPException) as exc:
        _parse_max_tokens({"max_tokens": invalido})
    assert exc.value.status_code == 400
    assert "positive integer" in exc.value.detail


def test_parse_max_tokens_acepta_positivo():
    assert _parse_max_tokens({"max_tokens": 1}) == 1
    assert _parse_max_tokens({"max_tokens": 999}) == 999


@pytest.mark.asyncio
async def test_streaming_400_con_max_tokens_invalido(client, test_user, auth_headers):
    """Streaming: max_tokens invalido -> 400 (antes de tocar Ollama)"""
    response = await client.post(
        "/api/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "mi_modelo",
            "messages": [{"role": "user", "content": "test"}],
            "stream": True,
            "max_tokens": -5,
        },
    )
    assert response.status_code == 400
    assert "positive integer" in response.json()["detail"]


@pytest.mark.asyncio
async def test_streaming_400_con_max_tokens_bool(client, test_user, auth_headers):
    """bool es invalido aunque isinstance(True, int)"""
    response = await client.post(
        "/api/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "mi_modelo",
            "messages": [{"role": "user", "content": "test"}],
            "stream": True,
            "max_tokens": True,
        },
    )
    assert response.status_code == 400