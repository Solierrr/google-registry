"""Testes de app.infrastructure.llm.keys.load_llm_keys"""

from app.infrastructure.llm.keys import key_id_for, load_llm_keys


def test_reads_numbered_keys_in_order_per_provider():
    keys = load_llm_keys(
        {
            "GROQ_API_KEY_2": "g2",
            "GEMINI_API_KEY_10": "m10",
            "GEMINI_API_KEY_2": "m2",
            "GROQ_API_KEY_1": "g1",
        }
    )

    assert [(k.provider, k.secret) for k in keys] == [
        ("gemini", "m2"),
        ("gemini", "m10"),
        ("groq", "g1"),
        ("groq", "g2"),
    ]


def test_accepts_the_names_used_by_the_ai_services_today():
    keys = load_llm_keys(
        {
            "GOOGLE_API_KEY": "a",
            "GEMINI_API_KEY2": "b",
            "GEMINI_API_KEY3": "c",
            "GROQ_API_KEY": "d",
            "GROQ_API_KEY2": "e",
        }
    )

    assert [(k.provider, k.secret) for k in keys] == [
        ("gemini", "a"),
        ("gemini", "b"),
        ("gemini", "c"),
        ("groq", "d"),
        ("groq", "e"),
    ]


def test_ignores_empty_values_unknown_providers_and_unrelated_variables():
    keys = load_llm_keys(
        {
            "GEMINI_API_KEY_1": "  ",
            "OPENAI_API_KEY": "x",
            "QDRANT_API_KEY": "y",
            "GOOGLE_KEY_MAPS": "z",
            "PATH": "/usr/bin",
            "GROQ_API_KEY_1": "ok",
        }
    )

    assert [(k.provider, k.secret) for k in keys] == [("groq", "ok")]


def test_same_secret_in_two_variables_counts_once():
    keys = load_llm_keys({"GOOGLE_API_KEY": "same", "GEMINI_API_KEY_1": "same"})

    assert len(keys) == 1


def test_key_id_is_stable_opaque_and_does_not_contain_the_secret():
    key_id = key_id_for("gemini", "super-secret-value")

    assert key_id == key_id_for("gemini", "super-secret-value")
    assert key_id.startswith("gemini-")
    assert "super-secret-value" not in key_id
    assert key_id != key_id_for("gemini", "other")
