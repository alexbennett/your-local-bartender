import os
import asyncio
import time
import threading
import speech_recognition as sr
from gtts import gTTS
import traceback
import json
import mafic
import wavelink
import yt_dlp as youtube_dl

import discord
from discord.ext import commands

from openai import OpenAI

from ylb import config
from ylb.llm import ConversationManager  # Import ConversationManager
from ylb.helpers.openai import (
    openai_read_file_into_vector_store,
    openai_get_vector_store_file_ids,
    openai_update_assistant_vector_store,
    openai_update_assistant_code_interpreter,
)
from ylb import utils

TOOLS = [
    openai_get_vector_store_file_ids,
    openai_read_file_into_vector_store,
    openai_update_assistant_code_interpreter,
    openai_update_assistant_vector_store,
]

COMMAND_PREFIX = "!"
COMMANDS_PIC = "!pic"
COMMANDS_SAY = "!say"
COMMANDS_READ = "!read"
COMMANDS_PLAY = "!play"
COMMANDS_STOP = "!stop"
COMMANDS_QUEUE = "!queue"
COMMANDS_CLEAR = "!clear"
COMMANDS_SKIP = "!skip"
COMMANDS_LISTEN = "!listen"
COMMANDS_JOIN = "!join"

r = sr.Recognizer()
client = OpenAI()


class Bartender(commands.Bot):
    """
    Discord bot acting as an AI-powered bartender.

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
        self.listen_thread = None
        self.conversation_manager = None  # Add this line

        self.loop.create_task(self.add_nodes())

    async def get_last_x_messages(self, channel, x):
        """
        Retrieves the last X messages from a specified text channel.

        Args:
            channel (discord.TextChannel): The text channel to retrieve messages from.
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
        """
        Gets a list of online users from the given message's guild.

        Args:
            message (discord.Message): Discord message object.

        Returns:
            list: A list of display names of online users.
        """

        online_members = [
            member.display_name
            for member in message.guild.members
            if member.status == discord.Status.online
        ]

        return online_members

    async def bot_display_name(self, message):
        """
        Gets the display name of the bot in the given message's guild.

        Args:
            message (discord.Message): Discord message object.

        Returns:
            str: The bot's display name in the guild.
        """

        bot_member = message.guild.get_member(self.user.id)

        if bot_member:
            return bot_member.display_name
        else:
            return "Bartender"

    async def users_in_voice_channel(self, message):
        """
        Gets a list of user display names in the same voice channel as the sender of the message.

        Args:
            message (discord.Message): Discord message object.

        Returns:
            list: A list of display names of users in the same voice channel, or None if the sender is not in a voice channel.
        """

        voice_channel = message.author.voice.channel if message.author.voice else None

        if voice_channel:
            return [member.display_name for member in voice_channel.members]
        else:
            return None

    async def add_nodes(self):
        """Asynchronously adds a node to the Mafic node pool."""
        await self.pool.create_node(
            host="127.0.0.1",
            port=2333,
            label="MAIN",
            password="*#kRzdk5u#P7",
        )

    async def play_next_in_queue(self):
        """Plays the next item in the queue and manages reactions."""
        if self._queue:
            message, title, url, next_item = self._queue.pop(0)
            await message.add_reaction("🎵")
            await message.reply(f"Now playing _{title}_ {url}")
            await self.play_file(next_item, auto_disconnect=True)
            await message.clear_reaction("🎵")
            await message.add_reaction("✅")

    async def join(self, message):
        """
        Joins the requester's voice channel and starts continuous listening.

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

        # Start the ConversationManager in a separate thread
        if self.conversation_manager is None:
            self.conversation_manager = ConversationManager(
                tools=[
                    self.get_last_x_messages,
                    self.get_online_users,
                    self.get_bot_display_name,
                    self.get_users_in_voice_channel,
                ]
                + TOOLS
            )  # Pass the Firestore client
            self.conversation_thread = threading.Thread(
                target=self.conversation_manager.run
            )
            self.conversation_thread.daemon = True
            self.conversation_thread.start()
        else:
            await message.reply("Conversation Manager is already running!")

        # Create a thread to run the continuous recording loop
        self.listen_thread = threading.Thread(
            target=self.continuous_listen, args=(message.channel, message)
        )
        self.listen_thread.daemon = True
        self.listen_thread.start()
        await message.add_reaction("👂")

    async def stop(self, message):
        """
        Stops recording, disconnects from the voice channel, and provides feedback.

        Args:
            message (discord.Message): Discord message instance representing the stop command.
        """
        if self.listen_thread:
            self.listen_thread.join()

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

    async def once_done(self, sink: discord.sinks, channel: discord.TextChannel, *args):
        """
        Processes recorded audio data after a recording session ends.

        This method is triggered when a voice recording session completes. It iterates through the recorded audio data,
        transcribes each user's speech using OpenAI's Whisper API, tags the transcript with the username, and sends the
        tagged transcript for further processing and potential response generation.

        Args:
            sink (discord.sinks): The sink object containing recorded audio data.
            channel (discord.TextChannel): The text channel to send messages to.
            *args: Additional arguments, including the original message that triggered the recording.
        """
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
                    respond=config.CONTINUOUS_LISTEN_ACTIVATION_PHRASE
                    in tagged_transcript.lower(),
                    remember=True,
                    recall=True,
                    override_author_name=user_name,
                )
            else:
                print(f"User with ID {user_id} not found in the guild.")

    async def get_username_from_id(self, user_id, guild):
        """
        Retrieves the display name of a user from their ID within a guild.

        Args:
            user_id (int): The ID of the user.
            guild (discord.Guild): The Discord guild to search for the user.

        Returns:
            str or None: The user's display name if found, otherwise None.
        """
        try:
            user = await guild.fetch_member(user_id)
            if user:
                return user.display_name
        except Exception as e:
            print(f"Error fetching username for user ID {user_id}: {str(e)}")
        return None

    async def process_audio_stream(self, user_name, audio):
        """
        Processes an audio stream to transcribe speech using OpenAI's Whisper API.

        Args:
            user_name (str): The name of the user associated with the audio.
            audio (discord.AudioSink): The audio data to be transcribed.

        Returns:
            str: The transcribed text from the audio stream.
        """
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
        """
        Starts a voice recording session for a specified duration, then processes the audio.

        Args:
            message (discord.Message): The Discord message that triggered the listen command.
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

        self._voice_client.start_recording(
            discord.sinks.WaveSink(),  # The sink type to use.
            self.once_done,  # What to do once done.
            message.channel,  # The channel to disconnect from.
            message,  # The args to pass to the callback.
            filter=lambda m: m.author.id
            == message.author.id,  # Record only the requester
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
        Continuously records audio in intervals, processes it, and handles disconnections.

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
                        discord.sinks.WaveSink(), self.once_done, text_channel, message
                    )
                    self._is_recording = True

                time.sleep(config.CONTINUOUS_LISTEN_RECORDING_DURATION)

                if self._is_recording:
                    try:
                        if self.listen_thread:
                            self.listen_thread.join()  # Stop the continuous_listen thread
                    except:
                        pass
                    self._voice_client.stop_recording()
                    self._is_recording = False

                time.sleep(config.CONTINUOUS_LISTEN_PAUSE_DURATION)

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
        Processes a message, potentially generates a response, and optionally provides TTS output.

        Args:
            message (discord.Message): The Discord message to process.
            override_phrase (str, optional): If provided, use this phrase instead of the message content. Defaults to None.
            override_author_name (str, optional): If provided, use this author name. Defaults to None.
            respond (bool, optional): If True, generate a response using OpenAI. Defaults to True.
            remember (bool, optional): If True, add the message to conversation history. Defaults to True.
            recall (bool, optional): If True, include conversation history in the response request. Defaults to True.
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
        channel = discord.utils.get(self._guild.text_channels, name="𝚖𝚎𝚣𝚣𝚊𝚗𝚒𝚗𝚎")

        # Build message queue
        messages = [
            {
                "role": "system",
                "content": config.SYSTEM_PROMPT.format(
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
        messages.append(dict(role="user", content=f"**{author_name}:** {phrase}"))

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

    async def say(self, message):
        """
        Generates and plays TTS audio from a text message using OpenAI.

        Args:
            message (discord.Message): The message containing the text to convert to speech.
        """
        await message.add_reaction("🤔")

        try:
            await message.clear_reaction("🤔")
            await message.add_reaction("🗣️")
            await self.say_raw(message.content[len(COMMANDS_SAY) + 1 :])
            await message.clear_reaction("🗣️")
            await message.add_reaction("✅")
        except:
            await message.clear_reaction("🤔")
            await message.add_reaction("❌")
            print("Failed to generate TTS audio")

    async def say_raw(self, message):
        """
        Generates and plays TTS audio from raw text using OpenAI.

        Args:
            message (str): The text to convert to speech.
        """
        try:
            response = client.audio.speech.create(
                model=config.OPENAI_VOICE_MODEL,
                voice=config.OPENAI_TTS_VOICE,
                input=message,
            )

            response.stream_to_file("generated_audio/output.mp3")
            self._is_speaking = True
            await self.play_file(
                "generated_audio/output.mp3",
                tempo=1.0,
                auto_disconnect=False,
                auto_move_channel=False,
            )
            self._is_speaking = False
        except:
            print("Failed to generate TTS audio")

    async def play_file(
        self,
        source="generated_audio/output.mp3",
        tempo=1.0,
        auto_disconnect=True,
        auto_move_channel=True,
    ):
        """
        Plays an audio file in a voice channel.

        Args:
            source (str, optional): Path to the audio file. Defaults to "generated_audio/output.mp3".
            tempo (float, optional): Playback speed multiplier. Defaults to 1.0.
            auto_disconnect (bool, optional): Whether to disconnect after playback. Defaults to True.
            auto_move_channel (bool, optional): Whether to move to the default voice channel. Defaults to True.
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
        Downloads and queues audio from a YouTube video.

        Args:
            message (discord.Message): The message containing the YouTube URL or query.
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
        Clears a specified number of messages in the channel.

        Args:
            message (discord.Message): The Discord message that triggered the clear command.

        Returns:
            List[discord.Message]: A list of deleted messages.
        """
        channel = message.channel
        deleted = await channel.purge(limit=5, check=lambda x: True)
        return deleted

    async def view_queue(self, message):
        """
        Displays the current queue of audio tracks.

        Args:
            message (discord.Message): The Discord message that triggered the view queue command.
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

    @utils.function_info
    async def get_last_x_messages(channel_id: int, x: int):
        """
        Retrieves the last X messages from a specified text channel.

        :param channel_id: The ID of the Discord text channel.
        :type channel_id: int
        :param x: The number of last messages to retrieve.
        :type x: int
        :return: A dictionary where keys are sender display names and values are sender messages.
        :rtype: dict
        """
        channel = discord.utils.get(bot.get_all_channels(), id=channel_id)
        if channel is None:
            return {}

        messages = await channel.history(limit=x).flatten()
        message_dict = {message.author.name: message.content for message in messages}
        return message_dict

    @utils.function_info
    async def get_online_users(guild_id: int):
        """
        Gets a list of online users from the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: int
        :return: A list of display names of online users.
        :rtype: list
        """
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild is None:
            return []

        online_members = [
            member.display_name
            for member in guild.members
            if member.status == discord.Status.online
        ]
        return online_members

    @utils.function_info
    async def get_bot_display_name(guild_id: int):
        """
        Gets the display name of the bot in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: int
        :return: The bot's display name in the guild.
        :rtype: str
        """
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild is None:
            return "Bartender"

        bot_member = guild.get_member(bot.user.id)
        return bot_member.display_name if bot_member else "Bartender"

    @utils.function_info
    async def get_users_in_voice_channel(channel_id: int):
        """
        Gets a list of user display names in the specified voice channel.

        :param channel_id: The ID of the Discord voice channel.
        :type channel_id: int
        :return: A list of display names of users in the same voice channel, or None if the channel is not found.
        :rtype: list
        """
        channel = discord.utils.get(bot.get_all_channels(), id=channel_id)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            return None

        return [member.display_name for member in channel.members]

    async def on_ready(self):
        """Event handler that runs when the bot is ready."""
        print(f"Logged in as {self.user.name}")

    async def on_message(self, message):
        """
        Handles incoming messages and dispatches commands.

        Args:
            message (discord.Message): The incoming message.
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
        """
        Handles voice state updates, such as users joining or leaving voice channels.

        Args:
            member (discord.Member): The member whose voice state changed.
            before (discord.VoiceState): The voice state before the change.
            after (discord.VoiceState): The voice state after the change.
        """
        print(f"Voice state update: {member} {before} {after}")

    async def on_wavelink_node_ready(node: wavelink.Node):
        """
        Event handler for when a Wavelink node becomes ready.

        Args:
            node (wavelink.Node): The Wavelink node that is now ready.
        """
        print(f"{node.identifier} is ready")  # print a message


if __name__ == "__main__":
    bot = Bartender(command_prefix=COMMAND_PREFIX, intents=discord.Intents.all())
    bot.run(config.DISCORD_BOT_TOKEN)
