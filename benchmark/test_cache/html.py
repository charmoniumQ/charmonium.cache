from __future__ import annotations

import functools
import xml.etree.ElementTree as xml
from typing import Dict, Union


class Tag:
    def __init__(
        self, name: str, attrib: Dict[str, str], *children: Union[str, Tag]
    ) -> None:
        self.name = name
        self.attrib = attrib
        self.children = children

    def to_xml(self) -> xml.Element:
        elem = xml.Element(self.name, self.attrib)
        elem.text = ""
        first = True
        last_elem = None
        for child in self.children:
            if isinstance(child, str):
                if first:
                    elem.text += child
                else:
                    assert last_elem is not None
                    last_elem.tail += child
            elif isinstance(child, Tag):
                child_elem = child.to_xml()
                child_elem.tail = ""
                elem.append(child_elem)
                last_elem = child_elem
                first = False
        return elem

    def __str__(self) -> str:
        return xml.tostring(self.to_xml(), method="html", encoding="unicode")

    def __repr__(self) -> str:
        return f"Tag({self.name}, {self.attrib!r}, {self.children!r})"


TagLike = Union[Tag, str]


class TagBuilder:
    def __init__(self, name: str, **attrib: str) -> None:
        self.name = name
        self.attrib = attrib

    def __call__(self, *elems: TagLike) -> Tag:
        return Tag(self.name, self.attrib, *elems)


div = functools.partial(TagBuilder, "div")
p = functools.partial(TagBuilder, "p")
span = functools.partial(TagBuilder, "span")
html = functools.partial(TagBuilder, "html")
body = functools.partial(TagBuilder, "body")
head = functools.partial(TagBuilder, "head")
meta = functools.partial(TagBuilder, "meta")
title = functools.partial(TagBuilder, "title")
link = functools.partial(TagBuilder, "link")
script = functools.partial(TagBuilder, "script")
table = functools.partial(TagBuilder, "table")
thead = functools.partial(TagBuilder, "thead")
tbody = functools.partial(TagBuilder, "tbody")
tr = functools.partial(TagBuilder, "tr")
td = functools.partial(TagBuilder, "td")
pre = functools.partial(TagBuilder, "pre")
code = functools.partial(TagBuilder, "code")
details = functools.partial(TagBuilder, "details")
summary = functools.partial(TagBuilder, "summary")
h1 = functools.partial(TagBuilder, "h1")
h2 = functools.partial(TagBuilder, "h2")
h3 = functools.partial(TagBuilder, "h3")
style = functools.partial(TagBuilder, "style")

assert (
    str(
        div()(
            p(attr="b")(
                "hello",
                span()(),
                "world",
            ),
        )
    )
    == '<div><p attr="b">hello<span></span>world</p></div>'
)
