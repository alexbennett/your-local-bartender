import logging

from ylb import config, utils
from ylb import openai_client as client


@utils.function_info
def openai_read_file_into_vector_store(file_path: str) -> str:
    """
    Upload a file and add it to the OpenAI vector store, returning the file ID.
    Adding the file to the vector store makes it available to Gwen for further
    processing, such as file search or code interpretation.

    :param file_path: The path of the file to upload.
    :type file_path: string
    :return: The file ID after uploading.
    :rtype: string
    """
    try:
        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")
        # Assuming vector_store_id is globally configured or predefined
        vector_store_id = config.OPENAI_VECTOR_STORE_ID
        with open(file_path, "rb") as file:
            # Upload file to OpenAI and create a file entry in the vector store
            file_response = client.files.create(file=file, purpose="assistants")
            file_id = file_response.id
            # Add file to vector store
            client.beta.vector_stores.files.create_and_poll(
                vector_store_id=vector_store_id, file_id=file_id
            )
        logging.info(f"File uploaded and added to vector store: {file_path}")
        return file_id
    except Exception as e:
        logging.error(f"Error uploading file to vector store: {str(e)}")
        return f"Error uploading file to vector store: {str(e)}"


@utils.function_info
def openai_get_vector_store_file_ids() -> str:
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


@utils.function_info
def openai_update_assistant_vector_store(vector_store_ids):
    """
    Updates the assistant's vector store configuration.

    :param vector_store_ids: List of vector store IDs to attach to the assistant.
    :type vector_store_ids: string
    """
    try:
        client.beta.assistants.update(
            assistant_id=config.OPENAI_ASSISTANT_ID,
            tool_resources={"file_search": {"vector_store_ids": vector_store_ids}},
        )
        logging.info(
            f"Updated assistant ({config.OPENAI_ASSISTANT_ID}) with new vector store IDs: {vector_store_ids}"
        )
        return f"Updated assistant ({config.OPENAI_ASSISTANT_ID}) with new vector store IDs: {vector_store_ids}"
    except Exception as e:
        logging.error(f"Failed to update the assistant's vector store: {str(e)}")
        return f"Failed to update the assistant's vector store: {str(e)}"


@utils.function_info
def openai_update_assistant_code_interpreter():
    """
    Updates the assistant code interpreter tool to include all file IDs returned by openai_get_vector_store_file_ids.

    :return: A message indicating the status of the update.
    :rtype: string
    """
    try:
        # Retrieve the list of file IDs from the vector store
        file_ids_str = openai_get_vector_store_file_ids()
        file_ids = eval(
            file_ids_str
        )  # Convert the string representation back to a list

        if not isinstance(file_ids, list):
            raise ValueError("Retrieved file IDs are not in the expected list format")

        # Update the assistant's code interpreter tool with the retrieved file IDs
        client.beta.assistants.update(
            assistant_id=config.OPENAI_ASSISTANT_ID,
            tool_resources={"code_interpreter": {"file_ids": file_ids}},
        )
        logging.info(f"Updated assistant code interpreter with file IDs: {file_ids}")
        return f"Updated assistant code interpreter with file IDs: {file_ids}"
    except Exception as e:
        logging.error(f"Failed to update the assistant's code interpreter: {str(e)}")
        return f"Failed to update the assistant's code interpreter: {str(e)}"
