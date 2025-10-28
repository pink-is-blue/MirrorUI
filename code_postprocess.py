
import re
from typing import Dict

_SPLIT = re.compile(r"\[FILE:\s*([^\]]+)\]", re.I)

def split_files(text: str) -> Dict[str,str]:
    parts = _SPLIT.split(text)
    if len(parts) < 3:
        return {"src/components/generated/AppBody.jsx": text.strip()}
    out = {}
    for i in range(1, len(parts), 2):
        path = parts[i].strip()
        code = parts[i+1] if i+1 < len(parts) else ""
        code = code.strip().lstrip("```").rstrip("```").strip()
        if path.startswith("src/"):
            out[path] = code
        else:
            out["src/" + path] = code
    return out
