"""Turn a saved source page (HTML or JSON) into plain text, so every lead can be checked against it.

    python3 -I pipeline/to_text.py data/sources/<event>/<page>.html data/sources/<event>/<page>.txt

PDFs go through `pdftotext -layout` instead.
"""

import html
import json
import re
import sys
from html.parser import HTMLParser

SKIP = {"script", "style", "noscript", "svg"}
BLOCK = {"p", "div", "li", "br", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "a"}


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skipping = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skipping += 1
        elif tag in BLOCK:
            self.parts.append("\n")
        # Logo walls often carry the company name only in alt/title attributes or link slugs.
        for key, value in attrs:
            if value and key in ("alt", "title", "aria-label"):
                self.parts.append(f" {value} ")
            if value and key == "href" and "/profile" in value:
                self.parts.append(f" [{value}] ")

    def handle_endtag(self, tag):
        if tag in SKIP and self.skipping:
            self.skipping -= 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from json_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from json_strings(v)


def to_text(raw: str, path: str) -> str:
    if path.endswith(".json"):
        text = "\n".join(json_strings(json.loads(raw)))
    else:
        parser = TextParser()
        parser.feed(raw)
        text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip() + "\n"


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(to_text(raw, src))
