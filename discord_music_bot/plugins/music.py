from __future__ import annotations

import asyncio
from typing import cast

from discord import (
    Embed,
    Guild,
    Interaction,
    Member,
    StageChannel,
    TextChannel,
    Thread,
    VoiceChannel,
    VoiceState,
)
from discord.app_commands import guild_only
from discord.utils import escape_markdown
from mafic import Playlist, Track, TrackEndEvent, TrackStartEvent

from discord_music_bot.bot import MyBot
from discord_music_bot.player import MyPlayer


async def setup(bot: MyBot) -> None:
    @bot.tree.command(  # type: ignore[arg-type]
        description="Play a track from YouTube."
    )
    @guild_only()
    async def play(interaction: Interaction[MyBot], song: str) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        channel = cast(TextChannel | VoiceChannel | Thread, interaction.channel)
        user = cast(Member, interaction.user)
        player = cast(MyPlayer | None, guild.voice_client)

        if not player:
            if user.voice and user.voice.channel:
                player = await user.voice.channel.connect(cls=MyPlayer, self_deaf=True)
            else:
                await interaction.followup.send("You're not in a voice channel.")
                return

        if not player.node.available:
            voice_channel = cast(VoiceChannel | StageChannel, player.channel)
            await player.disconnect()
            while bot.user in voice_channel.members:
                await asyncio.sleep(0.05)
            player = await voice_channel.connect(cls=MyPlayer, self_deaf=True)

        player.text_channel = channel

        results = await player.fetch_tracks(song)
        if not results:
            await interaction.followup.send("No results found.")
            return

        if isinstance(results, Playlist):
            player.queue.extend(results.tracks)

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
            player.queue.append(track)

            track_link = _track_link(track)
            embed = Embed(title="Track enqueued", description=track_link)

        await interaction.followup.send(embed=embed)

        if not player.current:
            await player.play(player.queue.popleft())

    @bot.tree.command(description="Skip to the next track.")  # type: ignore[arg-type]
    @guild_only()
    async def skip(interaction: Interaction[MyBot]) -> None:
        await _skip(interaction)

    @bot.tree.command(description="Stop the music.")  # type: ignore[arg-type]
    @guild_only()
    async def stop(interaction: Interaction[MyBot]) -> None:
        await _skip(interaction, clear=True)

    async def _skip(interaction: Interaction[MyBot], *, clear: bool = False) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        player = cast(MyPlayer | None, guild.voice_client)
        if not player or not player.current:
            await interaction.followup.send("There is nothing playing.")
            return

        if clear:
            player.queue.clear()
        skipped_track = player.current
        await player.stop()

        if clear:
            await interaction.followup.send("Queue cleared.")
        else:
            track_link = _track_link(skipped_track)
            embed = Embed(title="Track skipped", description=track_link)
            await interaction.followup.send(embed=embed)

    @bot.tree.command(  # type: ignore[arg-type]
        description="Remove a track from the queue."
    )
    @guild_only()
    async def remove(interaction: Interaction[MyBot], song: str) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        player = cast(MyPlayer | None, guild.voice_client)
        if not player or not player.current:
            await interaction.followup.send("The track queue is currently empty.")
            return

        song = song.casefold()

        if song in player.current.title.casefold():
            skipped_track = player.current
            await player.stop()
            track_link = _track_link(skipped_track)
            embed = Embed(title="Track skipped", description=track_link)
            await interaction.followup.send(embed=embed)
            return

        for track in player.queue:
            if song in track.title.casefold():
                player.queue.remove(track)
                track_link = _track_link(track)
                embed = Embed(title="Track removed", description=track_link)
                await interaction.followup.send(embed=embed)
                return

        await interaction.followup.send("The track was not found in the queue.")

    @bot.tree.command(description="Show the current queue.")  # type: ignore[arg-type]
    @guild_only()
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
        timestamp_current = _timestamp(player.position)
        timestamp_total = _timestamp(player.current.length)
        description = (
            f"Now playing: {track_link}\n"
            f"{timestamp_current} {progress_bar} {timestamp_total}"
        )
        embed = Embed(title="Song queue", description=description)
        for i, track in enumerate(player.queue, 1):
            if i > 25:
                break
            track_link = _track_link(track)
            embed.add_field(name="", value=f"{i}) {track_link}", inline=False)
        if len(player.queue) > 25:
            embed.set_footer(text=f"... and {len(player.queue) - 25} more.")

        await interaction.followup.send(embed=embed)

    @bot.tree.command(  # type: ignore[arg-type]
        description="Disconnect from the voice channel."
    )
    @guild_only()
    async def disconnect(interaction: Interaction[MyBot]) -> None:
        await interaction.response.defer()

        guild = cast(Guild, interaction.guild)
        player = cast(MyPlayer | None, guild.voice_client)
        if not player or not player.connected:
            await interaction.followup.send("I'm not in a voice channel.")
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
        voice_channel = cast(VoiceChannel | StageChannel, player.channel)
        if voice_channel.members == [bot.user]:
            await asyncio.sleep(15)
            if voice_channel.members == [bot.user]:
                await player.disconnect()

    @bot.listen()
    async def on_track_start(event: TrackStartEvent[MyPlayer]) -> None:
        if event.player.text_channel:
            track_link = _track_link(event.track)
            embed = Embed(title="Now playing", description=track_link)
            event.player.now_playing_message = await event.player.text_channel.send(
                embed=embed
            )

    @bot.listen()
    async def on_track_end(event: TrackEndEvent[MyPlayer]) -> None:
        if event.player.now_playing_message:
            await event.player.now_playing_message.delete()
        if event.player.queue:
            await event.player.play(event.player.queue.popleft())

    def _timestamp(milliseconds: int | float) -> str:
        minutes, seconds = divmod(int(milliseconds / 1000), 60)
        return f"{minutes:0>2}:{seconds:0>2}"

    def _track_link(track: Track) -> str:
        track_title = escape_markdown(track.title)
        if not track.uri:
            return track_title
        track_uri = escape_markdown(track.uri)
        return f"[{track_title}]({track_uri})"
