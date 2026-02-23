"""Click CLI — thin wrapper around ops.py."""

from __future__ import annotations

import json
import sys

import click

from feedcli.db import get_session


def _format_feed(feed) -> dict:
    return {
        "id": feed.id,
        "url": feed.url,
        "title": feed.title,
        "website": feed.website,
        "last_fetched_at": feed.last_fetched_at.isoformat() if feed.last_fetched_at else None,
        "error_count": feed.error_count,
        "disabled": feed.disabled,
        "created_at": feed.created_at.isoformat() if feed.created_at else None,
    }


def _format_item(item) -> dict:
    return {
        "id": item.id,
        "feed_id": item.feed_id,
        "title": item.title,
        "url": item.url,
        "author": item.author,
        "summary": item.summary[:200] if item.summary else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "is_read": item.is_read,
        "is_starred": item.is_starred,
    }


def _format_item_detail(item) -> dict:
    return {
        "id": item.id,
        "feed_id": item.feed_id,
        "guid": item.guid,
        "title": item.title,
        "url": item.url,
        "author": item.author,
        "summary": item.summary,
        "content": item.content,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "fetched_at": item.fetched_at.isoformat() if item.fetched_at else None,
        "is_read": item.is_read,
        "is_starred": item.is_starred,
    }


def _output(data, fmt: str):
    if fmt == "json":
        click.echo(json.dumps(data, indent=2))
    elif fmt == "table":
        if isinstance(data, list):
            if not data:
                click.echo("No results.")
                return
            keys = data[0].keys()
            header = "\t".join(str(k) for k in keys)
            click.echo(header)
            for row in data:
                click.echo("\t".join(str(row.get(k, "")) for k in keys))
        elif isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"{k}: {v}")


@click.group()
@click.pass_context
def main(ctx):
    """feedcli — RSS/Atom/JSON-Feed management."""
    ctx.ensure_object(dict)
    ctx.obj["session"] = get_session()


@main.group()
def feeds():
    """Manage feed subscriptions."""


@feeds.command("list")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def feeds_list(ctx, fmt):
    """List all subscribed feeds."""
    from feedcli.ops import list_feeds

    result = list_feeds(session=ctx.obj["session"])
    data = [_format_feed(f) for f in result]
    _output(data, fmt)


@feeds.command("add")
@click.argument("url")
@click.option("--title", "-t", default=None, help="Override feed title")
@click.option("--no-discover", is_flag=True, help="Skip feed discovery, treat URL as direct feed")
@click.option("--auto", is_flag=True, help="Auto-select first discovered feed")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def feeds_add(ctx, url, title, no_discover, auto, fmt):
    """Subscribe to a feed."""
    from feedcli.ops import add_feed

    try:
        feed = add_feed(
            url=url,
            title=title,
            auto_discover=not no_discover,
            session=ctx.obj["session"],
        )
        _output(_format_feed(feed), fmt)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@feeds.command("delete")
@click.argument("feed_id", type=int)
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def feeds_delete(ctx, feed_id, force):
    """Delete a feed and all its items."""
    from feedcli.ops import delete_feed

    if not force:
        click.confirm(f"Delete feed {feed_id} and all its items?", abort=True)
    try:
        delete_feed(feed_id, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "deleted", "feed_id": feed_id}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@feeds.command("update")
@click.argument("feed_id", type=int, required=False)
@click.option("--all", "update_all", is_flag=True, help="Update all feeds")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def feeds_update(ctx, feed_id, update_all, fmt):
    """Fetch new items for feeds."""
    from feedcli.ops import update_all_feeds, update_feed

    if update_all:
        results = update_all_feeds(session=ctx.obj["session"])
        total = sum(results.values())
        _output({"feeds_updated": len(results), "new_items": total, "details": results}, fmt)
    elif feed_id is not None:
        count = update_feed(feed_id, session=ctx.obj["session"])
        _output({"feed_id": feed_id, "new_items": count}, fmt)
    else:
        click.echo("Error: provide a feed ID or use --all", err=True)
        sys.exit(1)


@main.group()
def items():
    """Manage feed items."""


@items.command("list")
@click.option("--feed", "feed_id", type=int, default=None, help="Filter by feed ID")
@click.option("--unread", is_flag=True, help="Show only unread items")
@click.option("--limit", type=int, default=50, help="Max items to return")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def items_list(ctx, feed_id, unread, limit, fmt):
    """List feed items."""
    from feedcli.ops import get_items, get_unread_items

    if unread:
        result = get_unread_items(feed_id=feed_id, limit=limit, session=ctx.obj["session"])
    else:
        result = get_items(feed_id=feed_id, limit=limit, session=ctx.obj["session"])
    data = [_format_item(i) for i in result]
    _output(data, fmt)


@items.command("show")
@click.argument("item_id", type=int)
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def items_show(ctx, item_id, fmt):
    """Show a single item."""
    from feedcli.ops import get_item

    try:
        item = get_item(item_id, session=ctx.obj["session"])
        _output(_format_item_detail(item), fmt)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@items.command("mark-read")
@click.argument("item_id", type=int, required=False)
@click.option("--feed", "feed_id", type=int, default=None, help="Mark all items in feed as read")
@click.option("--all", "mark_all", is_flag=True, help="Mark all items as read")
@click.pass_context
def items_mark_read(ctx, item_id, feed_id, mark_all):
    """Mark items as read."""
    from feedcli.ops import mark_all_read, mark_read

    if mark_all:
        count = mark_all_read(session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "marked_read": count}))
    elif feed_id is not None:
        count = mark_all_read(feed_id=feed_id, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "feed_id": feed_id, "marked_read": count}))
    elif item_id is not None:
        try:
            mark_read(item_id, session=ctx.obj["session"])
            click.echo(json.dumps({"status": "ok", "item_id": item_id}))
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("Error: provide an item ID, --feed, or --all", err=True)
        sys.exit(1)
