"""Transparent duration estimate from actual script/card-plan text and response pauses."""


def estimate_timing(segments, grade, main_path=None):
    if main_path is not None:
        segments = [s for s in segments if s["id"] in main_path]
    words = sum(
        len(s.get("content", "").split())
        if "content" in s
        else sum(len(u["spoken"].split()) for u in s["utterances"])
        for s in segments
    )
    questions = sum(s.get("kind", s.get("type")) == "question" for s in segments)
    reflections = sum(
        (s.get("checkpoint") or s.get("phase") == "your_turn")
        and s.get("kind", s.get("type")) != "question"
        for s in segments
    )
    pace = 90 if grade <= 2 else 105
    spoken = round(words / pace * 60)
    response = questions * 150 + reflections * 45
    return {
        "minutes": max(15, min(35, round((spoken + response + 180) / 60))),
        "spoken_words": words,
        "speech_seconds": spoken,
        "response_seconds": response,
        "buffer_seconds": 180,
        "words_per_minute": pace,
        "estimated": True,
    }
