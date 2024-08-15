import json
import logging
from uuid import uuid4
from typing import Optional, List

from ylb import config
from ylb import utils
from ylb import openai_client as client


@utils.function_info
def remember(
    full_content: str,
    synopsis: str = None,
    keywords: Optional[List] = None,
    tags: Optional[List] = None,
    is_reminder: bool = False,
) -> str:
    """
    Remember content by adding it to the deep memory JSON file with a unique key and adding the key to the short memory file with a short synopsis, keywords, tags, and reminder option.

    :param full_content: The full content to remember.
    :type full_content: string
    :param synopsis: A short summary of the content (optional).
    :type synopsis: string
    :param keywords: The keywords associated with the content (optional).
    :type keywords: string
    :param tags: The tags associated with the content (optional).
    :type tags: string
    :param is_reminder: Indicates if this content is a reminder.
    :type is_reminder: boolean
    :return: The unique key associated with the remembered content.
    :rtype: string
    """
    key = str(uuid4())

    # Initialize keywords and tags as lists if None
    if keywords is None:
        keywords = []
    if tags is None:
        tags = []

    # Add "reminder" to tags if `is_reminder` is True
    if is_reminder and "reminder" not in tags:
        tags.append("reminder")

    # Handle deep memory
    deep_memory_entry = {"content": full_content, "keywords": keywords, "tags": tags}
    try:
        with open(config.DEEP_MEMORY_FILENAME, "r+") as file:
            data = json.load(file)
            data[key] = deep_memory_entry
            file.seek(0)
            json.dump(data, file, indent=4)
            file.truncate()
    except FileNotFoundError:
        with open(config.DEEP_MEMORY_FILENAME, "w") as file:
            json.dump({key: deep_memory_entry}, file, indent=4)

    # Handle short memory with synopsis, keywords, and tags
    short_memory_entry = {"synopsis": synopsis, "keywords": keywords, "tags": tags}
    try:
        with open(config.SHORT_MEMORY_FILENAME, "r+") as file:
            short_memory = json.load(file)
            short_memory[key] = short_memory_entry
            file.seek(0)
            json.dump(short_memory, file, indent=4)
            file.truncate()
    except FileNotFoundError:
        with open(config.SHORT_MEMORY_FILENAME, "w") as file:
            json.dump({key: short_memory_entry}, file, indent=4)

    logging.info(f"Remembered {key}={synopsis}")
    return f"Remembered {key}={synopsis}"


@utils.function_info
def recall(key: str) -> str:
    """
    Recall the content associated with a key from the deep memory JSON file and return as a JSON string.

    :param key: The unique key associated with the content.
    :type key: string
    :return: The remembered content as a JSON string if found, otherwise an error message.
    :rtype: string
    """
    try:
        with open(config.DEEP_MEMORY_FILENAME, "r") as file:
            data = json.load(file)
            entry = data.get(key, None)
            if entry is None:
                return f"Nothing recalled for {key}"
            logging.info(f"Recalled memory {key}={entry}")
            return json.dumps({key: entry}, indent=4)
    except FileNotFoundError:
        return "Nothing recalled"


@utils.function_info
def list_short_memory() -> str:
    """
    List all keys stored in the short memory file and return as a JSON string.

    :return: JSON string of the short memory content.
    :rtype: str
    """
    try:
        with open(config.SHORT_MEMORY_FILENAME, "r") as file:
            short_memory = json.load(file)
            return json.dumps(short_memory, indent=4)
    except FileNotFoundError:
        return json.dumps({}, indent=4)


@utils.function_info
def list_reminders() -> str:
    """
    List all short memory entries that have the "reminder" tag and return as a JSON string.

    :return: JSON string of all reminder entries in short memory.
    :rtype: str
    """
    try:
        with open(config.SHORT_MEMORY_FILENAME, "r") as file:
            short_memory = json.load(file)
            reminders = {
                key: value
                for key, value in short_memory.items()
                if "reminder" in value.get("tags", [])
            }
            return json.dumps(reminders, indent=4)
    except FileNotFoundError:
        return json.dumps({}, indent=4)
