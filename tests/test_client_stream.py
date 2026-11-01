from chatjimmy_harness.client import Stats, _iter_chat_chunks


def test_iter_chat_chunks_splits_stats_trailer():
    body = b"Hello world<|stats|>{\"decode_tokens\": 2, \"decode_rate\": 1000.5, \"done_reason\": \"stop\"}<|/stats|>"
    chunks = list(_iter_chat_chunks(iter([body[:5], body[5:20], body[20:]])))
    text = "".join(t for t, s in chunks if t)
    stats_list = [s for t, s in chunks if s is not None]
    assert text == "Hello world"
    assert len(stats_list) == 1
    assert isinstance(stats_list[0], Stats)
    assert stats_list[0].decode_tokens == 2
    assert stats_list[0].decode_rate == 1000.5
    assert stats_list[0].done_reason == "stop"


def test_iter_chat_chunks_without_stats():
    chunks = list(_iter_chat_chunks(iter([b"just ", b"text"])))
    text = "".join(t for t, s in chunks if t)
    assert text == "just text"
    assert all(s is None for _, s in chunks)


def test_stats_open_tag_split_across_chunks_does_not_leak():
    # Holdback must not emit a partial "<|stats|>" into visible text.
    parts = [b"abc<", b"|stats|>{\"decode_tokens\":1}<|/stats|>"]
    chunks = list(_iter_chat_chunks(iter(parts)))
    text = "".join(t for t, s in chunks if t)
    assert text == "abc"
    assert "<|" not in text
    assert any(s and s.decode_tokens == 1 for _, s in chunks)
