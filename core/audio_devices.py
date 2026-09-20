"""Small, platform-neutral helpers for audio-output detection."""

from __future__ import annotations


HEADPHONES = "headphones"
SPEAKERS = "speakers"
OTHER = "audio-output"

_HEADPHONE_TERMS = (
    "headphone",
    "headset",
    "earphone",
    "earbud",
    "airpod",
    "galaxy buds",
    "pixel buds",
)

_SPEAKER_TERMS = (
    "speaker",
    "loudspeaker",
    "line out",
    "line-out",
    "display audio",
    "hdmi",
)


def classify_audio_output(description: str | None) -> str:
    """Classify a system audio-output name without platform-specific APIs."""
    normalized = " ".join((description or "").casefold().split())
    if any(term in normalized for term in _HEADPHONE_TERMS):
        return HEADPHONES
    if any(term in normalized for term in _SPEAKER_TERMS):
        return SPEAKERS
    return OTHER


def headphones_were_disconnected(previous: str | None, current: str) -> bool:
    """Return true only for a transition away from a headphone output."""
    return previous == HEADPHONES and current != HEADPHONES


def output_kind_label(kind: str) -> str:
    return {
        HEADPHONES: "Headphones",
        SPEAKERS: "Speakers",
    }.get(kind, "Audio output")
