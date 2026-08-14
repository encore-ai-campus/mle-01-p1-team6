"""Small HTML tree/parser shared by the Aladin crawlers."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


class HTMLNode:
    def __init__(self, tag: str = "root", attrs: dict[str, str] | None = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[HTMLNode | str] = []

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    def text(self) -> str:
        chunks: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                chunks.append(child)
            elif child.tag == "br":
                chunks.append("\n")
            else:
                chunks.append(child.text())
        return "".join(chunks)

    def find_all(self, predicate: Any) -> list[HTMLNode]:
        found: list[HTMLNode] = []
        for child in self.children:
            if isinstance(child, HTMLNode):
                if predicate(child):
                    found.append(child)
                found.extend(child.find_all(predicate))
        return found


class HTMLTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HTMLNode()
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HTMLNode(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def has_class(node: HTMLNode, class_name: str) -> bool:
    return class_name in node.get("class").split()


def first(node: HTMLNode, predicate: Any) -> HTMLNode | None:
    matches = node.find_all(predicate)
    return matches[0] if matches else None


def clean_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def parse_int(pattern: str, value: str, default: int = 0) -> int:
    match = re.search(pattern, value)
    return int(match.group(1)) if match else default
