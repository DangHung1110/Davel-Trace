from __future__ import annotations

from BE.app.core.config import Settings
from BE.app.modules.ai_assistance.domain import ExplanationDraft, InterpretationDraft
from BE.app.modules.ai_assistance.service import AiAssistanceService
from BE.app.modules.ai_assistance.service import _candidate_names


def test_interpretation_bounds_catalog_and_normalizes_trip_context_times():
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


def test_candidate_shortlist_handles_accents_and_bounds_broad_matches():
    catalog = [{"name": f"Bãi biển Đà Nẵng {i}", "verified": True} for i in range(750)]
    catalog += [{"name": "Cầu Rồng", "verified": True}, {"name": "Biển bịa", "verified": False}]
    assert _candidate_names("ghe cau rong", catalog) == ["Cầu Rồng"]
    names = _candidate_names("thích biển Đà Nẵng", catalog)
    assert len(names) <= 24 and sum(map(len, names)) <= 1200
    assert "Biển bịa" not in names
    assert _candidate_names("Đi Đà Nẵng 2 người, ngân sách 3 triệu", catalog) == []


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
        catalog=[{"poi_id": "dragon", "name": "Cầu Rồng"}],
        trip_context={"destination": "da_nang"},
    )
    assert result["status"] == "review_required"
    assert result["hard_constraints"]["must_visit"] == ["dragon"]
    assert result["hard_constraints"]["accessibility"] == ["wheelchair"]
    assert result["soft_preferences"]["food_preferences"] == ["hải sản"]
    assert "Địa điểm bịa" in result["unresolved"]


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
