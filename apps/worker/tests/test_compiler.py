from core.embeddings import HashEmbedder
from worker.compiler import build_search_terms, fingerprint_text

VOICE = {
    "name": "Voice agents",
    "custom": False,
    "description": "AI phone agents",
    "problems": ["Calls are missed after hours"],
    "phrases": ["we miss calls after hours", "need someone to answer phones"],
    "technologies": ["Twilio", "Vapi"],
}
WEB = {
    "name": "Web development",
    "custom": False,
    "description": "Websites",
    "problems": ["The website looks outdated"],
    "phrases": ["our website looks old", "need a website redesign"],
    "technologies": ["Next.js", "WordPress"],
}


def test_different_profiles_give_different_terms() -> None:
    a = build_search_terms({"exclusions": ["crypto"], "min_budget_usd": 500}, [VOICE])
    b = build_search_terms({"exclusions": [], "min_budget_usd": 2000}, [WEB])
    assert "we miss calls after hours" in a["sources"]["reddit"]["queries"]
    assert "our website looks old" in b["sources"]["reddit"]["queries"]
    assert set(a["sources"]["reddit"]["queries"]).isdisjoint(b["sources"]["reddit"]["queries"])
    assert all(q.endswith(" -crypto") for q in a["sources"]["web_search"]["queries"])
    assert "voice agents freelancer" in a["sources"]["job_boards"]["queries"]
    assert a["min_budget_usd"] == 500 and b["min_budget_usd"] == 2000


def test_terms_are_deduplicated_and_bounded() -> None:
    many = {**VOICE, "phrases": [f"phrase {i}" for i in range(500)] + ["phrase 1"]}
    out = build_search_terms({}, [many])
    queries = out["sources"]["reddit"]["queries"]
    assert len(queries) == len(set(queries)) <= 60


def test_fingerprint_text_mentions_service_problems_and_tools() -> None:
    text = fingerprint_text(VOICE)
    assert "Voice agents" in text and "missed after hours" in text and "Twilio" in text


def test_hash_embedder_is_deterministic_and_normalised() -> None:
    e = HashEmbedder()
    v1, v2 = e.embed(["missed calls", "missed calls"])
    assert v1 == v2 and len(v1) == 384
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-9
