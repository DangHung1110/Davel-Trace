from __future__ import annotations

from BE.app.core.config import Settings
from BE.app.modules.ai_assistance.domain import ExplanationDraft, InterpretationDraft
from BE.app.modules.ai_assistance.service import AiAssistanceService


def test_interpretation_never_sends_catalog_and_normalizes_trip_context_times():
    captured = {}
    catalog = [
        {"poi_id": f"cafe-{i}", "name": f"Quán cà phê Đà Nẵng {i}", "verified": True}
        for i in range(750)
    ] + [{"poi_id": "dragon", "name": "Cầu Rồng", "verified": True}]
    def complete(prompt, schema, settings):
        captured["prompt"] = prompt
        return InterpretationDraft(travelers=2, must_visit=["Cầu Rồng"]).model_dump(mode="json")
    service = AiAssistanceService(Settings(llm_provider="local", _env_file=None), completer=complete)
    result = service.interpret("Đi 2 người, ghé Cầu Rồng", catalog=catalog,
        trip_context={"day_start": "07:00:00", "day_end": "21:00:00"})
    assert '"day_start": "07:00"' in captured["prompt"]
    assert '"day_end": "21:00"' in captured["prompt"]
    assert "07:00:00" not in captured["prompt"]
    assert "Quán cà phê Đà Nẵng 749" not in captured["prompt"]
    assert len(captured["prompt"]) < 2500
    assert result["hard_constraints"]["must_visit"] == ["dragon"]
    assert "KNOWN_POI_NAMES" not in captured["prompt"]
    first = captured["prompt"]
    service.interpret("Đi 2 người, ghé Cầu Rồng", catalog=[],
        trip_context={"day_start": "07:00:00", "day_end": "21:00:00"})
    assert captured["prompt"] == first


def test_interpretation_resolves_names_locally_without_guessing_ambiguous_ids():
    catalog = [
        {"poi_id": "bridge", "name": "Cầu Rồng", "verified": True},
        {"poi_id": "cafe-1", "name": "Cà phê An", "verified": True, "lat": 16.1, "lon": 108.1},
        {"poi_id": "cafe-2", "name": "Cà phê An", "verified": True, "lat": 16.2, "lon": 108.2},
        {"poi_id": "bad", "name": "Biển bịa", "verified": False},
    ]
    def complete(prompt, schema, settings):
        assert "Cà phê An" not in prompt
        return {"must_visit": ["cau rong", "ca phe an", "Biển bịa"],
                "avoid": ["ca phe an"], "activities": ["biển"]}
    service = AiAssistanceService(Settings(llm_provider="local", _env_file=None), completer=complete)
    result = service.interpret("ghé cau rong, ca phe an, Biển bịa", catalog=catalog, trip_context={})
    assert result["hard_constraints"]["must_visit"] == ["bridge"]
    assert result["hard_constraints"]["avoid"] == []
    pending = result["place_resolutions"]
    assert [(item["constraint"], item["status"]) for item in pending] == [
        ("must_visit", "ambiguous"), ("must_visit", "not_found"), ("avoid", "ambiguous")]
    assert [item["poi_id"] for item in pending[0]["candidates"]] == ["cafe-1", "cafe-2"]
    assert pending[0]["candidates"][1]["lat"] == 16.2
    assert pending[1]["candidates"] == []
    assert "Biển bịa" in result["unresolved"]
    assert result["soft_preferences"]["activities"] == ["biển"]


def test_interpretation_separates_hard_soft_and_unresolved() -> None:
    def complete(prompt, schema, settings):
        assert "UNTRUSTED_TRAVELER_TEXT" in prompt
        return InterpretationDraft(
            budget=3_000_000,
            travelers=2,
            must_visit=["Cầu Rồng", "Địa điểm bịa"],
            food_preferences=["hải sản"],
            accessibility=["wheelchair"],
            assumptions=["Khởi hành lúc 08:00"],
        ).model_dump(mode="json")

    service = AiAssistanceService(
        Settings(llm_provider="local", _env_file=None),
        completer=complete,
    )
    result = service.interpret(
        "đi 2 người, phải ghé Cầu Rồng và Địa điểm bịa",
        catalog=[{"poi_id": "dragon", "name": "Cầu Rồng", "verified": True}],
        trip_context={"destination": "da_nang"},
    )
    assert result["status"] == "review_required"
    assert result["hard_constraints"]["must_visit"] == ["dragon"]
    assert result["hard_constraints"]["accessibility"] == ["wheelchair"]
    assert result["soft_preferences"]["food_preferences"] == ["hải sản"]
    assert "Địa điểm bịa" in result["unresolved"]


def test_model_cannot_turn_unmentioned_catalog_places_into_hard_constraints():
    service = AiAssistanceService(
        Settings(llm_provider="local", _env_file=None),
        completer=lambda *args: {"must_visit": ["Cầu Rồng"], "activities": ["biển"]},
    )
    result = service.interpret("thích biển", trip_context={}, catalog=[
        {"poi_id": "bridge", "name": "Cầu Rồng", "verified": True},
    ])
    assert result["hard_constraints"]["must_visit"] == []
    assert result["place_resolutions"] == []
    assert result["unresolved"] == ["Cầu Rồng"]


def test_interpretation_prompt_does_not_include_account_or_token_data() -> None:
    seen = {}

    def complete(prompt, schema, settings):
        seen["prompt"] = prompt
        return InterpretationDraft().model_dump(mode="json")

    service = AiAssistanceService(
        Settings(llm_provider="local", _env_file=None), completer=complete
    )
    service.interpret(
        "ưu tiên bảo tàng",
        catalog=[],
        trip_context={
            "destination": "da_nang",
            "account_id": "private-account",
            "access_token": "private-token",
        },
    )
    assert "private-account" not in seen["prompt"]
    assert "private-token" not in seen["prompt"]


def test_explanation_rejects_unknown_evidence_key() -> None:
    def complete(prompt, schema, settings):
        return ExplanationDraft(
            summary="Lịch phù hợp.",
            reasons=[{"text": "Thông tin không có nguồn", "evidence_keys": ["made_up"]}],
        ).model_dump(mode="json")

    service = AiAssistanceService(
        Settings(llm_provider="local", _env_file=None), completer=complete
    )
    result = service.explain(
        alternative_id="alt-1",
        data_version="danang-v1",
        evidence={"budget": 3_000_000, "gate": {"passed": True}},
        warnings=["mưa"],
    )
    assert result["source"] == "deterministic"
    assert result["provider"] is None
    assert result["warnings"] == ["mưa"]


def test_readiness_is_secret_free() -> None:
    secret = "gemini-secret-value"
    service = AiAssistanceService(
        Settings(
            llm_provider="gemini",
            gemini_api_key=secret,
            llm_model="gemini-test",
            _env_file=None,
        )
    )
    readiness = service.readiness()
    assert readiness["configured"] is True
    assert readiness["provider"] == "gemini"
    assert secret not in repr(readiness)
