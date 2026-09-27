"""Minimal conversation (ask/listen) helper for pyrofork.

Several plugins call ``client.ask(...)`` / ``bot.ask(...)`` / ``client.listen(...)``,
but the pyromod package that provides those methods was never installed, so every
one of those calls raised ``AttributeError`` at runtime. Installing the real
pyromod is not safe here: it declares a hard dependency on the ``pyrogram``
distribution, which pip would install *over* pyrofork (both ship the top-level
``pyrogram`` package), breaking the bot.

This module provides a small dependency-free equivalent with the same call
signatures, patched onto :class:`pyrogram.Client` by :func:`install`:

* ``await client.ask(chat_id, text=None, timeout=None, **kwargs)`` — optionally
  sends ``text`` to ``chat_id``, then waits for the next message in that chat.
* ``await client.listen(user_id, timeout=None)`` — waits for the next message
  from ``user_id`` (in any chat).

A dispatcher-level router (registered by the caller, see ``bot.py``) delivers a
matching message to the oldest pending waiter and stops further propagation,
which mirrors pyromod closely enough for the admin-only flows that use it.
"""

import asyncio
from collections import defaultdict

from pyrogram import Client

# key -> list of futures waiting, oldest first.
# Keys are ("chat", chat_id) for ask() and ("user", user_id) for listen().
_pending = defaultdict(list)


def match_listener(message):
    """Return the pending-listener key this message satisfies, if any."""
    chat = getattr(message, "chat", None)
    if chat is not None:
        key = ("chat", chat.id)
        if _pending.get(key):
            return key
    user = getattr(message, "from_user", None)
    if user is not None:
        key = ("user", user.id)
        if _pending.get(key):
            return key
    return None


async def deliver(message):
    """Hand ``message`` to the oldest matching waiter. Returns True if claimed."""
    key = match_listener(message)
    if key is None:
        return False
    waiters = _pending.get(key)
    if not waiters:
        return False
    fut = waiters.pop(0)
    if not fut.done():
        fut.set_result(message)
    return True


async def _wait(key, timeout):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _pending[key].append(fut)
    try:
        if timeout:
            return await asyncio.wait_for(fut, timeout)
        return await fut
    finally:
        try:
            _pending[key].remove(fut)
        except ValueError:
            pass


async def _ask(self, chat_id, text=None, timeout=None, **kwargs):
    if text is not None:
        await self.send_message(chat_id, text, **kwargs)
    return await _wait(("chat", chat_id), timeout)


async def _listen(self, user_id, timeout=None):
    return await _wait(("user", user_id), timeout)


def install():
    """Patch :class:`pyrogram.Client` with ``ask``/``listen``.

    Returns the ``deliver`` coroutine for the dispatcher router.
    """
    Client.ask = _ask
    Client.listen = _listen
    return deliver
