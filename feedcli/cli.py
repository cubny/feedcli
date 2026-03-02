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


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell):
    """Output the shell completion script."""
    from click.shell_completion import get_completion_class

    cls = get_completion_class(shell)
    if cls is None:
        click.echo(f"Shell {shell} not supported.", err=True)
        sys.exit(1)

    prog_name = "feedcli"
    complete_var = f"_{prog_name.upper()}_COMPLETE"
    comp = cls(main, {}, prog_name, complete_var)
    click.echo(comp.source())


@main.group()
def feeds():
    """Manage feed subscriptions."""


@feeds.command("list")
@click.option("--tag", default=None, help="Filter by tag")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def feeds_list(ctx, tag, fmt):
    """List all subscribed feeds."""
    from feedcli.ops import list_feeds

    result = list_feeds(tag=tag, session=ctx.obj["session"])
    data = [_format_feed(f) for f in result]
    _output(data, fmt)


@feeds.command("add")
@click.argument("url")
@click.option("--title", "-t", default=None, help="Override feed title")
@click.option(
    "--tag",
    multiple=True,
    help="Tag to assign (can be repeated: --tag tech --tag ai)",
)
@click.option("--no-discover", is_flag=True, help="Skip feed discovery, treat URL as direct feed")
@click.option("--auto", is_flag=True, help="Auto-select first discovered feed")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def feeds_add(ctx, url, title, tag, no_discover, auto, fmt):
    """Subscribe to a feed."""
    from feedcli.ops import add_feed

    tags = list(tag) if tag else None
    try:
        feed = add_feed(
            url=url,
            title=title,
            tags=tags,
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


@feeds.command("info")
@click.argument("feed_id", type=int)
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def feeds_info(ctx, feed_id, fmt):
    """Show details for a single feed."""
    from feedcli.ops import get_feed

    try:
        feed = get_feed(feed_id, session=ctx.obj["session"])
        _output(_format_feed(feed), fmt)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@feeds.command("discover")
@click.argument("url")
@click.option("--format", "fmt", type=click.Choice(["json", "urls"]), default="json")
@click.option("--timeout", type=int, default=30, help="HTTP timeout in seconds")
def feeds_discover(url, fmt, timeout):
    """Discover feed URLs from a website URL."""
    from feedcli.ops import discover_feeds

    results = discover_feeds(url, timeout=timeout)
    if fmt == "urls":
        for r in results:
            click.echo(r["url"])
    else:
        _output(results, "json")


@feeds.command("retry")
@click.argument("feed_id", type=int)
@click.pass_context
def feeds_retry(ctx, feed_id):
    """Reset error state and re-fetch a feed."""
    from feedcli.ops import reset_feed_errors

    try:
        count = reset_feed_errors(feed_id, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "feed_id": feed_id, "new_items": count}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.group()
def items():
    """Manage feed items."""


@items.command("list")
@click.option("--feed", "feed_id", type=int, default=None, help="Filter by feed ID")
@click.option("--unread", is_flag=True, help="Show only unread items")
@click.option("--starred", is_flag=True, help="Show only starred items")
@click.option("--limit", type=int, default=50, help="Max items to return")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def items_list(ctx, feed_id, unread, starred, limit, fmt):
    """List feed items."""
    from feedcli.ops import get_items

    # Route everything through get_items() so --unread and --starred can combine.
    result = get_items(
        feed_id=feed_id,
        unread_only=unread,
        starred_only=starred,
        limit=limit,
        session=ctx.obj["session"],
    )
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


@items.command("mark-unread")
@click.argument("item_id", type=int)
@click.pass_context
def items_mark_unread(ctx, item_id):
    """Mark an item as unread."""
    from feedcli.ops import mark_unread

    try:
        mark_unread(item_id, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "item_id": item_id}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@items.command("delete")
@click.argument("item_id", type=int)
@click.option("--hard", is_flag=True, help="Permanently remove from DB")
@click.pass_context
def items_delete(ctx, item_id, hard):
    """Delete an item (soft-delete by default)."""
    from feedcli.ops import delete_item

    try:
        delete_item(item_id, hard=hard, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "deleted", "item_id": item_id, "hard": hard}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@items.command("search")
@click.argument("query")
@click.option("--feed", "feed_id", type=int, default=None, help="Filter by feed ID")
@click.option("--limit", type=int, default=20, help="Max results")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def items_search(ctx, query, feed_id, limit, fmt):
    """Search items by keyword."""
    from feedcli.ops import search_items

    result = search_items(query, feed_id=feed_id, limit=limit, session=ctx.obj["session"])
    data = [_format_item(i) for i in result]
    _output(data, fmt)


@items.command("star")
@click.argument("item_id", type=int)
@click.pass_context
def items_star(ctx, item_id):
    """Star/bookmark an item."""
    from feedcli.ops import star_item

    try:
        star_item(item_id, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "item_id": item_id, "starred": True}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@items.command("unstar")
@click.argument("item_id", type=int)
@click.pass_context
def items_unstar(ctx, item_id):
    """Remove star from an item."""
    from feedcli.ops import unstar_item

    try:
        unstar_item(item_id, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "item_id": item_id, "starred": False}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@items.command("starred")
@click.option("--limit", type=int, default=50, help="Max items to return")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def items_starred(ctx, limit, fmt):
    """List all starred items."""
    from feedcli.ops import get_starred_items

    result = get_starred_items(limit=limit, session=ctx.obj["session"])
    data = [_format_item(i) for i in result]
    _output(data, fmt)


@items.command("get-url")
@click.argument("item_id", type=int)
@click.pass_context
def items_get_url(ctx, item_id):
    """Get the URL for an item."""
    from feedcli.ops import get_item_url

    try:
        url = get_item_url(item_id, session=ctx.obj["session"])
        click.echo(url)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# --- Tags CLI ---


@main.group()
def tags():
    """Manage feed tags."""


@tags.command("list")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def tags_list(ctx, fmt):
    """List all tags in use."""
    from feedcli.ops import list_tags

    result = list_tags(session=ctx.obj["session"])
    # table output needs list[dict]; json accepts list[str] as-is
    if fmt == "table":
        _output([{"tag": t} for t in result], fmt)
    else:
        _output(result, fmt)


@tags.command("add")
@click.argument("feed_id", type=int)
@click.argument("tag")
@click.pass_context
def tags_add(ctx, feed_id, tag):
    """Add a tag to a feed."""
    from feedcli.ops import add_tag

    try:
        add_tag(feed_id, tag, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "feed_id": feed_id, "tag": tag}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@tags.command("remove")
@click.argument("feed_id", type=int)
@click.argument("tag")
@click.pass_context
def tags_remove(ctx, feed_id, tag):
    """Remove a tag from a feed."""
    from feedcli.ops import remove_tag

    try:
        remove_tag(feed_id, tag, session=ctx.obj["session"])
        click.echo(json.dumps({"status": "ok", "feed_id": feed_id, "tag_removed": tag}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@tags.command("show")
@click.argument("tag")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def tags_show(ctx, tag, fmt):
    """Show all feeds with a given tag."""
    from feedcli.ops import get_feeds_by_tag

    result = get_feeds_by_tag(tag, session=ctx.obj["session"])
    data = [_format_feed(f) for f in result]
    _output(data, fmt)


# --- OPML CLI ---


@main.group()
def opml():
    """Import/export OPML files."""


@opml.command("import")
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def opml_import(ctx, file, fmt):
    """Import feeds from an OPML file."""
    from feedcli.ops import import_opml

    feeds = import_opml(file, session=ctx.obj["session"])
    data = [_format_feed(f) for f in feeds]
    _output(data, fmt)
    click.echo(f"Imported {len(feeds)} feeds.", err=True)


@opml.command("export")
@click.argument("file", type=click.Path())
@click.pass_context
def opml_export(ctx, file):
    """Export all feeds to an OPML file."""
    from feedcli.ops import export_opml

    export_opml(file, session=ctx.obj["session"])
    click.echo(json.dumps({"status": "ok", "file": file}))


# --- Config CLI ---


@main.group()
def config():
    """Manage configuration."""


@config.command("show")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def config_show(ctx, fmt):
    """Show current configuration."""
    from feedcli.ops import get_config

    data = get_config()
    _output(data, fmt)


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx, key, value):
    """Set a configuration value.

    Valid keys: database.path, fetch.timeout, fetch.jobs
    """
    from feedcli.ops import set_config

    _VALID_CONFIG_KEYS = {"database.path", "fetch.timeout", "fetch.jobs"}
    if key not in _VALID_CONFIG_KEYS:
        valid = ", ".join(sorted(_VALID_CONFIG_KEYS))
        click.echo(f"Error: unknown config key '{key}'. Valid keys: {valid}", err=True)
        sys.exit(1)
    set_config(key, value)
    click.echo(json.dumps({"status": "ok", "key": key, "value": value}))


# --- DB CLI ---


@main.group()
def db():
    """Database management commands."""


@db.command("info")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.pass_context
def db_info_cmd(ctx, fmt):
    """Show database statistics."""
    from feedcli.ops import db_info

    data = db_info(session=ctx.obj["session"])
    _output(data, fmt)


@db.command("vacuum")
@click.pass_context
def db_vacuum_cmd(ctx):
    """Compact the SQLite database."""
    from feedcli.ops import db_vacuum

    db_vacuum()
    click.echo(json.dumps({"status": "ok", "action": "vacuum"}))


@db.command("path")
def db_path_cmd():
    """Show the database file path."""
    from feedcli.config import load_config

    click.echo(load_config()["db_path"])


@db.command("backup")
@click.argument("dest_path", type=click.Path())
@click.pass_context
def db_backup_cmd(ctx, dest_path):
    """Backup the database to a file."""
    from feedcli.ops import db_backup

    try:
        db_backup(dest_path)
        click.echo(json.dumps({"status": "ok", "backup": dest_path}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@db.command("restore")
@click.argument("src_path", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def db_restore_cmd(ctx, src_path, force):
    """Restore the database from a backup file."""
    from feedcli.ops import db_restore

    if not force:
        click.confirm("Restore database from backup? This will overwrite current data.", abort=True)

    # Close the existing session and dispose the engine before overwriting the
    # SQLite file to avoid lock conflicts or stale connections after restore.
    session = ctx.obj.get("session")
    if session is not None:
        try:
            engine = session.get_bind()
        except Exception:
            engine = getattr(session, "bind", None)
        session.close()
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass

    try:
        db_restore(src_path)
        click.echo(json.dumps({"status": "ok", "restored_from": src_path}))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        # Recreate a fresh session bound to the restored DB.
        from feedcli.db import get_session as _get_session
        ctx.obj["session"] = _get_session()


# --- Daemon CLI ---


@main.group()
def daemon():
    """Background fetch daemon."""


@daemon.command("start")
@click.option("--interval", type=int, default=60, help="Minutes between fetches")
def daemon_start(interval):
    """Start the background fetch daemon (foreground process).

    This command runs in the foreground and blocks the terminal until stopped.
    To run in the background, use: feedcli daemon start &
    Or manage it with a process supervisor like launchd or systemd.
    """
    from feedcli.daemon import start

    try:
        start(interval=interval)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@daemon.command("stop")
def daemon_stop():
    """Stop the running daemon."""
    from feedcli.daemon import stop

    try:
        stop()
        click.echo(json.dumps({"status": "ok", "action": "stopped"}))
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@daemon.command("status")
def daemon_status():
    """Show daemon status."""
    from feedcli.daemon import status

    data = status()
    click.echo(json.dumps(data))


@daemon.command("logs")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
def daemon_logs(lines):
    """Show recent daemon log output."""
    from feedcli.daemon import logs

    click.echo(logs(lines=lines))
