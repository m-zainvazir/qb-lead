from core.text import html_to_text
from worker.ingest.hackernews import to_item
from worker.ingest.planner import merge_queries
from worker.ingest.web_search import exa_items, serper_items, tavily_items


def test_planner_puts_shared_queries_first_and_dedupes() -> None:
    a = ["missed calls", "website redesign", "Missed  Calls"]
    b = ["missed calls", "invoice automation"]
    c = ["website redesign", "missed calls"]
    assert merge_queries([a, b, c], budget=10) == [
        "missed calls",
        "website redesign",
        "invoice automation",
    ]
    assert merge_queries([a, b, c], budget=1) == ["missed calls"]


def test_html_is_reduced_to_text() -> None:
    raw = "<p>Hi<br>there</p><script>alert(1)</script><img src=x onerror=alert(2)>&amp; bye"
    assert html_to_text(raw) == "Hi\nthere\n& bye"


def test_hn_comment_hit_becomes_raw_item() -> None:
    hit = {
        "objectID": "123",
        "author": "pg",
        "comment_text": "<p>Acme | Remote | Contract<p>Need a voice agent developer",
        "story_title": "Ask HN: Freelancer? Seeking freelancer? (November 2026)",
        "created_at_i": 1794600000,
        "_tags": ["comment", "story_1"],
        "parent_id": 1,
        "story_id": 1,
    }
    item = to_item(hit, "hiring_thread", thread="Ask HN: Freelancer? Seeking freelancer?")
    assert item.external_id == "123"
    assert item.title == "Acme | Remote | Contract"
    assert item.url == "https://news.ycombinator.com/item?id=123"
    assert item.author_url == "https://news.ycombinator.com/user?id=pg"
    assert "<p>" not in (item.body or "")


def test_web_search_parsers() -> None:
    exa = exa_items(
        {
            "results": [
                {
                    "url": "https://a.example/x",
                    "title": "T",
                    "text": "<b>b</b>",
                    "publishedDate": "2026-11-10T00:00:00Z",
                }
            ]
        },
        "q",
    )
    assert exa[0].body == "b" and exa[0].posted_at is not None
    tav = tavily_items(
        {"results": [{"url": "https://b.example", "title": "T", "content": "c"}]}, "q"
    )
    assert tav[0].url == "https://b.example"
    ser = serper_items(
        {"organic": [{"link": "https://c.example", "title": "T", "snippet": "s"}]}, "q"
    )
    assert (
        ser[0].external_id
        == exa_items({"results": [{"url": "https://c.example"}]}, "q")[0].external_id
    )
