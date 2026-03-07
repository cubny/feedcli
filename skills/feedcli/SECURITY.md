# Security Policy — feedcli Skill

## Access Declarations

### Network

- **Outbound HTTP(S) only**, limited to fetching RSS/Atom/JSON feed URLs
  provided by the user or stored in the subscription database.
- **No telemetry, analytics, or phone-home behavior.**
- No inbound listeners, sockets, or servers are opened.

### Filesystem

| Path | Access | Purpose |
|---|---|---|
| `$XDG_DATA_HOME/feedcli/feedcli.db` | Read/Write | SQLite database for feed subscriptions and items |
| User-specified OPML path | Read or Write | OPML import/export only when explicitly invoked |

No other filesystem paths are accessed. The database location defaults to
`~/.local/share/feedcli/feedcli.db` and respects XDG base directory conventions.

### Credentials & Secrets

- **None required.** This skill does not use API keys, tokens, passwords,
  or any form of authentication.
- No credentials are stored, transmitted, or read from the environment.

### Privileges

- **No elevated privileges.** Runs as the current user with no `sudo`,
  no `setuid`, no capability requests.
- **No background processes.** No daemons, cron jobs, or persistent
  background tasks are created.
- **No shell injection.** All tool functions accept typed parameters;
  no user input is passed to shell commands. The library never calls
  `subprocess`, `os.system`, or any shell execution API.

## Dependency Chain

All runtime behavior is implemented in the open-source
[feedcli](https://github.com/cubny/feedcli) Python package. Dependencies:

| Package | Purpose |
|---|---|
| `feedparser` | Parse RSS/Atom/JSON feeds |
| `httpx` | HTTP client for fetching feeds |
| `sqlalchemy` | ORM for local SQLite database |
| `beautifulsoup4` | HTML parsing for feed discovery |
| `python-dateutil` | Date parsing utilities |
| `click` | CLI interface (not used by skill tools) |

All dependencies are well-known, widely-used Python packages available on PyPI.

## Source Code

The complete source code is available at:
**https://github.com/cubny/feedcli**

All runtime behavior called by `tools.py` is implemented in `feedcli/ops/`
and can be fully inspected at the repository above.

## Reporting Vulnerabilities

Please report security issues via GitHub Issues at
https://github.com/cubny/feedcli/issues with the label `security`.
