from typing import List, Optional, Union, Mapping

from . import html


def html_table(
    elems: List[List[html.TagLike]],
    headers: Optional[List[html.TagLike]] = None
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

def css_string(declarations: Mapping[str, str]) -> str:
    return ";".join([
        f"{property}: {value}"
        for property, value in declarations.items()
    ])

def highlighted_code(lang: str, code: str, width: int = 60) -> html.Tag:
    # see https://highlightjs.org/usage/
    return html.pre()(html.code(**{
        "class": f"language-{lang}",
        "style": css_string({
            "width": f"{width}ch",
            "height": "20vw",
            "resize": "both",
        }),
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
