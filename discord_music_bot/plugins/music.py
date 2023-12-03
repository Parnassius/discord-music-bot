from __future__ import annotations

import asyncio
from typing import cast

from discord import (
    Embed,
    Guild,
    Interaction,
    Member,
    TextChannel,
    Thread,
    VoiceChannel,
    VoiceState,
)
from discord.app_commands import guild_only
from discord.app_commands.checks import bot_has_permissions
from discord.utils import escape_markdown
from wavelink import (
    InvalidNodeException,
    LavalinkLoadException,
    Playable,
    Playlist,
    TrackEndEventPayload,
    TrackStartEventPayload,
    WebsocketClosedEventPayload,
)

from discord_music_bot.bot import MyBot
from discord_music_bot.player import MyPlayer


async def setup(bot: MyBot) -> None:
    @bot.tree.command(description="Play a track from YouTube.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def play(interaction: Interaction[MyBot], song: str) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        channel = cast(TextChannel | VoiceChannel | Thread, interaction.channel)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player:
            if user.voice and user.voice.channel:
                try:
                    player = await user.voice.channel.connect(
                        cls=MyPlayer, self_deaf=True
                    )
                except (IndexError, InvalidNodeException):
                    await interaction.followup.send(
                        "Connection to Lavalink not yet established."
                    )
                    return
            else:
                await interaction.followup.send("You're not in a voice channel.")
                return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        player.text_channel = channel

        try:
            results = await Playable.search(song)
        except LavalinkLoadException:
            await interaction.followup.send("Failed to load track, please try again.")
            return
        if not results:
            await interaction.followup.send("No results found.")
            return

        if isinstance(results, Playlist):
            player.play_queue.extend(results.tracks)

            embed = Embed(
                title="Playlist enqueued", description=escape_markdown(results.name)
            )
            for i, track in enumerate(results.tracks, 1):
                if i > 25:
                    break
                track_link = _track_link(track)
                embed.add_field(name="", value=f"{i}) {track_link}", inline=False)
            if len(results.tracks) > 25:
                embed.set_footer(text=f"... and {len(results.tracks) - 25} more.")

        else:
            track = results[0]
            player.play_queue.append(track)

            track_link = _track_link(track)
            embed = Embed(title="Track enqueued", description=track_link)

        await interaction.followup.send(embed=embed)

        if not player.playing:
            await player.play(player.play_queue.popleft())

    @bot.tree.command(description="Seek the current track.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def seek(interaction: Interaction[MyBot], timestamp: str) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.current:
            await interaction.followup.send("There is nothing playing.")
            return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        try:
            position = int(player.position) + int(timestamp) * 1000
        except ValueError:
            position = 0
            try:
                for part in timestamp.split(":"):
                    position = position * 60 + int(part)
            except ValueError:
                await interaction.followup.send("Invalid timestamp specified.")
                return
            position *= 1000

        if position > player.current.length:
            await interaction.followup.send("Invalid timestamp specified.")
            return

        if position < 0:
            position = 0

        await player.seek(position)

        timestamp = _timestamp(position, player.current.length >= 60 * 60 * 100)
        await interaction.followup.send(f"Moved to {timestamp}.")

    @bot.tree.command(description="Loop the current track.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def loop(interaction: Interaction[MyBot]) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.current:
            await interaction.followup.send("There is nothing playing.")
            return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        if player.loop is player.current:
            player.loop = False
            await interaction.followup.send("Looping disabled.")
        else:
            player.loop = player.current
            await interaction.followup.send("Track looping enabled.")

    @bot.tree.command(description="Loop the current queue.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def loopall(interaction: Interaction[MyBot]) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.current:
            await interaction.followup.send("There is nothing playing.")
            return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        if player.loop is True:
            player.loop = False
            await interaction.followup.send("Looping disabled.")
        else:
            player.loop = True
            await interaction.followup.send("Queue looping enabled.")

    @bot.tree.command(description="Skip to the next track.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def skip(interaction: Interaction[MyBot]) -> None:
        await _skip(interaction)

    @bot.tree.command(description="Stop the music.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def stop(interaction: Interaction[MyBot]) -> None:
        await _skip(interaction, clear=True)

    async def _skip(interaction: Interaction[MyBot], *, clear: bool = False) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.current:
            await interaction.followup.send("There is nothing playing.")
            return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        if clear:
            player.play_queue.clear()
        skipped_track = player.current
        await player.stop()

        if clear:
            await interaction.followup.send("Queue cleared.")
        else:
            track_link = _track_link(skipped_track)
            embed = Embed(title="Track skipped", description=track_link)
            await interaction.followup.send(embed=embed)

    @bot.tree.command(description="Remove a track from the queue.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def remove(interaction: Interaction[MyBot], song: str) -> None:
        await _remove_or_bump(interaction, song, bump=False)

    @bot.tree.command(description="Move a track to the top of the queue.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def bump(interaction: Interaction[MyBot], song: str) -> None:
        await _remove_or_bump(interaction, song, bump=True)

    async def _remove_or_bump(
        interaction: Interaction[MyBot], song: str, *, bump: bool
    ) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.current:
            await interaction.followup.send("The track queue is currently empty.")
            return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        song = song.casefold()

        if not bump and song in player.current.title.casefold():
            skipped_track = player.current
            await player.stop()
            track_link = _track_link(skipped_track)
            embed = Embed(title="Track skipped", description=track_link)
            await interaction.followup.send(embed=embed)
            return

        for track in player.play_queue:
            if song in track.title.casefold():
                player.play_queue.remove(track)
                if bump:
                    player.play_queue.appendleft(track)
                track_link = _track_link(track)
                if bump:
                    embed = Embed(
                        title="Track moved to the top of the queue",
                        description=track_link,
                    )
                else:
                    embed = Embed(title="Track removed", description=track_link)
                await interaction.followup.send(embed=embed)
                return

        await interaction.followup.send("The track was not found in the queue.")

    @bot.tree.command(description="Show the current queue.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def queue(interaction: Interaction[MyBot]) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.current:
            await interaction.followup.send("The track queue is currently empty.")
            return

        track_link = _track_link(player.current)
        position = int(20 / player.current.length * player.position)
        progress_bar_before = "-" * position
        progress_bar_after = "-" * (19 - position)
        progress_bar = f"{progress_bar_before}:radio_button:{progress_bar_after}"
        timestamp_current = _timestamp(
            player.position, player.current.length > 60 * 60 * 1000
        )
        timestamp_total = _timestamp(player.current.length)
        description = (
            f"Now playing: {track_link}\n"
            f"{timestamp_current} {progress_bar} {timestamp_total}"
        )
        embed = Embed(title="Song queue", description=description)
        for i, track in enumerate(player.play_queue, 1):
            if i > 25:
                break
            track_link = _track_link(track)
            embed.add_field(name="", value=f"{i}) {track_link}", inline=False)
        if len(player.play_queue) > 25:
            embed.set_footer(text=f"... and {len(player.play_queue) - 25} more.")

        await interaction.followup.send(embed=embed)

    @bot.tree.command(description="Disconnect from the voice channel.")
    @guild_only()
    @bot_has_permissions(view_channel=True, send_messages=True)
    async def disconnect(interaction: Interaction[MyBot]) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player or not player.connected:
            await interaction.followup.send("I'm not in a voice channel.")
            return

        if not user.voice:
            await interaction.followup.send("You're not in a voice channel.")
            return

        if user.voice.channel != player.channel:
            await interaction.followup.send("We're not in the same voice channel.")
            return

        await player.disconnect()

        await interaction.followup.send("Disconnected.")

    @bot.listen()
    async def on_voice_state_update(
        member: Member, before: VoiceState, after: VoiceState  # noqa: ARG001
    ) -> None:
        player = cast(MyPlayer | None, member.guild.voice_client)
        if not player:
            return
        voice_channel = player.channel
        if all(x.bot for x in voice_channel.members):
            await asyncio.sleep(15)
            if all(x.bot for x in voice_channel.members):
                await player.disconnect()

    @bot.listen()
    async def on_wavelink_track_start(payload: TrackStartEventPayload) -> None:
        player = cast(MyPlayer, payload.player)

        if player.text_channel:
            track_link = _track_link(payload.track)
            embed = Embed(title="Now playing", description=track_link)
            player.now_playing_message = await player.text_channel.send(embed=embed)

    @bot.listen()
    async def on_wavelink_track_end(payload: TrackEndEventPayload) -> None:
        if payload.player is None:
            return

        player = cast(MyPlayer, payload.player)

        await player.delete_now_playing_message()
        if isinstance(player.loop, Playable):
            await player.play(player.loop)
        else:
            if player.loop:
                player.play_queue.append(payload.track)
            try:
                await player.play(player.play_queue.popleft())
            except IndexError:
                pass

    @bot.listen()
    async def on_wavelink_websocket_closed(
        payload: WebsocketClosedEventPayload,
    ) -> None:
        if payload.player is None:
            return

        player = cast(MyPlayer, payload.player)

        await player.delete_now_playing_message()

    def _timestamp(milliseconds: int | float, show_hours: bool | None = None) -> str:
        parts = []
        minutes, seconds = divmod(int(milliseconds / 1000), 60)
        if show_hours or (show_hours is None and minutes >= 60):
            hours, minutes = divmod(minutes, 60)
            parts.append(str(hours))
        parts.append(f"{minutes:0>2}")
        parts.append(f"{seconds:0>2}")
        return ":".join(parts)

    def _track_link(track: Playable) -> str:
        track_title = escape_markdown(track.title)
        if not track.uri:
            return track_title
        track_uri = escape_markdown(track.uri)
        return f"[{track_title}]({track_uri})"
