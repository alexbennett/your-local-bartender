import os
import asyncio
import time
import threading
import speech_recognition as sr
import json
import mafic
import yt_dlp as youtube_dl
import logging
import discord
from discord.ext import commands
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from ylb import config
from ylb import utils
from ylb.utils import TextColor
from ylb import openai_client as client

from ylb.helpers.openai import (
    openai_read_file_into_vector_store,
    openai_get_vector_store_file_ids,
    openai_update_assistant_vector_store,
    openai_update_assistant_code_interpreter,
)


COMMAND_PREFIX = "!"
COMMANDS_PLAY = "!play"
COMMANDS_JOIN = "!join"

r = sr.Recognizer()


class Bartender(commands.Bot):
    """
    Discord bot acting as an AI-powered assistant in voice channels.
    """

    def __init__(self, command_prefix, intents, extra_tools=None):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self._queue = []
        self._is_recording = False
        self._voice_client = None
        self._tools = [
            self.get_last_x_messages,
            self.get_online_users,
            self.get_bot_display_name,
            self.get_users_in_voice_channel,
        ] + extra_tools

        try:
            if config.OPENAI_ASSISTANT_ID:
                assistant = client.beta.assistants.retrieve(config.OPENAI_ASSISTANT_ID)
                client.beta.assistants.update(
                    assistant_id=assistant.id,
                    tools=[tool.info for tool in self._tools]
                    + [{"type": "file_search"}, {"type": "code_interpreter"}],
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [config.OPENAI_VECTOR_STORE_ID]
                        },
                        "code_interpreter": {
                            "file_ids": eval(openai_get_vector_store_file_ids())
                        },
                    },
                )
                print(f"Updated existing assistant ({assistant.id}) with latest tools.")
            else:
                assistant = client.beta.assistants.create(
                    name=config.OPENAI_ASSISTANT_NAME,
                    instructions=config.SYSTEM_PROMPT,
                    tools=[tool.info for tool in self._tools]
                    + [{"type": "file_search"}, {"type": "code_interpreter"}],
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [config.OPENAI_VECTOR_STORE_ID]
                        },
                        "code_interpreter": {
                            "file_ids": eval(openai_get_vector_store_file_ids())
                        },
                    },
                    model=config.OPENAI_MODEL,
                    temperature=config.OPENAI_MODEL_TEMPERATURE,
                )
                print(f"Created new assistant. Assistant ID: {assistant.id}")
                print(
                    "Please record this ID in your configuration and restart the program."
                )
                exit(1)
        except Exception as e:
            print(f"Failed to initialize assistant: {str(e)}")
            exit(1)

        self.pool = mafic.NodePool(self)
        self.listen_thread = None
        self.assistant_thread = None
        self.assistant = client.beta.assistants.retrieve(config.OPENAI_ASSISTANT_ID)
        self.current_thread = None
        self.text_logging_thread = None
        self.loop.create_task(self.add_nodes())

    async def add_nodes(self):
        """Asynchronously adds a node to the Mafic node pool."""
        await self.pool.create_node(
            host="127.0.0.1",
            port=2333,
            label="MAIN",
            password="*#kRzdk5u#P7",
        )

    async def on_ready(self):
        """Event handler that runs when the bot is ready."""
        print(f"Logged in as {self.user.name}")

    async def on_message(self, message):
        """
        Handles incoming messages and dispatches commands.

        Args:
            message (discord.Message): The incoming message.
        """
        if message.content.startswith(COMMANDS_PLAY):
            print("Handling PLAY")
            try:
                await self.play_youtube(message)
            except Exception as e:
                await message.add_reaction("❌")
                print(f"Unable to play YouTube video/audio: {e}")
        elif message.content.startswith(COMMANDS_JOIN):
            print("Handling JOIN")
            try:
                await self.join(message)
            except Exception as e:
                print(f"Error while listening in voice channel: {e}")
                if self._voice_client:
                    await self._voice_client.disconnect()

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

        # Check if a text logging thread already exists
        if self.text_logging_thread and not self.text_logging_thread.archived:
            await self.text_logging_thread.send(content=f"Joining voice channel: {channel.name}")
        else:
            # Create a new message thread in the voice channel for logging assistant responses
            self.text_logging_thread = await message.channel.create_thread(
            name=f"Assistant Log - {channel.name}",
            auto_archive_duration=60,
            )

        # Prepare the assistant's pre-prompt for the conversation
        users = ", ".join([member.display_name for member in channel.members])
        self.current_thread = client.beta.threads.create()
        start_prompt = (
            f"The assistant is now participating in a voice conversation in the Discord server '{message.guild.name}' "
            f"and voice channel '{channel.name}'. Users in the channel include: {users}. The conversation was started "
            f"by '{message.author.display_name}'."
        )
        # Start the conversation thread with the assistant
        client.beta.threads.messages.create(
            thread_id=self.current_thread.id, role="user", content=start_prompt
        )

        # Create a thread to run the continuous recording loop
        self.listen_thread = threading.Thread(
            target=self.continuous_listen, args=(message.channel,)
        )
        self.listen_thread.daemon = True
        self.listen_thread.start()
        await message.add_reaction("👂")

    def continuous_listen(self, text_channel):
        """
        Continuously records audio in intervals, processes it, and manages assistant responses.

        Args:
            text_channel (discord.TextChannel): Discord text channel to send messages.
        """
        while True:
            try:
                if not self._voice_client.is_connected():
                    print("Voice client is not connected, exiting continuous_listen")
                    break

                if not self._is_recording:
                    self._voice_client.start_recording(
                        discord.sinks.WaveSink(), self.once_done, text_channel
                    )
                    self._is_recording = True

                time.sleep(config.CONTINUOUS_LISTEN_RECORDING_DURATION)

                if self._is_recording:
                    self._voice_client.stop_recording()
                    self._is_recording = False

                time.sleep(config.CONTINUOUS_LISTEN_PAUSE_DURATION)

            except Exception as e:
                print(f"Error in continuous_listen: {str(e)}")

    async def once_done(self, sink: discord.sinks, channel: discord.TextChannel, *args):
        """
        Processes recorded audio data after a recording session ends.

        This method is triggered when a voice recording session completes. It transcribes each user's speech,
        adds the transcription to the assistant thread, and plays back the assistant's response.

        Args:
            sink (discord.sinks): The sink object containing recorded audio data.
            channel (discord.TextChannel): The text channel to send messages to.
        """
        # Check if any users were recorded
        if not sink.audio_data:
            print("No users were recorded, looping again...")
            return

        for user_id, audio in sink.audio_data.items():
            user_name = await self.get_username_from_id(user_id, channel.guild)
            if user_name:
                transcript = await self.process_audio_stream(user_name, audio)

                # Log the transcript the text logging thread
                if self.text_logging_thread:
                    await self.text_logging_thread.send(content=transcript)

                # Add the transcript as a message to the assistant thread
                client.beta.threads.messages.create(
                    thread_id=self.current_thread.id, role="user", content=transcript
                )

                # Poll the assistant for a response
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=self.current_thread.id,
                    assistant_id=self.assistant.id,
                    instructions=config.INSTRUCTION_PROMPT,
                    temperature=config.OPENAI_MODEL_TEMPERATURE,
                )

                while True:
                    time.sleep(0.01)
                    run = client.beta.threads.runs.retrieve(
                        thread_id=self.current_thread.id, run_id=run.id
                    )
                    if run.status == "completed":
                        messages = client.beta.threads.messages.list(
                            thread_id=self.current_thread.id,
                            limit=1,
                        )
                        for message in messages:
                            if message.role == "assistant":
                                try:
                                    print(
                                        f"\n{TextColor.BOLD}{TextColor.OKGREEN}{TextColor.BOLD}[💭] {message.content[0].text.value}{TextColor.ENDC}\n"
                                    )
                                    await self.say_and_log(
                                        message.content[0].text.value
                                    )
                                except Exception:
                                    print(
                                        "Failed to print assistant message: %s", message
                                    )
                                break
                        print(f"Run {run.id} completed")
                        break
                    elif run.status == "requires_action":
                        print(
                            f"Required action in run {run.id} / thread {run.thread_id} / assistant {run.assistant_id}"
                        )
                        self.handle_requires_action(run, run.id)
                    elif run.status == "failed":
                        print(
                            f"Run {run.id} failed with error: {run.last_error.code} -> {run.last_error.message}"
                        )
                        break
                    else:
                        pass
            else:
                print(f"User with ID {user_id} not found in the guild.")

    def handle_requires_action(self, data, run_id):
        """
        Handle the required action when function calls are needed by submitting tool outputs.
        """
        tool_outputs = []
        if hasattr(data.required_action.submit_tool_outputs, "tool_calls"):
            tool_calls = data.required_action.submit_tool_outputs.tool_calls
            with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                future_to_tool_call = {
                    executor.submit(
                        self.fetch_tool_output,
                        tool_call.function.name,
                        json.loads(tool_call.function.arguments),
                    ): tool_call.id
                    for tool_call in tool_calls
                }
                for future in as_completed(future_to_tool_call):
                    tool_call_id = future_to_tool_call[future]
                    try:
                        output = future.result()
                        tool_outputs.append(
                            {"tool_call_id": tool_call_id, "output": output}
                        )
                    except Exception as e:
                        logging.error(
                            f"Error during tool call {tool_call_id}: {str(e)}\n{traceback.format_exc()}"
                        )
                        tool_outputs.append(
                            {
                                "tool_call_id": tool_call_id,
                                "output": f"Error during tool call: {str(e)}\n{traceback.format_exc()}",
                            }
                        )
        else:
            logging.info("No tool calls found in the required action.")

        client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.current_thread.id, run_id=run_id, tool_outputs=tool_outputs
        )

    def fetch_tool_output(self, function_name, arguments):
        """
        Simulates fetching outputs for function calls.

        Parameters:
        - function_name (str): The name of the function to call.
        - arguments (str): The arguments to pass to the function as a JSON string.

        Returns:
        - The response from the function call.
        """
        logging.warning(
            f"Processing tool call...\n{TextColor.HEADER}{function_name}({json.dumps(arguments, indent=2)}){TextColor.ENDC}"
        )
        for tool in self._tools:
            if tool.info["function"]["name"] == function_name:
                try:
                    function_response = tool(**arguments)
                    return str(function_response)
                except Exception as e:
                    logging.error(
                        f"Error during tool call: {str(e)}\n{traceback.format_exc()}"
                    )
                    return f"Error during tool call: {str(e)}\n{traceback.format_exc()}"
        logging.error(f"Tool function '{function_name}' not found.")
        return f"Error: Tool function '{function_name}' not found."

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
            model=config.OPENAI_VOICE_MODEL, file=audio_file, response_format="text"
        )
        print(f"[{user_name}]: {transcript}")
        return f"{user_name}: {transcript}"

    async def say_and_log(self, message):
        """
        Plays the assistant's response in the voice channel and logs it to the text thread.

        Args:
            message (str): The assistant's response text.
        """
        try:
            filename = "generated_audio/output.mp3"
            response = client.audio.speech.create(
                model=config.OPENAI_TTS_MODEL,
                voice=config.OPENAI_TTS_VOICE,
                input=message,
            )
            # response.stream_to_file(filename)
            response.write_to_file(filename)
            if os.name == "nt":
                audio = discord.FFmpegPCMAudio(
                    executable="c:/ffmpeg/bin/ffmpeg.exe",
                    source=filename,
                    options=f'-af "atempo={tempo}" -v "quiet"',
                )
            elif os.name == "posix":
                audio = discord.FFmpegPCMAudio(
                    executable="ffmpeg", source=filename, options=f'-af "atempo=1.0" -v "quiet"'
                )

            # Play the audio file using FFmpeg
            self._voice_client.play(audio)

            # Wait for playback to finish
            while self._voice_client.is_playing():
                await asyncio.sleep(1)

            # Log the assistant's response in the text logging thread
            if self.text_logging_thread:
                await self.text_logging_thread.send(content=message)
        except Exception as e:
            print(f"Failed to generate TTS audio: {e}")

    @utils.function_info
    async def get_last_x_messages(channel_id: int, x: int):
        """Retrieves the last X messages from a specified text channel.

        :param channel_id: The ID of the Discord text channel.
        :type channel_id: integer
        :param x: The number of last messages to retrieve.
        :type x: integer
        :return: A dictionary where keys are sender display names and values are sender messages.
        :rtype: dictionary
        """
        channel = discord.utils.get(bot.get_all_channels(), id=channel_id)
        if channel is None:
            return {}

        messages = await channel.history(limit=x).flatten()
        message_dict = {message.author.name: message.content for message in messages}
        return message_dict

    @utils.function_info
    async def get_online_users(guild_id: int):
        """Gets a list of online users from the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
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
        """Gets the display name of the bot in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :return: The bot's display name in the guild.
        :rtype: string
        """
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild is None:
            return "Bartender"

        bot_member = guild.get_member(bot.user.id)
        return bot_member.display_name if bot_member else "Bartender"

    @utils.function_info
    async def get_users_in_voice_channel(channel_id: int):
        """Gets a list of user display names in the specified voice channel.

        :param channel_id: The ID of the Discord voice channel.
        :type channel_id: integer
        :return: A list of display names of users in the same voice channel, or None if the channel is not found.
        :rtype: list
        """
        channel = discord.utils.get(bot.get_all_channels(), id=channel_id)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            return None

        return [member.display_name for member in channel.members]

    async def play_youtube(self, message):
        """
        Downloads and queues audio from a YouTube video.

        Args:
            message (discord.Message): The message containing the YouTube URL or query.
        """
        url_or_query = message.content[len(COMMANDS_PLAY) + 1 :].strip()
        await message.add_reaction("🔍")

        with youtube_dl.YoutubeDL(
            {"default_search": "ytsearch1:", "quiet": True}
        ) as ydl:
            info = ydl.extract_info(url_or_query, download=False)
            url = info["entries"][0]["webpage_url"]
            title = info["entries"][0]["title"]

        filename = f"downloaded_songs/{title}"
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
        self._queue.append((message, title, url, filename + ".mp3"))

        if not self._voice_client or not self._voice_client.is_connected():
            await self.play_next_in_queue()
        else:
            await message.reply(f"_{title}_ ({url}) added to queue...")

    async def play_next_in_queue(self):
        """Plays the next item in the queue and manages reactions."""
        if self._queue:
            message, title, url, next_item = self._queue.pop(0)
            await message.add_reaction("🎵")
            await message.reply(f"Now playing _{title}_ {url}")
            await self.play_file(next_item)
            await message.clear_reaction("🎵")
            await message.add_reaction("✅")

    async def play_file(self, source):
        """Plays an audio file in a voice channel."""
        audio = discord.FFmpegPCMAudio(source)
        self._voice_client.play(audio)

        while self._voice_client.is_playing():
            await asyncio.sleep(1)


if __name__ == "__main__":
    extra_tools = [
        openai_get_vector_store_file_ids,
        openai_read_file_into_vector_store,
        openai_update_assistant_code_interpreter,
        openai_update_assistant_vector_store,
    ]

    intents = discord.Intents.default()
    intents.message_content = True
    bot = Bartender(
        command_prefix=COMMAND_PREFIX, intents=intents, extra_tools=extra_tools
    )
    bot.run(config.DISCORD_BOT_TOKEN)
