import threading
import logging
import sys
import json
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import APIError

from google.cloud import firestore

from ylb.utils import TextColor
from ylb.helpers import audio
from ylb import config
from ylb import openai_client as client

# Initialize Firestore client
db = firestore.Client()

class ConversationManager(threading.Thread):
    """
    This class represents a conversation thread, capable of executing conversation steps asynchronously.
    It manages the life cycle of an assistant's conversation and handles dynamic function calls.
    """

    def __init__(self, tools, prompt=config.OPENAI_DEFAULT_PROMPT):
        """
        Initializes the ConversationManager object with tools and an optional prompt.

        Parameters:
        tools (list): A list of tools configured for the assistant.
        prompt (str, optional): Initial user prompt to start the conversation.
        """
        super().__init__()
        self.tools = tools
        self.start_prompt = prompt
        self.max_cycles = config.CONVO_MAX_CYCLES

        try:
            # Retrieve or create the assistant based on provided ID
            if config.OPENAI_ASSISTANT_ID:
                self.assistant = client.beta.assistants.retrieve(
                    config.OPENAI_ASSISTANT_ID
                )
                # Always update the existing assistant with the latest tools list
                client.beta.assistants.update(
                    assistant_id=self.assistant.id,
                    tools=[tool.info for tool in self.tools]
                    + [{"type": "file_search"}, {"type": "code_interpreter"}],
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [config.OPENAI_VECTOR_STORE_ID]
                        },
                        "code_interpreter": {
                            "file_ids": eval(self.get_vector_store_file_ids())
                        },
                    },
                )
                logging.info(
                    f"Updated existing assistant ({self.assistant.id}) with latest tools"
                )
            else:
                self.assistant = self.create_new_assistant()
        except APIError as e:
            logging.error(f"Failed to retrieve or update the assistant: {e}")
            sys.exit(1)

        self.thread = client.beta.threads.create()
        self.temperature = config.OPENAI_MODEL_TEMPERATURE
        self.last_message = None

    def create_new_assistant(self):
        """
        Creates a new assistant if no valid ID is found in configuration. Asks for user input to confirm creation.
        """
        try:
            create_new = input(
                "No valid assistant ID found. Create a new assistant? (yes/no): "
            )
            if create_new.lower() == "yes":
                self.assistant = client.beta.assistants.create(
                    name=config.OPENAI_ASSISTANT_NAME,
                    instructions=config.SYSTEM_PROMPT,
                    tools=[tool.info for tool in self.tools]
                    + [{"type": "file_search"}, {"type": "code_interpreter"}],
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [config.OPENAI_VECTOR_STORE_ID]
                        },
                        "code_interpreter": {
                            "file_ids": eval(self.get_vector_store_file_ids())
                        },
                    },
                    model=config.OPENAI_MODEL,
                    temperature=config.OPENAI_MODEL_TEMPERATURE,
                )
                logging.info(
                    f"Created new assistant. Assistant ID: {self.assistant.id}"
                )
                logging.info(
                    "Please record this ID in your configuration and restart the program."
                )
                sys.exit(1)
            else:
                print("Operation cancelled by user.")
                sys.exit(1)
        except APIError as e:
            logging.error(f"Failed to create or retrieve the assistant: {e}")

    def run(self):
        try:
            while True:
                if self.start_prompt:
                    self.last_message = client.beta.threads.messages.create(
                        thread_id=self.thread.id,
                        role="user",
                        content=self.start_prompt,
                    )
                    self.start_prompt = None
                else:
                    text_input = input(
                        f"\n[📃] Enter your message (or 'v' to record voice): {TextColor.WARNING}{TextColor.BOLD}"
                    )
                    print(TextColor.ENDC)
                    if not text_input:
                        pass
                    elif text_input[0] == "v":
                        split_input = text_input.split(" ")
                        if split_input[-1].isdigit() and int(split_input[-1]) <= 60:
                            listen_time = int(split_input[-1])
                            voice_input = audio.listen(listen_time)
                        else:
                            voice_input = audio.listen(config.CONTINUOUS_LISTEN_RECORDING_DURATION)
                        self.last_message = client.beta.threads.messages.create(
                            thread_id=self.thread.id,
                            role="user",
                            content=voice_input
                            if voice_input
                            else "Continue the conversation with a question for the user.",
                        )
                    else:
                        self.last_message = client.beta.threads.messages.create(
                            thread_id=self.thread.id, role="user", content=text_input
                        )
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=self.thread.id,
                    assistant_id=self.assistant.id,
                    instructions=config.INSTRUCTION_PROMPT,
                    temperature=self.temperature,
                    tool_choice="auto",
                )
                while True:
                    time.sleep(0.01)
                    run = client.beta.threads.runs.retrieve(
                        thread_id=self.thread.id, run_id=run.id
                    )
                    if run.status == "completed":
                        messages = client.beta.threads.messages.list(
                            thread_id=self.thread.id,
                            limit=1,
                        )
                        for message in messages:
                            if message.role == "assistant":
                                try:
                                    print(
                                        f"\n{TextColor.BOLD}{TextColor.OKGREEN}{TextColor.BOLD}[💭] {message.content[0].text.value}{TextColor.ENDC}\n"
                                    )
                                except Exception:
                                    logging.error(
                                        "Failed to print assistant message: %s", message
                                    )
                                break
                        logging.info(f"Run {run.id} completed")
                        break
                    elif run.status == "requires_action":
                        logging.info(
                            f"Required action in run {run.id} / thread {run.thread_id} / assistant {run.assistant_id}"
                        )
                        self.handle_requires_action(run, run.id)
                    elif run.status == "failed":
                        logging.error(
                            f"Run {run.id} failed with error: {run.last_error.code} -> {run.last_error.message}"
                        )
                        break
                    else:
                        pass
        except KeyboardInterrupt:
            print(TextColor.ENDC)
            logging.info(f"User exited using keyboard interrupt")
        except Exception as e:
            logging.error(
                f"Unhandled error during conversation stream: {e}\n{traceback.format_exc()}"
            )

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
            thread_id=self.thread.id, run_id=run_id, tool_outputs=tool_outputs
        )

    def update_transcript(self, username, display_name, message, timestamp):
        """
        Updates the conversation transcript with a new message and stores it in Firestore.

        Args:
            username (str): The username of the message sender.
            display_name (str): The display name of the message sender.
            message (str): The content of the message.
            timestamp (datetime): The timestamp of the message.
        """
        # Store transcript data in Firestore
        doc_ref = db.collection("transcripts").document()
        doc_ref.set(
            {
                "username": username,
                "display_name": display_name,
                "message": message,
                "timestamp": timestamp,
            }
        )
        # Update local transcript
        self.transcript[timestamp] = {
            "username": username,
            "display_name": display_name,
            "message": message,
            "timestamp": timestamp,
        }


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
        for tool in self.tools:
            if tool.info["function"]["name"] == function_name:
                try:
                    function_response = tool(**arguments)
                    return str(function_response)
                except Exception as e:
                    logging.error(f"Error during tool call: {str(e)}\n{traceback.format_exc()}")
                    return f"Error during tool call: {str(e)}\n{traceback.format_exc()}"
        logging.error(f"Tool function '{function_name}' not found.")
        return f"Error: Tool function '{function_name}' not found."

    def get_vector_store_file_ids(self) -> str:
        """
        Retrieve a list of file IDs and names from the vector store.

        :return: A list of all file IDs in the vector store.
        :rtype: string
        """
        try:
            file_entries = client.beta.vector_stores.files.list(
                config.OPENAI_VECTOR_STORE_ID
            )
            file_info_list = [file_entry.id for file_entry in file_entries.data]
            logging.info(f"Retrieved vector store file IDs: {file_info_list}")
            return str(file_info_list)
        except Exception as e:
            logging.error(f"Error retrieving file info from vector store: {str(e)}")
            return f"Error retrieving file info from vector store: {str(e)}"
