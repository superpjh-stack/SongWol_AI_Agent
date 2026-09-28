"""Local, explicitly unapproved demo documents; no upload or paid indexing required."""
from pathlib import Path
import re

DOCS = Path(__file__).resolve().parents[1] / 'sample_docs'

def documents(query: str = '') -> list[dict]:
    terms = re.findall(r'[가-힣A-Za-z0-9]+', query.lower())
    result = []
    for path in sorted(DOCS.glob('*.md')):
        body = path.read_text(encoding='utf-8')
        if terms and not any(term in body.lower() for term in terms):
            continue
        revision = re.search(r'문서번호:\s*(\S+)', body)
        result.append({'id': path.stem, 'title': body.splitlines()[0].lstrip('# '),
                       'revision': revision.group(1) if revision else '미확인',
                       'approval': '미승인 · 검증용 샘플', 'body': body, 'demo_data': True})
    return result
