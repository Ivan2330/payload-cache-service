"""Integration tests: the endpoints, through a real ASGI transport."""

import pytest

pytestmark = pytest.mark.asyncio

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
EXPECTED = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"


async def test_create_then_read_returns_the_sample_output(client):
    created = await client.post("/payload", json=SAMPLE)
    assert created.status_code == 201
    identifier = created.json()["id"]

    fetched = await client.get(f"/payload/{identifier}")
    assert fetched.status_code == 200
    assert fetched.json() == {"output": EXPECTED}


async def test_repeated_create_reuses_the_identifier(client, transformer):
    first = await client.post("/payload", json=SAMPLE)
    second = await client.post("/payload", json=SAMPLE)

    assert first.json()["id"] == second.json()["id"]
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert transformer.calls == 1


async def test_lists_of_different_lengths_are_rejected(client):
    response = await client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c"]})
    assert response.status_code == 422
    assert "same length" in response.text


async def test_empty_lists_are_rejected(client):
    response = await client.post("/payload", json={"list_1": [], "list_2": []})
    assert response.status_code == 422


async def test_unknown_payload_returns_404(client):
    response = await client.get("/payload/0000000000000000")
    assert response.status_code == 404


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
