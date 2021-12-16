from html import escape as escape
from typing import List, Optional

from . import html


def html_table(
    elems: List[List[html.TagLike]], headers: Optional[List[html.TagLike]] = None
) -> html.Tag:
    if headers is not None:
        thead = [html.thead()(html.tr()(*[html.td()(header) for header in headers]))]
    else:
        thead = []
    return html.table()(
        *thead,
        html.tbody()(*[html.tr()(*[html.td()(elem) for elem in row]) for row in elems]),
    )


def highlighted_head(languages: List[str]) -> List[html.Tag]:
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


def highlighted_code(lang: str, code: str) -> html.Tag:
    # see https://highlightjs.org/usage/
    return html.pre()(html.code(**{"class": f"language-{lang}"})(escape(code)))


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
