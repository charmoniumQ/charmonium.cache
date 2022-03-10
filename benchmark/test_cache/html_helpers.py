from pathlib import Path
from typing import Sequence, Optional, Union, Mapping
import itertools

from . import html


def html_table(
    elems: Sequence[Sequence[html.TagLike]],
    headers: Optional[Sequence[html.TagLike]] = None
) -> html.Tag:
    if headers is not None:
        thead = [html.thead()(html.tr()(*[html.td()(header) for header in headers]))]
    else:
        thead = []
    return html.table()(
        *thead,
        html.tbody()(*[html.tr()(*[html.td()(elem) for elem in row]) for row in elems]),
    )

def html_list(elements: Sequence[html.TagLike], ordered: bool = False) -> html.Tag:
    list_factory = html.ol() if ordered else html.ul()
    return list_factory(*[
        html.li()(element)
        for element in elements
    ])

def html_path(path: Path) -> html.Tag:
    return html.a(href=f"file://{path.resolve()}")(html.code()(str(path)))

def highlighted_head(languages: Sequence[str]) -> Sequence[html.Tag]:
    # for supported langs https://cdnjs.com/libraries/highlight.js
    return [
        html.link(
            rel="stylesheet",
            href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.3.1/styles/default.min.css",
        )(),
        html.script(
            src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.3.1/highlight.min.js",
        )(""),
        *[
            html.script(
                src=f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.3.1/build/languages/{lang}.min.js",
            )("")
            for lang in languages
        ],
        html.script()("hljs.highlightAll();")
    ]

def css_string(**declarations: str) -> str:
    return ";".join([
        f"{property.replace('_', '-')}: {value}"
        for property, value in declarations.items()
    ])

def highlighted_code(lang: str, code: str, width: int = 60) -> html.Tag:
    # see https://highlightjs.org/usage/
    return html.pre()(html.code(**{
        "class": f"language-{lang}",
        "style": css_string(
            max_width=f"{width}ch",
            max_height="20vw",
            resize="both",
        ),
    })(code))

def collapsed(summary: html.TagLike, *details: html.TagLike) -> html.Tag:
    return html.details()(
        html.summary()(summary),
        *details,
    )


def disp_bool(val: bool) -> html.Tag:
    return html.span()(
        {
            False: "❌",
            True: "✅",
        }[val]
    )

def br_join(lines: Sequence[html.TagLike]) -> html.Tag:
    return html.span()(*itertools.chain.from_iterable(
        (html.span()(line) if isinstance(line, str) else line, html.br()())
        for line in lines
    ))

def small(text: str) -> html.Tag:
    return html.span(style=css_string(font_size="8pt"))(text)
