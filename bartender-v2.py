import os
import asyncio
import time
import threading
import speech_recognition as sr
import inspect
import json
import logging
import discord
import datetime
from discord.ext import commands
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from google.cloud import firestore
from pydub import AudioSegment
from typing import List, Tuple

from ylb import config
from ylb import utils
from ylb.utils import TextColor
from ylb.helpers.audio import has_speech
from ylb.helpers.rswiki import (
    search_osrs_wiki,
    search_osrs_item_value,
    search_rs3_wiki,
    search_rs3_item_value
)
from ylb.helpers.openai import (
    openai_read_file_into_vector_store,
    openai_get_vector_store_file_ids,
    openai_update_assistant_vector_store,
    openai_update_assistant_code_interpreter,
)

from ylb import openai_client as client

# General program information
name = "Your Local Bartender"
description = "An AI-powered assistant for Discord."
authors = "Alex Bennett <alex@b16.dev>"
__email__ = "alex@b16.dev"
__version__ = config.VERSION
__copyright__ = "(c) Copyright 2024, B16 LLC"
__status__ = "development"


COMMAND_PREFIX = "!"
COMMANDS_JOIN = "!join"

r = sr.Recognizer()

# Initialize Firestore
db = firestore.Client()

class Bartender(commands.Bot):
    """
    Discord bot acting as an AI-powered assistant in voice channels.
    """

    def __init__(self, command_prefix, intents, extra_tools=None):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self._queue = []
        self._is_recording = False
        self._is_speaking = False
        self._voice_client = None
        self._tools = [
            self.get_guild_online_users,
            self.get_guild_bot_display_name,
            self.get_users_in_voice_channel,
            self.get_guild_text_channels,
            self.get_guild_voice_channels,
            self.update_bot_display_name,
            self.send_message_to_channel,
            self.send_reply_to_message,
            self.send_message_reaction,
            self.remove_message_reaction,
            self.speak,
            self.join_voice_channel,
            self.leave_voice_channel,
            self.move_user_to_voice_channel,
            self.mute_user,
            self.unmute_user,
            self.get_user_voice_state,
            self.get_guild_users,
            self.create_text_channel,
            self.delete_text_channel,
            self.create_voice_channel,
            self.delete_voice_channel,
        ] + extra_tools

        try:
            if config.OPENAI_ASSISTANT_ID:
                assistant = client.beta.assistants.retrieve(config.OPENAI_ASSISTANT_ID)
                client.beta.assistants.update(
                    assistant_id=assistant.id,
                    instructions=config.SYSTEM_PROMPT.format(name=config.OPENAI_ASSISTANT_NAME),
                    tools=[tool.info for tool in self._tools]
                    + [{"type": "file_search"}, {"type": "code_interpreter"}],
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [config.OPENAI_VECTOR_STORE_ID]
                        },
                        "code_interpreter": {
                            "file_ids": openai_get_vector_store_file_ids()
                        },
                    },
                )
                logging.info(f"Updated existing assistant ({assistant.id}) with latest tools.")
            else:
                assistant = client.beta.assistants.create(
                    name=config.OPENAI_ASSISTANT_NAME,
                    instructions=config.SYSTEM_PROMPT.format(name=config.OPENAI_ASSISTANT_NAME),
                    tools=[tool.info for tool in self._tools]
                    + [{"type": "file_search"}, {"type": "code_interpreter"}],
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [config.OPENAI_VECTOR_STORE_ID]
                        },
                        "code_interpreter": {
                            "file_ids": openai_get_vector_store_file_ids()
                        },
                    },
                    model=config.OPENAI_MODEL,
                    temperature=config.OPENAI_MODEL_TEMPERATURE,
                )
                logging.info(f"Created new assistant. Assistant ID: {assistant.id}")
                logging.info(
                    "Please record this ID in your configuration and restart the program."
                )
                exit(1)
        except Exception as e:
            logging.error(f"Failed to initialize assistant: {str(e)}{traceback.format_exc()}")
            exit(1)

        self.listen_task = None
        self.assistant_thread = None
        self.assistant = client.beta.assistants.retrieve(config.OPENAI_ASSISTANT_ID)
        self.current_thread = None
        self.session_doc_ref = None
        self.transcript_buffer = []
        self._speak_lock = asyncio.Lock()

    def task_exception_handler(self, task):
        try:
            task.result()
        except Exception as e:
            logging.error(f"Task raised an exception: {e}")

    async def close(self):
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.disconnect()
        await super().close()
        
    async def on_ready(self):
        """Event handler that runs when the bot is ready."""
        logging.info(f"{TextColor.HEADER}Logged in as {self.user.name} (ID: {self.user.id}){TextColor.ENDC}")
        logging.info(f"{TextColor.OKCYAN}Connected to the following communities:{TextColor.ENDC}")
        for guild in self.guilds:
            logging.info(
                f" - {TextColor.OKGREEN}{guild.name}{TextColor.ENDC} "
                f"(ID: {guild.id}) | Members: {guild.member_count}"
            )
            await self.store_guild_info(guild)

    async def store_guild_info(self, guild):
        """Stores guild information in Firestore."""
        users = [member.id for member in guild.members]
        doc_ref = db.collection("instances").document(str(guild.id))
        doc_ref.set(
            {
                "guild_id": str(guild.id),
                "server_name": guild.name,
                "users": users,
            }
        )

    async def on_message(self, message):
        """
        Handles incoming messages and dispatches commands.

        Args:
            message (discord.Message): The incoming message.
        """
        if config.CONTINUOUS_LISTEN_ACTIVATION_PHRASE in message.content.lower():
            if message.author == self.user:
                return
            if message.author.bot:
                return

            try:
                if self._voice_client and self._voice_client.is_connected():
                    logging.info(f"Adding text message to current thread: \"{message.content}\"")
                    # Add the message to the current thread
                    client.beta.threads.messages.create(
                        thread_id=self.current_thread.id, role="user", content=message.content
                    )
                else:
                    # Perform a one-time chat completion
                    completion = client.chat.completions.create(
                        model=config.OPENAI_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": config.SYSTEM_PROMPT.format(name=config.OPENAI_ASSISTANT_NAME),
                            },
                            {
                                "role": "user",
                                "content": message.content,
                            },
                        ],
                        temperature=config.OPENAI_MODEL_TEMPERATURE,
                    )

                    # Extract the assistant's response
                    response = completion.choices[0].message.content

                    # Send the response back to the channel
                    await message.reply(response)

            except Exception as e:
                # Handle any errors during the API call
                logging.error(f"Error generating chat completion: {e}")
                await message.reply("Sorry, I couldn't generate a response due to an error.")

        elif message.content.startswith(COMMANDS_JOIN):
            logging.info(f"Received join command from {message.author.display_name}")
            try:
                await self.join(message)
            except Exception as e:
                logging.error(
                    f"Error while listening in voice channel: {e}{traceback.format_exc()}"
                )
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

        # Create a new thread for the assistant
        self.current_thread = client.beta.threads.create()

        # Prepare the assistant's pre-prompt for the conversation
        start_prompt = (
            f"You are now participating in a voice conversation in the Discord server '{message.guild.name}' (id: {message.guild.id}) "
            f"and voice channel '{channel.name}' (id: {channel.id}). The conversation was started by '{message.author.display_name}'. You will receive messages in chunks. Messages are stored by the program until your name ({config.OPENAI_ASSISTANT_NAME}) is mentioned. All messages stored up to that point are then sent to you for processing. You should consider the messages in the order received. Each message includes a timestamp, the name and id of the speaker, and the message content. Respond with the speak tool."
        )

        # Start the conversation thread with the assistant
        client.beta.threads.messages.create(
            thread_id=self.current_thread.id, role="user", content=start_prompt
        )

        # Create a new Firestore document for the session
        self.session_doc_ref = db.collection("sessions").document()
        self.session_doc_ref.set(
            {
                "id": self.session_doc_ref.id,
                "openai_assistant_id": config.OPENAI_ASSISTANT_ID,
                "discord_guild_id": message.guild.id,
                "discord_message_id": message.id,
                "openai_thread_id": self.current_thread.id,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "instruction_prompt": config.INSTRUCTION_PROMPT,
                "start_prompt": start_prompt,
                "temperature": config.OPENAI_MODEL_TEMPERATURE,
            }
        )

        # Start the continuous recording loop
        self.listen_task = asyncio.create_task(self.continuous_listen(message.channel))
        self.listen_task.add_done_callback(self.task_exception_handler)

        await message.add_reaction("✅")

    async def continuous_listen(self, text_channel):
        """
        Continuously records audio in intervals, processes it, and manages assistant responses.

        Args:
            text_channel (discord.TextChannel): Discord text channel to send messages.
        """
        while True:
            try:
                if not self._voice_client.is_connected():
                    logging.warning(
                        "Voice client is not connected, exiting continuous_listen"
                    )
                    break

                if not self._is_recording:
                    self._voice_client.start_recording(
                        discord.sinks.WaveSink(), self.once_done, text_channel
                    )
                    self._is_recording = True

                await asyncio.sleep(config.CONTINUOUS_LISTEN_RECORDING_DURATION)

                if self._is_recording:
                    self._voice_client.stop_recording()
                    self._is_recording = False

                await asyncio.sleep(config.CONTINUOUS_LISTEN_PAUSE_DURATION)

            except Exception as e:
                logging.error(f"Error in continuous_listen: {str(e)}")

    async def once_done(self, sink: discord.sinks, channel: discord.TextChannel):
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
            return

        self.transcript_buffer = []

        start_time = time.time()

        for user_id, audio in sink.audio_data.items():
            user_nick = await self.get_username_from_id(user_id, channel.guild)
            if user_nick:
                raw_transcript = await self.transcribe_audio_stream(user_id, audio)

                if not raw_transcript:
                    continue

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tagged_transcript = f"[{timestamp}] [{user_nick} (id: {user_id})] {raw_transcript}"

                logging.info(f"{TextColor.OKGREEN}{tagged_transcript}{TextColor.ENDC}")

                self.transcript_buffer.append(tagged_transcript)

                # Check if the activation phrase is in the transcript
                if config.CONTINUOUS_LISTEN_ACTIVATION_PHRASE.lower() in raw_transcript.lower():
                    # Combine all transcripts in the buffer
                    combined_transcript = "\n".join(self.transcript_buffer)
                    self.transcript_buffer.clear()

                    # Add the combined transcript as a message to the assistant thread
                    msg = client.beta.threads.messages.create(
                        thread_id=self.current_thread.id, role="user", content=combined_transcript
                    )

                    # Store the message in the Firestore subcollection
                    self.session_doc_ref.collection("messages").add(
                        {
                            "openai_thread_id": self.current_thread.id,
                            "openai_message_id": msg.id,
                            "discord_user_id": user_id,
                            "content": combined_transcript,
                            "timestamp": firestore.SERVER_TIMESTAMP,
                            "tool_call": None,
                        }
                    )

                    # Poll the assistant for a response
                    run = client.beta.threads.runs.create_and_poll(
                        thread_id=self.current_thread.id,
                        assistant_id=self.assistant.id,
                        instructions=config.INSTRUCTION_PROMPT,
                        temperature=config.OPENAI_MODEL_TEMPERATURE,
                    )

                    while True:
                        run = client.beta.threads.runs.retrieve(
                            thread_id=self.current_thread.id, run_id=run.id
                        )
                        if run.status == "completed":
                            messages = client.beta.threads.messages.list(
                                thread_id=self.current_thread.id, limit=1
                            )
                            for message in messages:
                                if message.role == "assistant":
                                    try:
                                        assistant_message = message.content[0].text.value
                                        logging.info(
                                            f"{TextColor.BOLD}{TextColor.GRAY}[{config.OPENAI_ASSISTANT_NAME} 💭] {assistant_message}{TextColor.ENDC}\n"
                                        )
                                        if config.ENABLE_THOUGHT_MESSAGES:
                                            await channel.send(f"💭 {assistant_message}")

                                        # Store the assistant message in the Firestore subcollection
                                        self.session_doc_ref.collection("messages").add(
                                            {
                                                "openai_thread_id": self.current_thread.id,
                                                "openai_message_id": message.id,
                                                "content": message.content[0].text.value,
                                                "timestamp": firestore.SERVER_TIMESTAMP,
                                                "tool_call": None,
                                            }
                                        )
                                        break
                                    except Exception:
                                        logging.error(
                                            "Failed to print assistant message: %s",
                                            message,
                                        )
                                        logging.error(traceback.format_exc())
                            logging.info(f"Run {run.id} completed")
                            break
                        elif run.status == "requires_action":
                            logging.info(
                                f"Required action in {run.id} → {run.thread_id}"
                            )
                            await self.handle_requires_action(run, run.id)
                        elif run.status == "failed":
                            logging.error(
                                f"Run {run.id} failed with error: {run.last_error.code} -> {run.last_error.message}"
                            )
                            break
                        else:
                            pass
                        await asyncio.sleep(0.1)
            logging.info(f"Processed {len(sink.audio_data)} audio streams in {time.time() - start_time:.2f} seconds")

    async def handle_requires_action(self, data, run_id):
        """
        Handle the required action when function calls are needed by submitting tool outputs.
        """
        tool_outputs = []
        if hasattr(data.required_action.submit_tool_outputs, "tool_calls"):
            tool_calls = data.required_action.submit_tool_outputs.tool_calls
            tasks = [
                self.fetch_tool_output(
                    tool_call.function.name, json.loads(tool_call.function.arguments)
                )
                for tool_call in tool_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for tool_call, result in zip(tool_calls, results):
                tool_call_id = tool_call.id
                fname = tool_call.function.name
                fargs = tool_call.function.arguments
                if isinstance(result, Exception):
                    logging.error(
                        f"Error during tool call {tool_call_id}: {str(result)}"
                    )
                    output = f"Error during tool call: {str(result)}"
                else:
                    output = result

                tool_outputs.append(
                    {"tool_call_id": tool_call_id, "output": output}
                )

                # Store the tool call in the Firestore subcollection
                self.session_doc_ref.collection("messages").add(
                    {
                        "openai_thread_id": self.current_thread.id,
                        "openai_message_id": None,
                        "content": None,
                        "timestamp": firestore.SERVER_TIMESTAMP,
                        "tool_call": {
                            "tool_call_id": tool_call_id,
                            "function_name": fname,
                            "arguments": json.loads(fargs),
                            "output": output,
                        },
                    }
                )
                logging.info(
                    f"Tool call completed -> {TextColor.HEADER}{tool_call.function.name}(){TextColor.ENDC}"
                )
        else:
            logging.info("No tool calls found in the required action.")

        client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.current_thread.id, run_id=run_id, tool_outputs=tool_outputs
        )

    async def fetch_tool_output(self, function_name, arguments):
        """
        Fetches outputs for function calls, handling both async and sync functions.

        Parameters:
        - function_name (str): The name of the function to call.
        - arguments (dict): The arguments to pass to the function.

        Returns:
        - The response from the function call.
        """
        logging.info(
            f"Processing tool call -> {TextColor.HEADER}{function_name}({json.dumps(arguments, indent=2)}){TextColor.ENDC}"
        )
        for tool in self._tools:
            if tool.info["function"]["name"] == function_name:
                try:
                    # Check if the tool function is a member of self
                    if hasattr(self, tool.func.__name__):
                        # Check if the tool function is async
                        if inspect.iscoroutinefunction(tool.func):
                            function_response = await tool(self, **arguments)
                        else:
                            # If sync, call directly
                            function_response = tool(self, **arguments)
                    else:
                        # If the function is not a member of self, call without self
                        if inspect.iscoroutinefunction(tool.func):
                            function_response = await tool(**arguments)
                        else:
                            function_response = tool(**arguments)
                    return str(function_response)
                except Exception as e:
                    logging.warning(
                        f"Error during tool call: {str(e)}\n{traceback.format_exc()}"
                    )
                    return f"Error during tool call: {str(e)}\n{traceback.format_exc()}"
        logging.warning(f"Tool function '{function_name}' not found.")
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
            logging.info(f"Error fetching username for user ID {user_id}: {str(e)}")
        return None
    
    async def get_nick_from_id(self, user_id, guild):
        """
        Retrieves the nickname of a user from their ID within a guild.

        Args:
            user_id (int): The ID of the user.
            guild (discord.Guild): The Discord guild to search for the user.

        Returns:
            str or None: The user's nickname if found, otherwise None.
        """
        try:
            user = await guild.fetch_member(user_id)
            if user:
                return user.nick
        except Exception as e:
            logging.info(f"Error fetching nickname for user ID {user_id}: {str(e)}")
        return None

    async def transcribe_audio_stream(self, user_id, audio):
        """
        Processes an audio stream to transcribe speech using OpenAI's Whisper API.

        Args:
            user_id (str): The ID of the user associated with the audio.
            audio (discord.AudioSink): The audio data to be transcribed.

        Returns:
            str: The transcribed text from the audio stream.
        """
        filename = f"generated_audio/request-{user_id}.wav"
        
        # Output the audio data to a WAV file
        with open(filename, "wb") as f:
            f.write(audio.file.getbuffer())
        
        # Convert the audio file to correct WAV format
        audio_file = open(filename, "rb")
        sound = AudioSegment.from_file(audio_file)
        sound.export(filename, format="wav")
        
        if not has_speech(filename):
            return ""

        transcript = client.audio.transcriptions.create(
            model=config.OPENAI_VOICE_MODEL, file=audio_file, response_format="text"
        )

        return str(transcript)

    @utils.function_info
    async def speak(self, message):
        """
        Use TTS to play a spoken message in the voice channel.

        :param message: The text to be spoken.
        :type message: string
        :return: The spoken message.
        :rtype: string
        """
        try:
            filename = "generated_audio/output.mp3"
            async with self._speak_lock:
                response = client.audio.speech.create(
                    model=config.OPENAI_TTS_MODEL,
                    voice=config.OPENAI_TTS_VOICE,
                    input=message,
                    speed=1.0
                )
                # response.stream_to_file(filename)
                response.write_to_file(filename)
                if os.name == "nt":
                    audio = discord.FFmpegPCMAudio(
                        executable="c:/ffmpeg/bin/ffmpeg.exe",
                        source=filename,
                        options=f'-af "atempo=1.0" -v "quiet"',
                    )
                elif os.name == "posix":
                    audio = discord.FFmpegPCMAudio(
                        executable="ffmpeg",
                        source=filename,
                        options=f'-af "atempo=1.1" -v "quiet"',
                    )
                # Play the audio file using FFmpeg
                self._voice_client.play(audio)

                # Wait for playback to finish
                while self._voice_client.is_playing():
                    await asyncio.sleep(1)
        except Exception as e:
            logging.warning(f"Failed to generate TTS audio: {e}")
            logging.warning(traceback.format_exc())
            return f"Failed to speak: {e}"

    @utils.function_info
    def get_guild_online_users(self, guild_id: int):
        """Gets a list of online users from the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :return: A list of display names of online users.
        :rtype: list
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return []

        online_members = [
            member.display_name
            for member in guild.members
            if member.status == discord.Status.online
        ]
        return online_members

    @utils.function_info
    def get_guild_text_channels(self, guild_id: int):
        """Gets a list of text channels in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :return: A list of dictionaries containing the id and name of each text channel.
        :rtype: list
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return []

        text_channels = [
            {"id": channel.id, "name": channel.name}
            for channel in guild.text_channels
        ]
        return text_channels

    @utils.function_info
    def get_guild_voice_channels(self, guild_id: int):
        """Gets a list of voice channels in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :return: A list of dictionaries containing the id and name of each voice channel.
        :rtype: list
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return []

        voice_channels = [
            {"id": channel.id, "name": channel.name}
            for channel in guild.voice_channels
        ]
        return voice_channels

    @utils.function_info
    def get_guild_bot_display_name(self, guild_id: int):
        """Gets the display name of the bot in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :return: The bot's display name in the guild.
        :rtype: string
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return "Bartender"

        bot_member = guild.get_member(self.user.id)
        return bot_member.display_name if bot_member else "Bartender"

    @utils.function_info
    def get_users_in_voice_channel(self, channel_id: int):
        """Gets a list of user display names in the specified voice channel.

        :param channel_id: The ID of the Discord voice channel.
        :type channel_id: integer
        :return: A list of display names of users in the same voice channel, or None if the channel is not found.
        :rtype: string
        """
        channel = discord.utils.get(self.get_all_channels(), id=channel_id)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            return None

        return [member.display_name for member in channel.members]

    @utils.function_info
    async def update_bot_display_name(self, guild_id: int, new_name: str):
        """Updates the bot's display name in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param new_name: The new display name for the bot.
        :type new_name: string
        :return: The new display name of the bot in the guild.
        :rtype: string
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return config.OPENAI_ASSISTANT_NAME

        try:
            bot_member = guild.get_member(self.user.id)
            if bot_member:
                await bot_member.edit(nick=new_name)
                return f"Updated bot display name to {new_name}."
            else:
                return "Bot not found in the guild."
        except discord.HTTPException as e:
            logging.error(f"Error updating bot display name: {e}")
            return f"Error updating bot display name: {e}"

    @utils.function_info
    async def send_message_to_channel(self, channel_id: int, message: str):
        """Sends a message to the specified channel.

        :param channel_id: The ID of the Discord channel.
        :type channel_id: integer
        :param message: The message to be sent.
        :type message: string
        :return: The sent message object.
        :rtype: string
        """
        channel = discord.utils.get(self.get_all_channels(), id=channel_id)
        if channel is None:
            return f"Channel with ID {channel_id} not found."

        try:
            await channel.send(message)
            return "Message sent successfully."
        except discord.HTTPException as e:
            logging.error(f"Error sending message: {e}")
            return f"Error sending message."

    @utils.function_info
    async def send_reply_to_message(self, message_id: int, reply: str):
        """Sends a reply to the specified message.

        :param message_id: The ID of the message to reply to.
        :type message_id: integer
        :param reply: The reply message.
        :type reply: string
        :return: The sent reply message object.
        :rtype: string
        """
        message = await self.get_message(message_id)
        if message is None:
            return f"Message with ID {message_id} not found."

        try:
            await message.reply(reply)
            return "Reply sent successfully."
        except discord.HTTPException as e:
            logging.error(f"Error sending reply message: {e}")
            return f"Error sending reply message."

    @utils.function_info
    async def send_message_reaction(self, message_id: int, reaction: str):
        """Adds a reaction to the specified message.

        :param message_id: The ID of the message to add the reaction to.
        :type message_id: integer
        :param reaction: The reaction emoji.
        :type reaction: string
        :return: Whether the reaction was added successfully.
        :rtype: boolean
        """
        message = await self.get_message(message_id)
        if message is None:
            return f"Message with ID {message_id} not found."

        try:
            await message.add_reaction(reaction)
            return "Reaction added successfully."
        except discord.HTTPException as e:
            logging.error(f"Error adding reaction: {e}")
            return "Error adding reaction."
        
    @utils.function_info
    async def remove_message_reaction(self, message_id: int, reaction: str):
        """Removes a reaction from the specified message.

        :param message_id: The ID of the message to remove the reaction from.
        :type message_id: integer
        :param reaction: The reaction emoji.
        :type reaction: string
        :return: Whether the reaction was removed successfully.
        :rtype: boolean
        """
        message = await self.get_message(message_id)
        if message is None:
            return f"Message with ID {message_id} not found."

        try:
            await message.remove_reaction(reaction, self.user)
            return "Reaction removed successfully."
        except discord.HTTPException as e:
            logging.error(f"Error removing reaction: {e}")
            return "Error removing reaction."

    @utils.function_info
    async def join_voice_channel(self, channel_id: int):
        """Joins the specified voice channel.

        :param channel_id: The ID of the voice channel to join.
        :type channel_id: integer
        :return: Whether the bot successfully joined the channel.
        :rtype: boolean
        """
        channel = discord.utils.get(self.get_all_channels(), id=channel_id)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            return f"Voice channel with ID {channel_id} not found."

        try:
            self._voice_client = await channel.connect()
            return f"Successfully joined voice channel {channel.name}."
        except discord.HTTPException as e:
            logging.error(f"Error joining voice channel: {e}")
            return f"Error joining voice channel."

    @utils.function_info
    async def leave_voice_channel(self):
        """Leaves the current voice channel.

        :return: Whether the bot successfully left the channel.
        :rtype: boolean
        """
        if self._voice_client and self._voice_client.is_connected():
            try:
                await self._voice_client.disconnect()
                return f"Successfully left voice channel."
            except discord.HTTPException as e:
                logging.error(f"Error leaving voice channel: {e}")
                return f"Error leaving voice channel."
        else:
            return "Bot is not connected to a voice channel."
        
    @utils.function_info
    async def move_user_to_voice_channel(self, user_id: int, channel_id: int):
        """Moves a user to the specified voice channel.

        :param user_id: The ID of the user to move.
        :type user_id: integer
        :param channel_id: The ID of the voice channel to move the user to.
        :type channel_id: integer
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        if not self._voice_client or not self._voice_client.is_connected():
            return "Bot is not connected to any voice channel."

        guild = self._voice_client.guild
        member = guild.get_member(user_id)
        if member is None:
            return f"User with ID {user_id} not found."

        channel = discord.utils.get(guild.voice_channels, id=channel_id)
        if channel is None:
            return f"Voice channel with ID {channel_id} not found."

        try:
            await member.move_to(channel)
            return f"Successfully moved user {member.display_name} to voice channel {channel.name}."
        except discord.HTTPException as e:
            logging.error(f"Error moving user to voice channel: {e}")
            return f"Error moving user to voice channel."

    @utils.function_info
    async def mute_user(self, guild_id: int, user_id: int):
        """Mutes the specified user in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param user_id: The ID of the user to mute.
        :type user_id: integer
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return f"Guild with ID {guild_id} not found."

        member = guild.get_member(user_id)
        if member is None:
            return f"User with ID {user_id} not found."

        try:
            await member.edit(mute=True)
            return f"Successfully muted user {member.display_name}."
        except discord.HTTPException as e:
            logging.error(f"Error muting user: {e}")
            return f"Error muting user."
        
    @utils.function_info
    async def unmute_user(self, guild_id: int, user_id: int):
        """Unmutes the specified user in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param user_id: The ID of the user to unmute.
        :type user_id: integer
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return f"Guild with ID {guild_id} not found."

        member = guild.get_member(user_id)
        if member is None:
            return f"User with ID {user_id} not found."

        try:
            await member.edit(mute=False)
            return f"Successfully unmuted user {member.display_name}."
        except discord.HTTPException as e:
            logging.error(f"Error unmuting user: {e}")
            return f"Error unmuting user."
        
    @utils.function_info
    async def create_voice_channel(self, guild_id: int, channel_name: str):
        """Creates a new voice channel in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param channel_name: The name of the new voice channel.
        :type channel_name: string
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return f"Guild with ID {guild_id} not found."

        try:
            await guild.create_voice_channel(channel_name)
            return f"Successfully created voice channel '{channel_name}'."
        except discord.HTTPException as e:
            logging.error(f"Error creating voice channel: {e}")
            return f"Error creating voice channel."
        
    @utils.function_info
    async def delete_voice_channel(self, guild_id: int, channel_id: int):
        """Deletes the specified voice channel.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param channel_id: The ID of the voice channel to delete.
        :type channel_id: integer
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        channel = discord.utils.get(self.get_all_channels(), id=channel_id)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            return f"Voice channel with ID {channel_id} not found."

        try:
            await channel.delete()
            return f"Successfully deleted voice channel '{channel.name}'."
        except discord.HTTPException as e:
            logging.error(f"Error deleting voice channel: {e}")
            return f"Error deleting voice channel."
        
    @utils.function_info
    async def create_text_channel(self, guild_id: int, channel_name: str):
        """Creates a new text channel in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param channel_name: The name of the new text channel.
        :type channel_name: string
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return f"Guild with ID {guild_id} not found."

        try:
            await guild.create_text_channel(channel_name)
            return f"Successfully created text channel '{channel_name}'."
        except discord.HTTPException as e:
            logging.error(f"Error creating text channel: {e}")
            return f"Error creating text channel."
        
    @utils.function_info
    async def delete_text_channel(self, guild_id: int, channel_id: int):
        """Deletes the specified text channel.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :param channel_id: The ID of the text channel to delete.
        :type channel_id: integer
        :return: A message indicating the result of the operation.
        :rtype: string
        """
        channel = discord.utils.get(self.get_all_channels(), id=channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return f"Text channel with ID {channel_id} not found."

        try:
            await channel.delete()
            return f"Successfully deleted text channel '{channel.name}'."
        except discord.HTTPException as e:
            logging.error(f"Error deleting text channel: {e}")
            return f"Error deleting text channel."
        
    @utils.function_info
    async def get_user_voice_state(self, user_id: int):
        """Gets the voice state of the specified user.

        :param user_id: The ID of the user to get the voice state for.
        :type user_id: integer
        :return: A dictionary containing the voice state of the user.
        :rtype: dict
        """
        if not self._voice_client or not self._voice_client.is_connected():
            return "Bot is not connected to any voice channel."

        guild = self._voice_client.guild
        member = guild.get_member(user_id)
        if member is None:
            return f"User with ID {user_id} not found."

        return {
            "user_id": member.id,
            "display_name": member.display_name,
            "voice_channel_id": member.voice.channel.id if member.voice else None,
            "is_muted": member.voice.mute if member.voice else None,
            "is_deafened": member.voice.deaf if member.voice else None,
            "is_streaming": member.voice.self_stream if member.voice else None,
        }
    
    @utils.function_info
    async def get_guild_users(self, guild_id: int):
        """Gets a list of users in the specified guild.

        :param guild_id: The ID of the Discord guild.
        :type guild_id: integer
        :return: A list of dictionaries containing user information.
        :rtype: list
        """
        guild = discord.utils.get(self.guilds, id=guild_id)
        if guild is None:
            return []

        users = [
            {
                "id": member.id,
                "name": member.display_name,
                "status": str(member.status),
                "joined_at": str(member.joined_at),
            }
            for member in guild.members
        ]
        return users

def print_welcome_screen():
    """Prints the ASCII logo and basic program details."""
    ascii_logo = f"""{TextColor.OKCYAN}                                                                      
 __   __                  _                    _  
 \ \ / /__  _   _ _ __   | |    ___   ___ __ _| | 
  \ V / _ \| | | | '__|  | |   / _ \ / __/ _` | | 
   | | (_) | |_| | |     | |__| (_) | (_| (_| | | 
   |_|\___/ \__,_|_|     |_____\___/ \___\__,_|_| 
  ____             _                 _           
 | __ )  __ _ _ __| |_ ___ _ __   __| | ___ _ __ 
 |  _ \ / _` | '__| __/ _ \ '_ \ / _` |/ _ \ '__|
 | |_) | (_| | |  | ||  __/ | | | (_| |  __/ |   
 |____/ \__,_|_|   \__\___|_| |_|\__,_|\___|_|   """
    program_details = f"""{TextColor.ENDC}
 Version: {__version__}
 Author(s): {authors}
 Description: {description}
 
 {TextColor.OKCYAN}OpenAI Configuration{TextColor.ENDC}
 Organization ID: {config.OPENAI_ORG_ID}
 Model: {config.OPENAI_MODEL}
 Model Temperature: {config.OPENAI_MODEL_TEMPERATURE}
 Voice Model: {config.OPENAI_VOICE_MODEL}
 TTS Voice: {config.OPENAI_TTS_VOICE}
 TTS Model: {config.OPENAI_TTS_MODEL}
 Assistant ID: {config.OPENAI_ASSISTANT_ID}
 Assistant Name: {config.OPENAI_ASSISTANT_NAME}
 Vector Store ID: {config.OPENAI_VECTOR_STORE_ID}

 {TextColor.OKCYAN}Discord Configuration{TextColor.ENDC}
 Continuous Listen Recording Duration: {config.CONTINUOUS_LISTEN_RECORDING_DURATION}
 Continuous Listen Pause Duration: {config.CONTINUOUS_LISTEN_PAUSE_DURATION}
 Continuous Listen Activation Phrase: \"{config.CONTINUOUS_LISTEN_ACTIVATION_PHRASE}\"
    """
    logging.info(ascii_logo)
    logging.info(program_details)


if __name__ == "__main__":
    print_welcome_screen()

    extra_tools = [
        openai_get_vector_store_file_ids,
        openai_read_file_into_vector_store,
        openai_update_assistant_code_interpreter,
        openai_update_assistant_vector_store,
        search_osrs_wiki,
        search_osrs_item_value,
        search_rs3_wiki,
        search_rs3_item_value
    ]

    intents = discord.Intents.default()
    intents.message_content = True
    bot = Bartender(
        command_prefix=COMMAND_PREFIX, intents=intents, extra_tools=extra_tools
    )
    bot.run(config.DISCORD_BOT_TOKEN)        