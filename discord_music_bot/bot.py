from __future__ import annotations

import asyncio
import io
from pathlib import Path
from sys import exc_info
from traceback import format_exception
from typing import Any

import aiohttp
from discord import File, Object
from discord.backoff import ExponentialBackoff
from discord.ext import commands
from mafic import Node, NodePool


class MyBot(commands.Bot):
    def __init__(
        self,
        *args: Any,
        lavalink_connection: tuple[str, int, str],
        test_guild_id: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.lavalink_connection = lavalink_connection
        self.pool = NodePool(self)
        self.test_guild_id = test_guild_id

    async def setup_hook(self) -> None:
        modules = Path(__file__).parent / "plugins"
        for f in modules.glob("*.py"):
            if f.is_file() and f.name != "__init__.py":
                await self.load_extension(f"discord_music_bot.plugins.{f.stem}")

        if self.test_guild_id:
            test_guild = Object(id=self.test_guild_id)
            self.tree.copy_global_to(guild=test_guild)
            await self.tree.sync(guild=test_guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        await self.add_node()
        print(f"Logged on as {self.user}!")

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        if not self.owner_id:
            return
        target = await self.fetch_user(self.owner_id)
        tb = format_exception(*exc_info())
        file = File(io.BytesIO("".join(tb).encode()), filename="traceback.txt")
        await target.send(f"Handler `{event_method}` raised an exception", file=file)

    async def add_node(self) -> None:
        node: Node[MyBot] | None = None
        backoff = ExponentialBackoff()
        host, port, password = self.lavalink_connection
        while not node:
            try:
                node = await self.pool.create_node(
                    host=host,
                    port=port,
                    label="MAIN",
                    password=password,
                )
            except aiohttp.client_exceptions.ClientConnectorError:
                await asyncio.sleep(backoff.delay())
