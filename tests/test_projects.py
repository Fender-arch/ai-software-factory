def test_create_project_and_message(client):
    created = client.post(
        "/projects",
        json={"name": "Auto CRM", "product_type": "telegram_bot"},
    )
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Auto CRM"
    assert project["status"] == "NEW"

    msg = client.post(
        f"/projects/{project['id']}/messages",
        json={"text": "Need a booking bot"},
    )
    assert msg.status_code == 201
    body = msg.json()
    assert body["text"] == "Need a booking bot"
    assert body["kind"] == "TEXT"

    got = client.get(f"/projects/{project['id']}")
    assert got.status_code == 200
    assert got.json()["status"] == "INTERVIEW"


def test_ingest_voice_uses_stub_stt(client):
    created = client.post("/projects", json={"name": "Voice Project"})
    project_id = created.json()["id"]

    response = client.post(
        f"/projects/{project_id}/messages/voice",
        files={"file": ("note.ogg", b"fake-audio-bytes", "audio/ogg")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == "VOICE"
    assert "stub transcript" in data["text"]
    assert data["stt_meta"]["stt_provider"] == "StubSTT"
