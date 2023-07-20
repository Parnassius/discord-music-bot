from __future__ import annotations

import io
from pathlib import Path
from sys import exc_info
from traceback import format_exception
from typing import Any

from discord import File, Object
from discord.ext import commands
from wavelink import Node, NodePool  # type: ignore[import]


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
        print(f"Logged on as {self.user}!")

        host, port, password = self.lavalink_connection
        node = Node(uri=f"http://{host}:{port}", password=password)
        await NodePool.connect(client=self, nodes=[node])

    async def on_wavelink_node_ready(self, node: Node) -> None:
        print(f"Node {node.id} is ready!")

        for player in list(node.players.values()):
            await player.disconnect()

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        if not self.owner_id:
            return
        target = await self.fetch_user(self.owner_id)
        tb = format_exception(*exc_info())
        file = File(io.BytesIO("".join(tb).encode()), filename="traceback.txt")
        await target.send(f"Handler `{event_method}` raised an exception", file=file)
