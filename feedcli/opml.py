"""OPML import/export for feedcli."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def parse_opml(file_path: str) -> list[dict]:
    """Parse an OPML file and return a list of outline dicts.

    Each dict has keys: text, title, xml_url, html_url, category.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()
    body = root.find("body")
    if body is None:
        return []

    outlines = []
    _collect_outlines(body, outlines, category=None)
    return outlines


def _collect_outlines(
    element: ET.Element,
    outlines: list[dict],
    category: str | None,
) -> None:
    """Recursively collect outline elements."""
    for outline in element.findall("outline"):
        xml_url = outline.get("xmlUrl")
        if xml_url:
            # This is a feed outline
            outlines.append(
                {
                    "text": outline.get("text", ""),
                    "title": outline.get("title", ""),
                    "xml_url": xml_url,
                    "html_url": outline.get("htmlUrl", ""),
                    "category": category,
                }
            )
        else:
            # This is a category folder — recurse
            folder_name = outline.get("text") or outline.get("title")
            _collect_outlines(outline, outlines, category=folder_name)


def generate_opml(feeds: list, file_path: str) -> None:
    """Generate an OPML file from a list of Feed ORM objects."""
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "feedcli subscriptions"
    ET.SubElement(head, "dateCreated").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    body = ET.SubElement(opml, "body")

    # Group feeds by category into folders
    categorized: dict[str | None, list] = {}
    for feed in feeds:
        cat = getattr(feed, "category", None)
        cat_name = cat.name if cat and cat.name != "default" else None
        categorized.setdefault(cat_name, []).append(feed)

    for cat, cat_feeds in categorized.items():
        if cat:
            folder = ET.SubElement(body, "outline", text=cat, title=cat)
            parent = folder
        else:
            parent = body

        for feed in cat_feeds:
            attrs = {
                "type": "rss",
                "text": feed.title or feed.url,
                "title": feed.title or feed.url,
                "xmlUrl": feed.url,
            }
            if feed.website:
                attrs["htmlUrl"] = feed.website
            ET.SubElement(parent, "outline", **attrs)

    tree = ET.ElementTree(opml)
    ET.indent(tree, space="  ")
    tree.write(file_path, encoding="utf-8", xml_declaration=True)
