import os
from ylb import utils


@utils.function_info
def list_folder(folder_path: str) -> str:
    """
    List files and directories in a specified folder.

    :param folder_path: The path of the folder to list.
    :type folder_path: string
    :return: A string containing a list of files and directories in the specified folder.
    :rtype: string
    :raises: Exception if there is an error listing the folder.
    :raises: Exception if the specified folder is not under the present working directory.
    """
    try:
        if "/mnt/data/" in folder_path:
            folder_path = folder_path.replace("/mnt/data/", "")
        abs_folder_path = os.path.abspath(folder_path)
        if not abs_folder_path.startswith(os.getcwd()):
            raise Exception(
                "Error: Only folders under the present working directory can be listed."
            )
        folder_contents = os.listdir(abs_folder_path)
        return "\n".join(folder_contents)
    except Exception as e:
        return f"Error listing folder: {str(e)}"


@utils.function_info
def create_folder(folder_path: str) -> str:
    """
    Create a new folder at the specified path.

    :param folder_path: The path where the new folder will be created.
    :type folder_path: string
    :return: A message indicating the folder was created.
    :rtype: string
    :raises: Exception if the specified folder is not under the present working directory.
    """
    try:
        if "/mnt/data/" in folder_path:
            folder_path = folder_path.replace("/mnt/data/", "")
        abs_folder_path = os.path.abspath(folder_path)
        if not abs_folder_path.startswith(os.getcwd()):
            raise Exception(
                "Error: Only folders under the present working directory can be created."
            )
        os.makedirs(abs_folder_path, exist_ok=True)
        return f"Creating folder: {abs_folder_path}"
    except Exception as e:
        return f"Error creating folder: {str(e)}"


@utils.function_info
def delete_folder(folder_path: str) -> str:
    """
    Delete a folder from the filesystem.

    :param folder_path: The path of the folder to delete.
    :type folder_path: string
    :return: A message indicating the folder was deleted.
    :rtype: string
    :raises: Exception if the specified folder is not under the present working directory.
    """
    try:
        if "/mnt/data/" in folder_path:
            folder_path = folder_path.replace("/mnt/data/", "")
        abs_folder_path = os.path.abspath(folder_path)
        if not abs_folder_path.startswith(os.getcwd()):
            raise Exception(
                "Error: Only folders under the present working directory can be deleted."
            )
        if os.path.exists(abs_folder_path):
            os.rmdir(abs_folder_path)
            return f"Deleting folder: {abs_folder_path}"
        else:
            return f"Folder not found: {abs_folder_path}"
    except Exception as e:
        return f"Error deleting folder: {str(e)}"
