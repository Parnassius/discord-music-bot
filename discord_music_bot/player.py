from __future__ import annotations

from collections import deque

from discord import Client, Message, NotFound, TextChannel, Thread, VoiceChannel
from discord.abc import Connectable
from mafic import Player, Track


class MyPlayer(Player[Client]):
    def __init__(self, client: Client, channel: Connectable) -> None:
        super().__init__(client, channel)

        self.queue: deque[Track] = deque()
        self.text_channel: TextChannel | VoiceChannel | Thread | None = None
        self.now_playing_message: Message | None = None

    async def disconnect(self, *, force: bool = False) -> None:
        await self.delete_now_playing_message()
        await super().disconnect(force=force)

    async def delete_now_playing_message(self) -> None:
        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except NotFound:
                pass
