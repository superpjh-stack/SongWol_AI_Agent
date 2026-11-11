"""Accept nonempty questions without a wake phrase."""

def calls_songwol(text: str) -> bool:
    return bool(text.strip())
