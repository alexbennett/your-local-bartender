import os
import requests
import asyncio
import speech_recognition as sr
from gtts import gTTS
import traceback
import json
import discord
from discord.ext import commands
import yt_dlp as youtube_dl

import config
import utilities

COMMAND_PREFIX = ">"
COMMANDS_PIC = ">pic"
COMMANDS_BARTENDER = ">bartender"
COMMANDS_SAY = ">say"
COMMANDS_READ = ">read"
COMMANDS_PROG = ">py"
COMMANDS_PLAY = ">play"
COMMANDS_STOP = ">stop"
COMMANDS_QUEUE = ">queue"
COMMANDS_CLEAR = ">clear"
COMMANDS_SKIP = ">skip"

class Bartender(commands.Bot):
    """
    Discord bot class representing a Bartender.

    Inherits from commands.Bot class provided by Discord.py.
    """

    def __init__(self, command_prefix, intents):
        """
        Initializes a new instance of the Bartender class.

        Args:
            command_prefix (str): Prefix to use for bot commands.
            intents (discord.Intents): Intents to enable for the bot.
        """
        super().__init__(command_prefix=command_prefix, intents=intents)
        self._messages = []
        self._programs = []
        self._guild = None
        self._voice_client = None
        self._queue = []

    async def play_next_in_queue(self):
        """
        Plays the next item in the queue, if any.
        """
        if self._queue:
            message, title, url, next_item = self._queue.pop(0)  # Get the first item in the queue
            await message.add_reaction("🎵")
            await message.reply(f"Now playing _{title}_ {url}", suppress_embeds=True)
            await self.play_file(next_item)
            await message.clear_reaction("🎵")
            await message.add_reaction("✅")

    async def prog(self, message, respond=True, remember=True, recall=True):
        """
        Bartender reads the prompt, generates a program, and potentially plays a TTS audio response in the voice channel.

        Args:
            message (discord.Message): Discord message instance representing the prog command.
            respond (bool, optional): If True, the bot will generate a TTS audio response and play it in the voice channel. Defaults to True.
            remember (bool, optional): If True, the bot will commit the phrase and response to its memory to maintain conversational context. Defaults to True.
            recall (bool, optional): If True, the bot will prepend all messages from its memory to the response request. Defaults to True.
        """
        phrase = message.content[len(COMMANDS_READ) + 1 :]

        print(
            f"Listening to program request: '{phrase}' - Respond? {respond} Remember? {remember} Recall? {recall}"
        )

        # Build message queue
        messages = [
            {
                "role": "system",
                "content": config.RESPONSE_PROMPT_2,
            },
        ]

        # Load previous conversation into message queue
        if recall:
            messages.extend(self._programs)

        # Remember phrase
        if remember:
            await message.add_reaction("🧠")
            self._programs.append(dict(role="user", content=phrase))

        # Add new message to queue
        messages.append({"role": "user", "content": phrase})

        # Get response from OpenAI
        await message.add_reaction("🤔")

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            },
            json={"model": config.OPENAI_MODEL, "messages": messages, "temperature": 0.5},
        )

        # print(f"OpenAI API response: {json.dumps(response.json(), indent=2)}")

        generated_response = response.json()["choices"][0]["message"]["content"].strip()

        await message.clear_reaction("🤔")
        await message.reply(generated_response)

        # Remember generated phrase
        if remember:
            self._programs.append({"role": "assistant", "content": generated_response})

        if respond:
            pass
           
        await message.add_reaction("✅")

        print(f"🧠 Bartender program memory dump:\n{json.dumps(self._programs, indent=2)}")

    async def read(self, message, respond=True, remember=True, recall=True):
        """
        Bartender reads the phrase, generates a response, and potentially plays a TTS audio response in the voice channel.

        Args:
            message (discord.Message): Discord message instance representing the read command.
            respond (bool, optional): If True, the bot will generate a TTS audio response and play it in the voice channel. Defaults to True.
            remember (bool, optional): If True, the bot will commit the phrase and response to its memory to maintain conversational context. Defaults to True.
            recall (bool, optional): If True, the bot will prepend all messages from its memory to the response request. Defaults to True.
        """
        phrase = message.content[len(COMMANDS_READ) + 1 :]

        print(
            f"Listening to phrase: '{phrase}' - Respond? {respond} Remember? {remember} Recall? {recall}"
        )

        # Build message queue
        messages = [
            {
                "role": "system",
                "content": config.RESPONSE_PROMPT_INSULT_1,
            },
        ]

        # Load previous conversation into message queue
        if recall:
            messages.extend(self._messages)

        # Remember phrase
        if remember:
            await message.add_reaction("🧠")
            self._messages.append(dict(role="user", content=f"[{message.author.name}] {phrase}"))

        # Add new message to queue
        messages.append(dict(role="user", content=f"[{message.author.name}] {phrase}"))

        # Get response from OpenAI
        if respond:
            await message.add_reaction("🤔")

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                },
                json={"model": config.OPENAI_MODEL, "messages": messages, "temperature": 0.1},
            )

            print(f"OpenAI API response: {json.dumps(response.json(), indent=2)}")

            generated_response = (
                response.json()["choices"][0]["message"]["content"]
                .strip()
            )

            # Remember generated phrase
            if remember:
                self._messages.append({"role": "assistant", "content": generated_response})

            tts = gTTS(text=generated_response, lang="es", tld="com.mx")
            tts.save("audio.mp3")

            await message.clear_reaction("🤔")
            await message.reply(generated_response)
            await message.add_reaction("🗣️")
            await self.play_file("./audio.mp3")

        await message.add_reaction("✅")

        print(f"🧠 Bartender memory dump:\n{json.dumps(self._messages, indent=2)}")

    async def pic(self, message):
        """
        Generates images based on a prompt and sends them as responses in the Discord channel.

        Args:
            message (discord.Message): Discord message instance representing the pic command.
        """
        await message.add_reaction("🤔")

        image_urls = utilities.call_image_generation_api(
            message.content[len(COMMANDS_PIC):], n=1, size="512x512"
        )

        await message.clear_reaction("🤔")
        await message.add_reaction("⏬")

        imgs = utilities.download_images(image_urls, "generated_images")

        await message.clear_reaction("⏬")

        for img in imgs:
            await message.reply(file=discord.File(img))

        await message.add_reaction("✅")

    async def say(self, message):
        """
        Generates TTS audio from a text message and plays it in the voice channel.

        Args:
            message (discord.Message): Discord message instance representing the say command.
        """
        await message.add_reaction("🤔")

        print(f'Generating TTS audio for: "{message.content[len(COMMANDS_SAY):]}"')

        tts = gTTS(text=message.content[4:], lang="en", tld=config.GTTS_TLD)
        tts.save("audio.mp3")

        await message.clear_reaction("🤔")
        await message.add_reaction("🗣️")
        await self.play_file("./audio.mp3")
        await message.clear_reaction("🗣️")
        await message.add_reaction("✅")

    async def play_file(self, source="./audio.mp3", auto_disconnect=True):
        """
        Plays an audio file in the voice channel.

        Args:
            source (str, optional): Path to the audio file. Defaults to "./audio.mp3".
            auto_disconnect (bool, optional): If True, the bot will automatically disconnect from the voice channel after playback. Defaults to True.
        """
        # Connect voice client to the "bartender" channel
        self._guild = self.guilds[0]  # Assuming the bot is only in one guild
        channel = discord.utils.get(self._guild.voice_channels, name=config.DISCORD_DEFAULT_CHANNEL)

        # Handle (re)connection
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.move_to(channel)
        else:
            self._voice_client = await channel.connect()

        if os.name == "nt":
            audio = discord.FFmpegPCMAudio(
                executable="c:/ffmpeg/bin/ffmpeg.exe", source=source, options="-af \"atempo=1.0\""
            )
        elif os.name == "posix":
            audio = discord.FFmpegPCMAudio(executable="ffmpeg", source=source, options="-af \"atempo=1.0\"")

        # Play the audio file using FFmpeg
        self._voice_client.play(audio)

        # Wait for playback to finish
        while self._voice_client.is_playing():
            await asyncio.sleep(0.1)

        # Disconnect
        if auto_disconnect:
            await self._voice_client.disconnect()

    async def play_youtube(self, message):
        """
        Plays audio from a YouTube video.

        Args:
            url_or_query (str): URL or query string.
        """
        url_or_query = message.content[len(COMMANDS_PLAY) + 1:]

        await message.add_reaction("🔍")

        # Determine if it's a URL or query string
        if "youtube.com" in url_or_query or "youtu.be" in url_or_query:
            url = url_or_query
            title = url_or_query
        else:
            # Use youtube_dl to search YouTube for the query
            with youtube_dl.YoutubeDL({"default_search": "ytsearch1:", "quiet": True}) as ydl:
                info = ydl.extract_info(url_or_query, download=False)
                with open("youtube_dl_info.json", "w") as f:
                    json.dump(info, f, indent=2)
                url = info["entries"][0]["webpage_url"]
                title = info["entries"][0]["title"]

        filename = 'downloaded_songs/' + info["title"]

        # Download the audio from the YouTube video
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': filename,
            'quiet': True
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
            await message.reply(f"_{title}_ ({url}) added to queue...", suppress_embeds=True)


    async def stop(self, message):
        """
        Stops the bot and disconnects it from the voice channel (if connected).

        Args:
            message (discord.Message): Discord message instance representing the stop command.
        """
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.disconnect()
            await message.add_reaction("👋")
        else:
            await message.add_reaction("❌")

    async def clear(self, message):
        """
        Clears a specified number of messages in the channel where the command is invoked.

        Args:
            message (discord.Message): Discord message instance representing the clear command.

        Returns:
            List[discord.Message]: List of deleted messages.
        """
        channel = message.channel
        deleted = await channel.purge(limit=5, check=lambda x: True)
        return deleted

    async def view_queue(self, message):
        """
        Displays the upcoming items in the queue.

        Args:
            message (discord.Message): Discord message instance representing the queue command.
        """
        if not self._queue:
            await message.reply("The queue is empty.")
            return

        queue_info = "\n".join([f"{i+1}. _{title}_ ({url})" for i, (_, title, url, _) in enumerate(self._queue)])
        await message.reply(f"Upcoming queue:\n{queue_info}", suppress_embeds=True)
        
    async def on_ready(self):
        """
        Event handler that runs when the bot successfully logs in.
        """
        print(f"Logged in as {self.user.name}")

    async def on_message(self, message):
        """
        Event handler that runs whenever a message is sent in a channel the bot can see.

        Args:
            message (discord.Message): The received message.
        """
        if message.content.startswith(COMMANDS_SAY):
            print(f"Handling SAY")
            try:
                await self.say(message)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to speak")
        elif message.content.startswith(COMMANDS_READ):
            print(f"Handling READ")
            try:
                await self.read(message, respond=True, remember=True, recall=True)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to read")
        elif message.content.startswith(COMMANDS_PROG):
            print(f"Handling PROG")
            try:
                await self.prog(message, respond=True, remember=True, recall=True)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to prog")
        elif message.content.startswith(COMMANDS_PIC):
            print(f"Handling PIC")
            try:
                await self.pic(message)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to generate pic")
        elif message.content.startswith(COMMANDS_CLEAR):
            print("Handling CLEAR")
            try:
                await self.clear(message)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to clear")
        elif message.content.startswith(COMMANDS_PLAY):
            print("Handling PLAY")
            try:
                await self.play_youtube(message)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to play YouTube video/audio")
        elif message.content.startswith(COMMANDS_STOP):
            print("Handling STOP")
            try:
                await self.stop(message)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to stop")
        elif message.content.startswith(COMMANDS_QUEUE):
            print("Handling QUEUE")
            try:
                await self.view_queue(message)
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to show queue")
        elif message.content.startswith(COMMANDS_SKIP):
            print("Handling SKIP")
            try:
                await self.play_next_in_queue()
            except:
                await message.add_reaction("❌")
                print(traceback.format_exc())
                print("Unable to skip item")

    async def on_voice_state_update(self, member, before, after):
        print(f"Voice state update: {member} {before} {after}")
        # Check if the bot should play the next item in the queue when a user leaves the voice channel
        if member == self.user and before.channel is not None:
            await self.play_next_in_queue()

if __name__ == "__main__":
    bot = Bartender(command_prefix=">", intents=discord.Intents.all())
    bot.run(config.DISCORD_BOT_TOKEN)
