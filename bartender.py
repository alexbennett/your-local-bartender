import os
import subprocess
import requests
import asyncio
import aiohttp
import time
import threading
import speech_recognition as sr
from gtts import gTTS
import traceback
import json
import mafic
import discord
from discord.ext import commands
import wavelink
import yt_dlp as youtube_dl
from openai import OpenAI

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
COMMANDS_LISTEN = ">listen"
COMMANDS_JOIN = ">join"

r = sr.Recognizer()
client = OpenAI()

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
        self._connections = {}
        self._guild = None
        self._voice_client = None
        self._queue = []
        self._is_recording = False
        self._is_speaking = False
        self.pool = mafic.NodePool(self)
        self.listen_thread = None  # Initialize listen_thread attribute

        self.loop.create_task(self.add_nodes())

    async def get_last_x_messages(self, channel, x):
        """
        Retrieves the last X messages from a specific text channel and returns them as a dictionary.

        Args:
            channel_id (int): The ID of the text channel from which to retrieve messages.
            x (int): The number of last messages to retrieve.

        Returns:
            dict: A dictionary where keys are sender display names and values are sender messages.
        """
        if channel is None:
            return {}  # Return an empty dictionary if the channel is not found

        messages = await channel.history(
            limit=x
        ).flatten()  # Get the last X messages from the channel

        message_dict = {}
        for message in messages:
            sender_name = message.author.name
            message_content = message.content
            message_dict[sender_name] = message_content

        return message_dict

    async def online_users(self, message):
        """Gets a list of online users from the given message's guild."""

        online_members = [
            member.display_name
            for member in message.guild.members
            if member.status == discord.Status.online
        ]

        return online_members

    async def bot_display_name(self, message):
        """Gets the display name of the bot in the given message's guild."""
        
        bot_member = message.guild.get_member(self.user.id)
        
        if bot_member:
            return bot_member.display_name
        else:
            return "Bartender"
        
    async def users_in_voice_channel(self, message):
        """Gets a list of user display names in the same voice channel as the sender of the message."""

        voice_channel = message.author.voice.channel if message.author.voice else None

        if voice_channel:
            return [member.display_name for member in voice_channel.members]
        else:
            return None
    
    async def add_nodes(self):
        await self.pool.create_node(
            host="127.0.0.1",
            port=2333,
            label="MAIN",
            password="*#kRzdk5u#P7",
        )

    async def play_next_in_queue(self):
        """
        Plays the next item in the queue, if any.
        """
        if self._queue:
            message, title, url, next_item = self._queue.pop(
                0
            )  # Get the first item in the queue
            await message.add_reaction("🎵")
            await message.reply(f"Now playing _{title}_ {url}")
            await self.play_file(next_item, auto_disconnect=True)
            await message.clear_reaction("🎵")
            await message.add_reaction("✅")

    async def join(self, message):
        """
        Joins the requester's voice channel and starts recording all voice activity in 30-second intervals.

        Args:
            message (discord.Message): Discord message instance representing the join command.
        """
        # Check if the user is in a voice channel
        if message.author.voice is None:
            await message.reply("You are not in a voice channel.")
            return

        # Connect to the user's voice channel
        channel = message.author.voice.channel
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.move_to(channel)
        else:
            self._voice_client = await channel.connect()

        # Create a thread to run the continuous recording loop
        self.listen_thread = threading.Thread(
            target=self.continuous_listen,
            args=(message.channel, message)
        )
        self.listen_thread.daemon = True
        self.listen_thread.start()
        await message.add_reaction("👂")

    async def stop(self, message):
        """
        Stops the bot and disconnects it from the voice channel (if connected).

        Args:
            message (discord.Message): Discord message instance representing the stop command.
        """
        if self.listen_thread:
            self.listen_thread.join()  # Stop the continuous_listen thread

        if self._voice_client and self._is_recording:
            self._voice_client.stop_recording()
            self._is_recording = False
        else:
            await message.respond("I am currently not recording here.")

        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.disconnect()
            await message.add_reaction("👋")
        else:
            await message.add_reaction("❌")

    async def once_done(
        self, sink: discord.sinks, channel: discord.TextChannel, *args
    ):
        message = args[0]  # Get the message from the args.

        # Check if any users were recorded
        if not sink.audio_data:
            print("No users were recorded, looping again...")
            return

        for user_id, audio in sink.audio_data.items():
            user_name = await self.get_username_from_id(user_id, message.guild)
            if user_name:
                transcript = await self.process_audio_stream(user_name, audio)

                # Tag each transcript with the username/display name
                tagged_transcript = f"{user_name}: {transcript}"

                await self.read(
                    message,
                    override_phrase=tagged_transcript,
                    respond=config.CONTINUOUS_LISTEN_ACTIVATOR in tagged_transcript.lower(),
                    remember=True,
                    recall=True,
                    override_author_name=user_name,
                )
            else:
                print(f"User with ID {user_id} not found in the guild.")

    async def get_username_from_id(self, user_id, guild):
        try:
            user = await guild.fetch_member(user_id)
            if user:
                return user.display_name
        except Exception as e:
            print(f"Error fetching username for user ID {user_id}: {str(e)}")
        return None
    
    async def process_audio_stream(self, user_name, audio):
        filename = f"generated_audio/request-{user_name}.wav"

        with open(filename, "wb") as f:
            f.write(audio.file.getbuffer())

        audio_file = open(filename, "rb")

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )
        print(f"[{user_name}]: {transcript}")

        return transcript
    
    async def listen(self, message):
        # Check if the user is in a voice channel
        if message.author.voice is None:
            await message.reply("You are not in a voice channel.")
            return

        # Connect to the user's voice channel
        channel = message.author.voice.channel
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.move_to(channel)
        else:
            self._voice_client = await channel.connect()

        self._voice_client.start_recording(
            discord.sinks.WaveSink(),  # The sink type to use.
            self.once_done,  # What to do once done.
            message.channel,  # The channel to disconnect from.
            message,  # The args to pass to the callback.
            filter=lambda m: m.author.id == message.author.id,  # Record only the requester
        )
        self._is_recording = True
        await message.add_reaction("👂")

        await asyncio.sleep(7)  # Wait for 5 seconds.

        if self._is_recording:  # Check if the guild is in the cache.
            self._voice_client.stop_recording()  # Stop recording, and call the callback (once_done).
            self._is_recording = False

        await message.clear_reaction("👂")

        
    def continuous_listen(self, text_channel, message):
        """
        Continuous loop to record voice activity in 30-second intervals.
        
        Args:
            text_channel (discord.TextChannel): Discord text channel to send messages.
            message (discord.Message): Discord message instance representing the join command.
        """
        while True:            
            try:
                if not self._voice_client.is_connected():
                    print("Voice client is not connected, exiting continuous_listen")
                    break

                if not self._is_recording:
                    self._voice_client.start_recording(
                        discord.sinks.WaveSink(),
                        self.once_done,
                        text_channel,
                        message
                    )
                    self._is_recording = True

                time.sleep(config.CONTINUOUS_LISTEN_RECORDING_INTERVAL)

                if self._is_recording:
                    try:
                        if self.listen_thread:
                            self.listen_thread.join()  # Stop the continuous_listen thread
                    except:
                        pass
                    self._voice_client.stop_recording()
                    self._is_recording = False

                time.sleep(config.CONTINUOUS_LISTEN_PAUSE_TIME)

            except Exception as e:
                print(f"Error in continuous_listen: {str(e)}")


    async def read(
        self,
        message,
        override_phrase: str = None,
        override_author_name: str = None,
        respond=True,
        remember=True,
        recall=True,
    ):
        """
        Bartender reads the phrase, generates a response, and potentially plays a TTS audio response in the voice channel.

        Args:
            message (discord.Message): Discord message instance representing the read command.
            respond (bool, optional): If True, the bot will generate a TTS audio response and play it in the voice channel. Defaults to True.
            remember (bool, optional): If True, the bot will commit the phrase and response to its memory to maintain conversational context. Defaults to True.
            recall (bool, optional): If True, the bot will prepend all messages from its memory to the response request. Defaults to True.
        """
        if override_phrase:
            phrase = override_phrase
        else:
            phrase = message.content[len(COMMANDS_READ) + 1 :]

        if override_author_name:
            author_name = override_author_name
        else:
            author_name = message.author.name

        self._guild = self.guilds[0]  # Assuming the bot is only in one guild
        channel = discord.utils.get(
            self._guild.text_channels, name="𝚖𝚎𝚣𝚣𝚊𝚗𝚒𝚗𝚎"
        )

        # Build message queue
        messages = [
            {
                "role": "system",
                "content": config.RESPONSE_PROMPT_1.format(
                    community_name=await self.bot_display_name(message),
                    online_users=await self.online_users(message),
                    same_channel_users=await self.users_in_voice_channel(message),
                    recent_messages=await self.get_last_x_messages(channel, 50),
                ),
            },
        ]

        # Load previous conversation into message queue
        if recall:
            messages.extend(self._messages)

        # Remember phrase
        if remember:
            await message.add_reaction("🧠")
            self._messages.append(
                dict(role="user", content=f"**{author_name}:** {phrase}")
            )

        # Add new message to queue
        messages.append(
            dict(role="user", content=f"[**{author_name}:** {phrase}")
        )

        # Get response from OpenAI asynchronously
        if respond:
            await message.add_reaction("🤔")

            res = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=messages,
                temperature=0.4,
            )

            generated_response = res.choices[0].message.content.strip()

            print(f"[Bartender]: {generated_response}")
        
            # Remember generated phrase
            if remember:
                self._messages.append(
                    {"role": "assistant", "content": generated_response}
                )

            await message.clear_reaction("🤔")
            await message.reply(f"@{author_name} {generated_response}")
            await message.add_reaction("🗣️")
            await self.say_raw(generated_response)
            await message.clear_reaction("🗣️")

        await message.add_reaction("✅")

    async def pic(self, message):
        """
        Generates images based on a prompt and sends them as responses in the Discord channel.

        Args:
            message (discord.Message): Discord message instance representing the pic command.
        """
        await message.add_reaction("🤔")

        image_urls = utilities.call_image_generation_api(
            message.content[len(COMMANDS_PIC) :], n=1, size="512x512"
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
        Generates TTS audio from a text message using OpenAI's Text-to-Speech API and plays it in the voice channel.

        Args:
            message (discord.Message): Discord message instance representing the say command.
        """
        await message.add_reaction("🤔")

        try:
            await message.clear_reaction("🤔")
            await message.add_reaction("🗣️")
            await self.say_raw(message.content[len(COMMANDS_SAY) + 1:])
            await message.clear_reaction("🗣️")
            await message.add_reaction("✅")
        except:
            await message.clear_reaction("🤔")
            await message.add_reaction("❌")
            print("Failed to generate TTS audio")

    async def say_raw(self, message):
        """
        Generates TTS audio from a text message using OpenAI's Text-to-Speech API and plays it in the voice channel.

        Args:
            message (discord.Message): Discord message instance representing the say command.
        """
        try:
            response = client.audio.speech.create(
                model="tts-1-hd",
                voice=config.OPENAI_TTS_VOICE,
                input=message,
            )

            response.stream_to_file("generated_audio/say.mp3")
            self._is_speaking = True
            await self.play_file("generated_audio/say.mp3", tempo=1.0, auto_disconnect=False, auto_move_channel=False)
            self._is_speaking = False
        except:
            print("Failed to generate TTS audio")

    async def play_file(
        self, source="generated_audio/audio.mp3", tempo=1.0, auto_disconnect=True, auto_move_channel=True
    ):
        """
        Plays an audio file in the voice channel.

        Args:
            source (str, optional): Path to the audio file. Defaults to "./audio.mp3".
            auto_disconnect (bool, optional): If True, the bot will automatically disconnect from the voice channel after playback. Defaults to True.
        """
        # Connect voice client to the "bartender" channel
        self._guild = self.guilds[0]  # Assuming the bot is only in one guild
        channel = discord.utils.get(
            self._guild.voice_channels, name=config.DISCORD_DEFAULT_CHANNEL
        )

        # Handle (re)connection
        if auto_move_channel:
            if self._voice_client and self._voice_client.is_connected():
                await self._voice_client.move_to(channel)
            else:
                self._voice_client = await channel.connect()

        await asyncio.sleep(0.1)

        if os.name == "nt":
            audio = discord.FFmpegPCMAudio(
                executable="c:/ffmpeg/bin/ffmpeg.exe",
                source=source,
                options=f'-af "atempo={tempo}"',
            )
        elif os.name == "posix":
            audio = discord.FFmpegPCMAudio(
                executable="ffmpeg", source=source, options=f'-af "atempo={tempo}"'
            )

        # Play the audio file using FFmpeg
        self._voice_client.play(audio)

        # Wait for playback to finish
        while self._voice_client.is_playing():
            await asyncio.sleep(1)

        # Disconnect
        if auto_disconnect:
            await self._voice_client.disconnect()

    async def play_youtube(self, message):
        """
        Plays audio from a YouTube video.

        Args:
            url_or_query (str): URL or query string.
        """
        url_or_query = message.content[len(COMMANDS_PLAY) + 1 :]

        await message.add_reaction("🔍")

        # Determine if it's a URL or query string
        if "youtube.com" in url_or_query or "youtu.be" in url_or_query:
            url = url_or_query
            title = url_or_query
        else:
            # Use youtube_dl to search YouTube for the query
            with youtube_dl.YoutubeDL(
                {"default_search": "ytsearch1:", "quiet": True}
            ) as ydl:
                info = ydl.extract_info(url_or_query, download=False)
                with open("youtube_dl_info.json", "w") as f:
                    json.dump(info, f, indent=2)
                url = info["entries"][0]["webpage_url"]
                title = info["entries"][0]["title"]

        filename = "downloaded_songs/" + info["title"]

        # Download the audio from the YouTube video
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
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

        queue_info = "\n".join(
            [
                f"{i+1}. _{title}_ ({url})"
                for i, (_, title, url, _) in enumerate(self._queue)
            ]
        )
        await message.reply(f"Upcoming queue:\n{queue_info}")


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
                print("Unable to speak")
        elif message.content.startswith(COMMANDS_READ):
            print(f"Handling READ")
            try:
                await self.read(message, respond=True, remember=True, recall=True)
            except:
                await message.add_reaction("❌")
                print("Unable to read")
        elif message.content.startswith(COMMANDS_PROG):
            print(f"Handling PROG")
            try:
                await self.prog(message, respond=True, remember=True, recall=True)
            except:
                await message.add_reaction("❌")
                print("Unable to prog")
        elif message.content.startswith(COMMANDS_PIC):
            print(f"Handling PIC")
            try:
                await self.pic(message)
            except:
                await message.add_reaction("❌")
                print("Unable to generate pic")
        elif message.content.startswith(COMMANDS_CLEAR):
            print("Handling CLEAR")
            try:
                await self.clear(message)
            except:
                await message.add_reaction("❌")
                print("Unable to clear")
        elif message.content.startswith(COMMANDS_PLAY):
            print("Handling PLAY")
            try:
                await self.play_youtube(message)
            except:
                await message.add_reaction("❌")
                print("Unable to play YouTube video/audio")
        elif message.content.startswith(COMMANDS_STOP):
            print("Handling STOP")
            try:
                await self.stop(message)
            except:
                await message.add_reaction("❌")
                print("Unable to stop")
        elif message.content.startswith(COMMANDS_QUEUE):
            print("Handling QUEUE")
            try:
                await self.view_queue(message)
            except:
                await message.add_reaction("❌")
                print("Unable to show queue")
        elif message.content.startswith(COMMANDS_SKIP):
            print("Handling SKIP")
            try:
                await self.play_next_in_queue()
            except:
                await message.add_reaction("❌")
                print("Unable to skip item")
        elif message.content.startswith(COMMANDS_LISTEN):
            print("Handling LISTEN")
            try:
                await self.listen(message)
            except:
                await message.add_reaction("❌")
                print("Unable to listen to voice channel")
        elif message.content.startswith(COMMANDS_JOIN):
            print("Handling JOIN")
            try:
                await self.join(message)
            except:
                print("Error while listening in voice channel")
                print(traceback.format_exc())
                if self._voice_client:
                    await self._voice_client.disconnect()

    async def on_voice_state_update(self, member, before, after):
        # print(f"Voice state update: {member} {before} {after}")
        # Check if the bot should play the next item in the queue when a user leaves the voice channel
        if member == self.user and before.channel is not None:
            await self.play_next_in_queue()

    async def on_wavelink_node_ready(node: wavelink.Node):
        print(f"{node.identifier} is ready.")  # print a message


if __name__ == "__main__":
    bot = Bartender(command_prefix=">", intents=discord.Intents.all())
    bot.run(config.DISCORD_BOT_TOKEN)
