from __future__ import annotations

from discord import Intents
from discord.ext import commands
from typenv import Env

from discord_music_bot.bot import MyBot
from discord_music_bot.tree import MyTree


def main() -> None:
    env = Env()
    env.read_env()

    token = env.str("TOKEN")
    owner_id = env.int("OWNER_ID")
    test_guild_id = env.int("TEST_GUILD_ID", default=None)

    with env.prefixed("LAVALINK_"):
        lavalink_connection = (env.str("HOST"), env.int("PORT"), env.str("PASSWORD"))

    intents = Intents.default()

    bot = MyBot(
        commands.when_mentioned,
        tree_cls=MyTree,
        intents=intents,
        owner_id=owner_id,
        help_command=None,
        lavalink_connection=lavalink_connection,
        test_guild_id=test_guild_id,
    )

    bot.run(token)


if __name__ == "__main__":
    main()
