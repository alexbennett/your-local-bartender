import traceback

import os
import logging
from typing import Optional
from ylb import utils


@utils.function_info
def read_file(
    file_path: str, line_number: Optional[int] = None, num_lines: Optional[int] = None
) -> str:
    """
    Open a file and return its content.

    :param file_path: The path of the file to execute. Must be within the current working directory.
    :type file_path: string
    :param line_number: The line number to start reading from (optional).
    :type line_number: integer
    :param num_lines: The number of lines to read (optional).
    :type num_lines: integer
    :return: The content of the executed file.
    :rtype: string
    :raises ValueError: If the file path is not within the current working directory.
    """
    try:
        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")
        with open(file_path, "r") as file:
            if line_number is not None and num_lines is not None:
                lines = file.readlines()[line_number - 1 : line_number - 1 + num_lines]
                content = "".join(lines)
            elif line_number is not None:
                lines = file.readlines()[line_number - 1 :]
                content = "".join(lines)
            elif num_lines is not None:
                lines = file.readlines()[:num_lines]
                content = "".join(lines)
            else:
                content = file.read()
        logging.info(f"Reading file: {file_path}")
        return content
    except Exception as e:
        logging.error(f"Error executing file: {str(e)}\n{traceback.format_exc()}")
        return f"Error executing file: {str(e)}\n{traceback.format_exc()}"


@utils.function_info
def edit_file(
    file_path: str,
    content: Optional[str] = "",
    readmode: Optional[str] = "a+",
    line_number: Optional[int] = None,
) -> str:
    """
    Edit a file by appending content or overwriting it with optional read mode.
    If line_number is provided, the content will be injected at that line number.

    :param file_path: The path of the file to edit. Must be within the current working directory.
    :type file_path: string
    :param content: The content to append or overwrite the file with (optional).
    :type content: string
    :param readmode: The read mode for opening the file (optional, default is 'a+').
    :type readmode: string
    :param line_number: The line number to inject the content (optional).
    :type line_number: integer
    :return: A message indicating the file was edited.
    :rtype: string
    :raises ValueError: If the file path is not within the current working directory.
    """
    try:
        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")
        if line_number is not None:
            with open(file_path, "r") as file:
                lines = file.readlines()
            lines.insert(line_number - 1, content)
            content = "".join(lines)
        with open(file_path, readmode) as file:
            file.write(content)
        logging.info(f"Editing file: {file_path}")
        return f"Editing file: {file_path}"
    except Exception as e:
        logging.info(f"Error editing file: {str(e)}\n{traceback.format_exc()}")
        return f"Error editing file: {str(e)}\n{traceback.format_exc()}"


@utils.function_info
def delete_file(file_path: str) -> str:
    """
    Delete a file from the filesystem.

    :param file_path: The path of the file to delete.
    :type file_path: string
    :return: A message indicating the file was deleted.
    :rtype: string
    :raises ValueError: If the file path is not within the current working directory.
    """
    try:
        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.warning(f"Deleting file: {file_path}")
            return f"Deleting file: {file_path}"
        else:
            logging.info(f"File not found: {file_path}")
            return f"File not found: {file_path}"
    except Exception as e:
        logging.error(f"Error deleting file: {str(e)}\n{traceback.format_exc()}")
        return f"Error deleting file: {str(e)}\n{traceback.format_exc()}"


@utils.function_info
def create_file(
    file_path: str,
    content: Optional[str] = "",
    readmode: Optional[str] = "w",
) -> str:
    """
    Create a file at the specified path with optional content and read mode.
    The file path must be within the current working directory.

    :param file_path: The path where the new file will be created.
    :type file_path: string
    :param content: The content to write to the file (optional).
    :type content: string
    :param readmode: The read mode for opening the file (optional, default is 'w').
    :type readmode: string
    :return: A message indicating the file was created.
    :rtype: string
    """
    try:
        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")
        logging.info(f"Creating file {file_path} with content: {content}")
        with open(file_path, readmode) as file:
            if content:
                file.write(content)
        return f"Creating file: {file_path}"
    except Exception as e:
        logging.error(f"Error creating file: {str(e)}\n{traceback.format_exc()}")
        return f"Error creating file: {str(e)}\n{traceback.format_exc()}"
