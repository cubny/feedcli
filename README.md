# feedcli

A local Python library and CLI for RSS/Atom/JSON-Feed management.

## Overview

`feedcli` provides programmatic CRUD operations on feeds and items, backed by a local SQLite database. It is built to be a high-performance, deterministic component for content curation workflows.

### Key Features

- **Library-First Design**: The core logic resides in `feedcli.ops`, making it easy to embed into other Python applications.
- **Auto-Discovery**: Automatically finds feed URLs from website links.
- **Conditional Fetching**: Uses ETag and Last-Modified headers to minimize bandwidth.
- **CLI Interface**: A thin Click-based wrapper for manual management and scripting.
- **Local Storage**: XDG-compliant SQLite storage.

## Installation

```bash
pip install .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

### CLI Usage

```bash
# Add a feed
feedcli feeds add https://example.com/blog

# Fetch new items
feedcli feeds update --all

# List unread items
feedcli items list --unread

# Mark an item as read
feedcli items mark-read <item-id>
```

### Library Usage

```python
from feedcli.ops import get_unread_items, mark_read

# Get new content
items = get_unread_items(limit=10)

for item in items:
    print(f"{item.title}: {item.url}")
    # ... process item ...
    mark_read(item.id)
```

### Shell Autocompletion

`feedcli` supports shell autocompletion for bash, zsh, and fish.

To enable it, add the following to your shell's configuration file (e.g., `~/.bashrc`, `~/.zshrc`):

**Bash:**
```bash
eval "$(feedcli completion bash)"
```

**Zsh:**
```zsh
eval "$(feedcli completion zsh)"
```

**Fish:**
```fish
feedcli completion fish | source
```

## Documentation

- [AI Agent Skill Documentation](skill/SKILL.md)

## License

MIT
