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
