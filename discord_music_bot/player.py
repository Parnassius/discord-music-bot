from __future__ import annotations

from collections import deque
from typing import Any

from discord import Client, Message, NotFound, TextChannel, Thread, VoiceChannel
from discord.abc import Connectable
from wavelink import Playable, Player  # type: ignore[import]


class MyPlayer(Player):  # type: ignore[misc]
    def __init__(self, client: Client, channel: Connectable) -> None:
        super().__init__(client, channel)

        self.play_queue: deque[Playable] = deque()
        self.loop: bool | Playable = False
        self.text_channel: TextChannel | VoiceChannel | Thread | None = None
        self.now_playing_message: Message | None = None

    async def stop(self, *, force: bool = True) -> None:
        if isinstance(self.loop, Playable):
            try:
                self.loop = self.play_queue.popleft()
            except IndexError:
                self.loop = False
        await super().stop(force=force)

    async def disconnect(self, **kwargs: Any) -> None:
        await self.delete_now_playing_message()
        await super().disconnect(**kwargs)

    async def delete_now_playing_message(self) -> None:
        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except NotFound:
                pass
