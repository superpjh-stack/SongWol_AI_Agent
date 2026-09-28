from __future__ import annotations

from typing import Any


def extract_sources(response: Any) -> list[str]:
    result: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                filename = getattr(annotation, "filename", None)
                if filename and filename not in result:
                    result.append(filename)
    return result


def extract_evidence(response: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "file_search_call":
            continue
        for hit in getattr(item, "results", []) or []:
            result.append({
                "filename": getattr(hit, "filename", None) or "문서",
                "text": getattr(hit, "text", None),
                "score": getattr(hit, "score", None),
            })
    return result
