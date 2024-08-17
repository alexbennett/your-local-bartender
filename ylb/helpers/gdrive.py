import io
import os
import logging
import traceback

from ga import config
from ga import utils

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


def get_drive_service():
    """
    Returns a service that connects to the Google Drive API.

    Returns:
        service (googleapiclient.discovery.Resource): A service object that allows interaction with the Google Drive API.
    """
    try:
        creds = Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception as e:
        error_message = f"Error in get_drive_service: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_move_file_to_folder(file_id: str, folder_id: str) -> str:
    """
    Move a file to a specified folder in Google Drive.

    :param file_id: The ID of the file to be moved.
    :type file_id: string
    :param folder_id: The ID of the folder to move the file to.
    :type folder_id: string
    :return: A string indicating the success of the operation.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        # Retrieve the existing parents to remove
        file = service.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))
        # Move the file to the new folder
        file = (
            service.files()
            .update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            )
            .execute()
        )
        return f"Moved file {file_id} to folder {folder_id}"
    except Exception as e:
        error_message = (
            f"Error in gdrive_move_file_to_folder: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_find_file(
    name: str = None, snippet: str = None, mime_type: str = None
) -> str:
    """
    Search for files in Google Drive based on the provided parameters.

    :param name: The name of the file to search for. (optional)
    :type name: string
    :param snippet: A snippet of text to search for within the file. (optional)
    :type snippet: string
    :param mime_type: The MIME type of the file to search for. (optional)
    :type mime_type: string
    :return: A string indicating the search results.
    :raises ValueError: If no search parameters are provided.
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        query = []
        if name:
            query.append(f"name contains '{name}'")
        if snippet:
            query.append(f"fullText contains '{snippet}'")
        if mime_type:
            query.append(f"mimeType = '{mime_type}'")

        if not query:
            raise ValueError("At least one search parameter must be provided.")

        results = (
            service.files()
            .list(
                q=" and ".join(query),
                spaces="drive",
                corpora="drive",
                driveId=config.DEFAULT_SHARED_DRIVE_ID,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        items = results.get("files", [])
        if not items:
            return "No files found."
        else:
            return f"Found files: {items}"
    except Exception as e:
        error_message = f"Error in gdrive_find_file: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_create_folder(name: str, parent_folder_id: str = None) -> str:
    """
    Create a new folder in Google Drive.

    :param name: The name of the folder.
    :type name: string
    :param parent_folder_id: The ID of the parent folder (optional).
    :type parent_folder_id: string
    :return: A string indicating the successful creation of the folder.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]
        folder = service.files().create(body=file_metadata, fields="id").execute()
        return f"Created folder {name} with ID: {folder.get('id')}"
    except Exception as e:
        error_message = f"Error in gdrive_create_folder: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_share_file(file_id: str, email_addresses: list) -> str:
    """
    Share a Google Drive file with a list of email addresses.

    :param file_id: The ID of the file to be shared.
    :type file_id: string
    :param email_addresses: A list of email addresses to share the file with.
    :type email_addresses: string
    :return: A string indicating the file ID and the email addresses it was shared with.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        batch = service.new_batch_http_request()
        user_permission = {
            "type": "user",
            "role": "editor",
            "emailAddress": None,
        }
        for email in email_addresses:
            user_permission["emailAddress"] = email
            batch.add(
                service.permissions().create(
                    fileId=file_id,
                    body=user_permission,
                    fields="id",
                )
            )
        batch.execute()
        return f"Shared file {file_id} with {[email for email in email_addresses]}"
    except Exception as e:
        error_message = f"Error in gdrive_share_file: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_list_files(folder_id: str) -> str:
    """
    Lists all files in the folder with the given ID, otherwise returns all files in the root of the shared drive.

    :param folder_id: The ID of a folder within the shared drive.
    :type folder_id: string
    :return: A list of the files in the folder.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        results = (
            service.files()
            .list(
                q=f"trashed=false",
                spaces="drive",
                corpora="drive",
                driveId=config.DEFAULT_SHARED_DRIVE_ID,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        items = results.get("files", [])
        if not items:
            return "No files found."
        else:
            return f"Found files: {items}"
    except Exception as e:
        error_message = f"Error in gdrive_list_files: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_read_file(file_id: str) -> str:
    """
    Reads the content of a file from Google Drive.

    :param file_id: The ID of the file to be read.
    :type file_id: string
    :return: The content of the file as a string.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)

        # Return the bytes content directly
        try:
            return fh.getvalue().decode("utf-8")
        except UnicodeDecodeError:
            return fh.getvalue()
    except Exception as e:
        error_message = f"Error in gdrive_read_file: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_upload_file(
    file_name: str,
    file_path: str,
    folder_id: str = config.DEFAULT_SHARED_DRIVE_ID,
    mime_type: str = "text/plain",
) -> str:
    """
    Uploads a generic file to a Google Drive folder.

    :param file_name: The name of the file to be uploaded.
    :type file_name: string
    :param file_path: The path to the file on the local machine.
    :type file_path: string
    :param folder_id: The ID of the Google Drive folder where the file will be uploaded. If None, uploads to the root directory.
    :type folder_id: string
    :param mime_type: The MIME type of the file. Defaults to 'text/plain'.
    :type mime_type: string
    :return: The ID of the uploaded file.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service

        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")

        file_metadata = {
            "name": file_name,
            "parents": (
                [folder_id] if folder_id != config.DEFAULT_SHARED_DRIVE_ID else []
            ),
        }
        media = MediaFileUpload(file_path, mimetype=mime_type)
        file = (
            service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        return file.get("id")
    except Exception as e:
        error_message = f"Error in gdrive_upload_file: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_upload_spreadsheet(name: str, file_path: str, folder_id: str = None) -> str:
    """
    Uploads a spreadsheet to Google Drive and converts it to Google Sheets format,
    handling various input formats including Microsoft Excel, OpenDocument Spreadsheet, CSV, TSV, and plain text.

    :param name: The name of the file to be uploaded.
    :type name: string
    :param file_path: The path to the file on the local machine.
    :type file_path: string
    :param folder_id: The ID of the Google Drive folder where the file will be uploaded. If None, uploads to the root directory.
    :type folder_id: string
    :return: The ID of the uploaded spreadsheet in Google Sheets format.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service

        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")

        # Determine the MIME type based on the file extension
        mime_types = {
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ods": "application/vnd.oasis.opendocument.spreadsheet",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".txt": "text/plain",
        }
        file_extension = os.path.splitext(file_path)[1].lower()
        mime_type = mime_types.get(
            file_extension, "application/vnd.google-apps.spreadsheet"
        )

        if mime_type is None:
            raise ValueError("Unsupported file type for spreadsheet upload.")

        file_metadata = {
            "name": name,
            "parents": [folder_id] if folder_id else [],
            "mimeType": "application/vnd.google-apps.spreadsheet",  # Target Google Sheets format
        }

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        file = (
            service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )

        return f"Uploaded spreadsheet {name} and converted to Google Sheets with ID: {file.get('id')}"
    except Exception as e:
        error_message = (
            f"Error in gdrive_upload_spreadsheet: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gdrive_upload_document(
    file_name: str, file_path: str, folder_id: str = None
) -> str:
    """
    Uploads a document to Google Drive and converts it to Google Docs format.

    :param file_name: The name of the file to be uploaded.
    :type file_name: string
    :param file_path: The path to the file on the local machine.
    :type file_path: string
    :param folder_id: The ID of the Google Drive folder where the file will be uploaded. If None, uploads to the root directory.
    :type folder_id: string
    :return: The ID of the uploaded document in Google Docs format.
    :rtype: string
    """
    try:
        service = get_drive_service()
        if isinstance(service, str):  # Check if service is an error message
            return service

        if "/mnt/data/" in file_path:
            file_path = file_path.replace("/mnt/data/", "")

        # Determine the MIME type based on the file extension
        mime_types = {
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".odt": "application/vnd.oasis.opendocument.text",
            ".html": "text/html",
            ".htm": "text/html",
            ".rtf": "application/rtf",
            ".txt": "text/plain",
        }
        file_extension = os.path.splitext(file_name)[1].lower()
        mime_type = mime_types.get(
            file_extension, "text/plain"
        )  # Default to plain text if unknown

        if mime_type is None:
            raise ValueError("Unsupported file type for document upload.")

        file_metadata = {
            "name": file_name,
            "parents": [folder_id] if folder_id else [],
            "mimeType": "application/vnd.google-apps.document",  # Target Google Docs format
        }

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        file = (
            service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )

        return f"Uploaded document {file_name} and converted to Google Docs with ID: {file.get('id')}"
    except Exception as e:
        error_message = (
            f"Error in gdrive_upload_document: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message
