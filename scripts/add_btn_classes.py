import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'

TAG_PATTERNS = [
    (re.compile(r"(<button\b([^>]*))>", re.IGNORECASE), 'button'),
    (re.compile(r"(<a\b([^>]*))>", re.IGNORECASE), 'a'),
    (re.compile(r"(<input\b([^>]*type=[\"']?(?:submit|button|reset)[\"']?[^>]*))>", re.IGNORECASE), 'input'),
]

CLS_RE = re.compile(r'class\s*=\s*(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)


def ensure_btn_in_attrs(attrs_text: str) -> str:
    m = CLS_RE.search(attrs_text)
    if m:
        quote = m.group(1)
        classes = m.group(2)
        if 'btn' in classes.split():
            return attrs_text
        new_classes = classes + ' btn'
        return attrs_text[:m.start()] + f'class={quote}{new_classes}{quote}' + attrs_text[m.end():]
    else:
        # insert class before the end (keep leading/trailing spaces)
        return attrs_text + ' class="btn"'


def process_text(text: str) -> (str, bool):
    changed = False
    for pattern, tag in TAG_PATTERNS:
        def repl(match):
            nonlocal changed
            full = match.group(1)
            attrs = match.group(2)
            new_attrs = ensure_btn_in_attrs(attrs)
            if new_attrs != attrs:
                changed = True
            return new_attrs + '>'

        text = pattern.sub(repl, text)
    return text, changed


def backup_file(path: Path):
    bak = path.with_suffix(path.suffix + '.bak')
    if not bak.exists():
        bak.write_bytes(path.read_bytes())


def main():
    html_files = list(TEMPLATES.rglob('*.html'))
    print(f'Found {len(html_files)} template files')
    for p in html_files:
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            continue
        new_text, changed = process_text(text)
        if changed:
            backup_file(p)
            p.write_text(new_text, encoding='utf-8')
            print('Updated', p)


if __name__ == '__main__':
    main()
