"""An explicit "송월아" address is required for each new question."""
import re

_CALL = re.compile(r'^[\s\"\'“‘]*송월아(?=$|[\s,，.!?。！？:：~～])')

def calls_songwol(text: str) -> bool:
    return bool(_CALL.search(text.strip()))
