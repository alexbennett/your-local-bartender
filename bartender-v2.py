import os
import asyncio
import time
import threading
import speech_recognition as sr
import inspect
import json
import logging
import discord
from discord.ext import commands
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from ylb import config
from ylb import utils
from ylb.utils import TextColor
from ylb import openai_client as client
from google.cloud import firestore

from ylb.helpers.openai import (
    openai_read_file_into_vector_store,
    openai_get_vector_store_file_ids,
    openai_update_assistant_vector_store,
    openai_update_assistant_code_interpreter,
)

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
            self.get_online_users,
            self.get_bot_display_name,
            self.get_users_in_voice_channel,
            self.get_text_channels,
            self.get_voice_channels,
            self.update_bot_display_name,
            self.send_message_to_channel,
            self.send_reply_to_message,
            self.send_message_reaction,
            self.speak,
            self.join_voice_channel,
            self.leave_voice_channel,
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
                            "file_ids": openai_get_vector_store_file_ids()
                        },
                    },
                )
                print(f"Updated existing assistant ({assistant.id}) with latest tools.")
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
                print(f"Created new assistant. Assistant ID: {assistant.id}")
                print(
                    "Please record this ID in your configuration and restart the program."
                )
                exit(1)
        except Exception as e:
            print(f"Failed to initialize assistant: {str(e)}{traceback.format_exc()}")
            exit(1)

        self.listen_task = None
        self.assistant_thread = None
        self.assistant = client.beta.assistants.retrieve(config.OPENAI_ASSISTANT_ID)
        self.current_thread = None
        self.session_doc_ref = None
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
        print(f"{TextColor.HEADER}Logged in as {self.user.name} (ID: {self.user.id}){TextColor.ENDC}")
        print(f"{TextColor.OKCYAN}Connected to the following communities:{TextColor.ENDC}")
        for guild in self.guilds:
            print(
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
            utils.print_section(f"Joining voice channel", TextColor.OKCYAN)
            try:
                await self.join(message)
            except Exception as e:
                print(
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
            f"and voice channel '{channel.name}' (id: {channel.id}). The conversation was started by '{message.author.display_name}'."
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

        await message.add_reaction("👂")

    async def continuous_listen(self, text_channel):
        """
        Continuously records audio in intervals, processes it, and manages assistant responses.

        Args:
            text_channel (discord.TextChannel): Discord text channel to send messages.
        """
        while True:
            try:
                if not self._voice_client.is_connected():
                    print(
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

                # Add the transcript as a message to the assistant thread
                msg = client.beta.threads.messages.create(
                    thread_id=self.current_thread.id, role="user", content=transcript
                )

                # # Store the message in the Firestore subcollection
                self.session_doc_ref.collection("messages").add(
                    {
                        "openai_thread_id": self.current_thread.id,
                        "openai_message_id": msg.id,
                        "content": transcript,
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
                                    print(
                                        f"{TextColor.BOLD}{TextColor.OKGREEN}[{config.OPENAI_ASSISTANT_NAME} 💭] {message.content[0].text.value}{TextColor.ENDC}\n"
                                    )
                                    await channel.send(f"💭 {message.content[0].text.value}")

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
                                    print(
                                        "Failed to print assistant message: %s",
                                        message,
                                    )
                                    print(traceback.format_exc())
                        print(f"Run {run.id} completed")
                        break
                    elif run.status == "requires_action":
                        print(
                            f"Required action in {run.id} → {run.thread_id}"
                        )
                        await self.handle_requires_action(run, run.id)
                    elif run.status == "failed":
                        print(
                            f"Run {run.id} failed with error: {run.last_error.code} -> {run.last_error.message}"
                        )
                        break
                    else:
                        pass
                else:
                    print(f"User with ID {user_id} not found in the guild.")

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
                        f"Error during tool call {tool_call_id}: {str(result)}\n{traceback.format_exc()}"
                    )
                    output = f"Error during tool call: {str(result)}\n{traceback.format_exc()}"
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
                print(f"Tool call {tool_call_id} completed")
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
        print(
            f"Processing tool call -> {TextColor.HEADER}{function_name}({json.dumps(arguments, indent=2)}){TextColor.ENDC}"
        )
        for tool in self._tools:
            if tool.info["function"]["name"] == function_name:
                try:
                    # Check if the tool function is async
                    if inspect.iscoroutinefunction(tool.func):
                        function_response = await tool(self, **arguments)
                    else:
                        # If sync, call directly
                        function_response = tool(self, **arguments)
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
        return f"[{user_name}]: {transcript}"

    @utils.function_info
    async def speak(self, message):
        """
        Play the assistant's response in the voice channel and log it to the text thread.

        :param message: The assistant's response text.
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
                        options=f'-af "atempo=1.0" -v "quiet"',
                    )
                # Play the audio file using FFmpeg
                self._voice_client.play(audio)

                # Wait for playback to finish
                while self._voice_client.is_playing():
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Failed to generate TTS audio: {e}")
            print(traceback.format_exc())
            return f"Failed to speak: {e}"

    @utils.function_info
    def get_online_users(self, guild_id: int):
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
    def get_text_channels(self, guild_id: int):
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
    def get_voice_channels(self, guild_id: int):
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
    def get_bot_display_name(self, guild_id: int):
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
 
 {TextColor.OKCYAN}Discord Configuration{TextColor.ENDC}
 Continuous Listen Recording Duration: {config.CONTINUOUS_LISTEN_RECORDING_DURATION}
 Continuous Listen Pause Duration: {config.CONTINUOUS_LISTEN_PAUSE_DURATION}
 Continuous Listen Activation Phrase: {config.CONTINUOUS_LISTEN_ACTIVATION_PHRASE}
 
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
    ]

    intents = discord.Intents.default()
    intents.message_content = True
    bot = Bartender(
        command_prefix=COMMAND_PREFIX, intents=intents, extra_tools=extra_tools
    )
    bot.run(config.DISCORD_BOT_TOKEN)
