"""Session context manager — replaces _get_session + try/finally/rollback boilerplate."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session

from feedcli.db import get_session


@contextmanager
def managed_session(session: Session | None = None, *, commit: bool = False):
    """Yield a session; close it only if we created it.

    Args:
        session: An existing session to reuse, or None to create a new one.
        commit: If True, commit the session on successful exit.
    """
    if session is not None:
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        return
    sess = get_session()
    try:
        yield sess
        if commit:
            sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
