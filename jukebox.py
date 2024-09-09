import os
import asyncio
import json
import discord
import yt_dlp as youtube_dl
from discord.ext import commands
from ylb import config

COMMAND_PREFIX = "!"
COMMANDS_PLAY = "!play"

class Jukebox(commands.Bot):
    """
    Discord bot that plays YouTube audio in voice channels.
    """

    def __init__(self, command_prefix, intents):
        """
        Initializes a new instance of the Jukebox class.

        Args:
            command_prefix (str): Prefix to use for bot commands.
            intents (discord.Intents): Intents to enable for the bot.
        """
        super().__init__(command_prefix=command_prefix, intents=intents)
        self._queue = []
        self._voice_client = None

    async def on_ready(self):
        """Event handler that runs when the bot is ready."""
        print(f"Logged in as {self.user.name}")

    async def on_message(self, message):
        """
        Handles incoming messages and dispatches the play command.

        Args:
            message (discord.Message): The incoming message.
        """
        if message.content.startswith(COMMANDS_PLAY):
            print("Handling PLAY")
            try:
                await self.play_youtube(message)
            except:
                await message.add_reaction("❌")
                print("Unable to play YouTube video/audio")

    async def play_youtube(self, message):
        """
        Downloads and queues audio from a YouTube video.

        Args:
            message (discord.Message): The message containing the YouTube URL or query.
        """
        url_or_query = message.content[len(COMMANDS_PLAY) + 1 :].strip()

        await message.add_reaction("🔍")

        # Use youtube_dl to search YouTube for the query
        with youtube_dl.YoutubeDL({"default_search": "ytsearch1:", "quiet": True}) as ydl:
            info = ydl.extract_info(url_or_query, download=False)
            url = info["entries"][0]["webpage_url"]
            title = info["entries"][0]["title"]

        filename = f"downloaded_songs/{info['title']}"

        # Download the audio from the YouTube video
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "outtmpl": filename,
            "quiet": True,
        }

        await message.clear_reaction("🔍")
        await message.add_reaction("⏬")

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await message.clear_reaction("⏬")

        # Add the downloaded audio file to the queue
        self._queue.append((message, title, url, filename + ".mp3"))

        if not self._voice_client or not self._voice_client.is_connected():
            await self.play_next_in_queue()
        else:
            await message.reply(f"_{title}_ ({url}) added to queue...")

    async def play_next_in_queue(self):
        """Plays the next item in the queue."""
        if self._queue:
            message, title, url, next_item = self._queue.pop(0)
            await message.add_reaction("🎵")
            await message.reply(f"Now playing _{title}_ {url}")
            await self.play_file(next_item)
            await message.clear_reaction("🎵")
            await message.add_reaction("✅")

    async def play_file(self, source):
        """
        Plays an audio file in a voice channel.

        Args:
            source (str): Path to the audio file.
        """
        # Connect voice client to the channel of the user who sent the message
        self._voice_client = discord.utils.get(self.voice_clients)

        if not self._voice_client or not self._voice_client.is_connected():
            channel = self._queue[0][0].author.voice.channel
            self._voice_client = await channel.connect()

        audio = discord.FFmpegPCMAudio(source)
        self._voice_client.play(audio)

        # Wait for playback to finish
        while self._voice_client.is_playing():
            await asyncio.sleep(1)

        await self.play_next_in_queue()

if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    bot = Jukebox(command_prefix=COMMAND_PREFIX, intents=intents)
    bot.run(config.DISCORD_BOT_TOKEN)
