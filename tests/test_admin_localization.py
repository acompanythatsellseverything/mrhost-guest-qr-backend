from app.schemas.localization import LocalizationKind
from app.services import localization as localization_service
from tests.test_admin_auth import login


def test_localization_sync_requires_auth(client) -> None:
    response = client.post(
        "/admin/localization/sync",
        json={
            "kind": "consent",
            "source_translation": {"language_code": "en", "title": "Hi", "body": "Hello"},
        },
    )
    assert response.status_code == 401


def test_localization_sync_returns_generated_translations(client, admin_user, monkeypatch) -> None:
    tokens = login(client, admin_user.email, "Secretpass1!")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    def fake_generate_localized_translations(**kwargs):
        assert kwargs["kind"] == LocalizationKind.CONSENT
        assert kwargs["source_translation"]["language_code"] == "en"
        return [
            {"language_code": "es", "title": "Hola", "body": "Bienvenido"},
            {"language_code": "ru", "title": "Privet", "body": "Dobro pozhalovat"},
        ]

    monkeypatch.setattr(
        localization_service,
        "generate_localized_translations",
        fake_generate_localized_translations,
    )

    response = client.post(
        "/admin/localization/sync",
        json={
            "kind": "consent",
            "source_translation": {"language_code": "en", "title": "Hello", "body": "Welcome"},
            "existing_translations": [{"language_code": "fr", "title": "", "body": ""}],
            "target_languages": ["es", "ru"],
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["translations"][0]["language_code"] == "es"
    assert data["translations"][1]["language_code"] == "ru"


def test_generate_localized_translations_retries_missing_languages(monkeypatch) -> None:
    responses = [
        {
            "translations": [
                {"language_code": "es", "title": "Hola", "body": "Bienvenido"},
            ]
        },
        {
            "translations": [
                {"language_code": "ru", "title": "Privet", "body": "Dobro pozhalovat"},
            ]
        },
    ]
    prompts: list[str] = []

    def fake_request_openrouter_localization(**kwargs):
        prompts.append(kwargs["prompt"])
        return responses.pop(0)

    monkeypatch.setattr(
        localization_service,
        "_request_openrouter_localization",
        fake_request_openrouter_localization,
    )

    translations = localization_service.generate_localized_translations(
        kind=LocalizationKind.CONSENT,
        source_translation={"language_code": "en", "title": "Hello", "body": "Welcome"},
        existing_translations=[],
        target_languages=["es", "ru"],
    )

    assert [item["language_code"] for item in translations] == ["es", "ru"]
    assert "Requested languages: es, ru." in prompts[0]
    assert "Requested languages: ru." in prompts[1]
