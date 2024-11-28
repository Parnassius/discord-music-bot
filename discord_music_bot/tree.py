import io
from traceback import format_exception

from discord import File, Interaction
from discord.app_commands import AppCommandError, CommandTree

from discord_music_bot.bot import MyBot


class MyTree(CommandTree[MyBot]):
    async def on_error(
        self, interaction: Interaction[MyBot], error: AppCommandError, /
    ) -> None:
        if not interaction.client.owner_id:
            return
        target = await interaction.client.fetch_user(interaction.client.owner_id)
        command = f"`{interaction.command.name}`" if interaction.command else "tree"
        tb = format_exception(type(error), error, error.__traceback__)
        file = File(io.BytesIO("".join(tb).encode()), filename="traceback.txt")
        await target.send(f"Command {command} raised an exception", file=file)

        if interaction.response.is_done():
            await interaction.followup.send(str(error), ephemeral=True)
        else:
            await interaction.response.send_message(str(error), ephemeral=True)
