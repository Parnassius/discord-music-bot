from __future__ import annotations

from collections import deque

from discord import Client, Message, TextChannel, Thread, VoiceChannel
from discord.abc import Connectable
from mafic import Player, Track


class MyPlayer(Player[Client]):
    def __init__(self, client: Client, channel: Connectable) -> None:
        super().__init__(client, channel)

        self.queue: deque[Track] = deque()
        self.text_channel: TextChannel | VoiceChannel | Thread | None = None
        self.now_playing_message: Message | None = None
