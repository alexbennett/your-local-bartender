import os
import json
import logging
import traceback

from ylb import config
from ylb import utils

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/presentations"]


def get_service():
    """
    Returns a service that connects to the Google Slides API.

    :return: An instance of the Google Slides API service.
    :rtype: service
    """
    try:
        creds = Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("slides", "v1", credentials=creds)
        return service
    except Exception as e:
        error_message = f"Error in get_service: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_create_presentation(title: str):
    """
    Creates a new Google Slides presentation.

    :param title: The title of the presentation.
    :type title: string
    :return: The presentation ID.
    :rtype: string
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        presentation_body = {"title": title}
        presentation = service.presentations().create(body=presentation_body).execute()
        return_message = f"Created presentation: {presentation['presentationId']}"
        print(return_message)
        return return_message
    except Exception as e:
        error_message = (
            f"Error in gslides_create_presentation: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_open_presentation(presentation_id: str):
    """
    Opens an existing Google Slides presentation and retrieves its metadata.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :return: The metadata of the presentation.
    :rtype: dict
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        presentation = (
            service.presentations().get(presentationId=presentation_id).execute()
        )

        return str(presentation)
    except Exception as e:
        error_message = (
            f"Error in gslides_open_presentation: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_create_slide(
    presentation_id: str,
    slide_title: str = None,
    slide_body: str = None,
):
    """
    Creates a new slide in a presentation with the specified layout and optionally updates
    the content of the newly created slide with the provided title and body.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_title: The title text to insert into the slide, defaults to None
    :type slide_title: string
    :param slide_body: The body text to insert into the slide, defaults to None
    :type slide_body: string
    :return: The ID of the new slide.
    :rtype: string
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service

        insertion_index = 1

        # Prepare the request to create the slide
        requests = [
            {
                "createSlide": {
                    "insertionIndex": insertion_index,
                    "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
                }
            }
        ]

        # Execute the batch update to create the slide
        body = {"requests": requests}
        response = (
            service.presentations()
            .batchUpdate(presentationId=presentation_id, body=body)
            .execute()
        )

        # Get the new slide ID from the response
        new_slide_id = response.get("replies")[0].get("createSlide").get("objectId")

        if slide_title or slide_body:
            # Get the new slide's page elements to find the title and body placeholders
            slide = (
                service.presentations()
                .pages()
                .get(presentationId=presentation_id, pageObjectId=new_slide_id)
                .execute()
            )
            title_id = None
            body_id = None
            for element in slide["pageElements"]:
                if "placeholder" in element["shape"]:
                    if element["shape"]["placeholder"]["type"] == "TITLE":
                        title_id = element["objectId"]
                    elif element["shape"]["placeholder"]["type"] == "BODY":
                        body_id = element["objectId"]

            # Prepare requests to update title and body text if they are provided
            update_requests = []
            if slide_title and title_id:
                update_requests.append(
                    {
                        "insertText": {
                            "objectId": title_id,
                            "insertionIndex": 0,
                            "text": slide_title,
                        }
                    }
                )
            if slide_body and body_id:
                update_requests.append(
                    {
                        "insertText": {
                            "objectId": body_id,
                            "insertionIndex": 0,
                            "text": slide_body,
                        }
                    }
                )

            if update_requests:
                body = {"requests": update_requests}
                response = (
                    service.presentations()
                    .batchUpdate(presentationId=presentation_id, body=body)
                    .execute()
                )

        return new_slide_id
    except Exception as e:
        error_message = f"Error in gslides_create_slide: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_update_slide(
    presentation_id: str,
    slide_id: str,
    replace_text: str,
    replace_with: str,
):
    """
    Updates the content of an existing slide by replacing text.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_id: The ID of the slide to update.
    :type slide_id: string
    :param replace_text: The text to be replaced.
    :type replace_text: string
    :param replace_with: The text to replace with.
    :type replace_with: string
    :return: None
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service

        # Retrieve the slide content
        slide = (
            service.presentations()
            .pages()
            .get(presentationId=presentation_id, pageObjectId=slide_id)
            .execute()
        )

        requests = []
        # Find the placeholder text boxes
        for element in slide.get("pageElements"):
            if (
                element.get("shape")
                and element["shape"].get("shapeType") == "TEXT_BOX"
                and element["shape"].get("text")
                and element["shape"]["text"].get("textElements")
            ):
                text_elements = element["shape"]["text"]["textElements"]
                for index, text_element in enumerate(text_elements):
                    if (
                        text_element.get("textRun")
                        and text_element["textRun"].get("content").strip()
                        == replace_text
                    ):
                        requests.append(
                            {
                                "replaceAllText": {
                                    "containsText": {
                                        "text": replace_text,
                                        "matchCase": True,
                                    },
                                    "replaceText": replace_with,
                                    # "objectId": element["objectId"],
                                }
                            }
                        )

        if requests:
            logging.info("Sending requests: %s", requests)
            body = {"requests": requests}
            service.presentations().batchUpdate(
                presentationId=presentation_id, body=body
            ).execute()

    except Exception as e:
        error_message = f"Error in gslides_update_slide: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_get_slide_content(presentation_id: str, slide_id: str):
    """
    Retrieves the content of a slide in a presentation.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_id: The ID of the slide.
    :type slide_id: string
    :return: The content of the slide.
    :rtype: dict
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        slide = (
            service.presentations()
            .pages()
            .get(presentationId=presentation_id, pageObjectId=slide_id)
            .execute()
        )

        return str(slide)
    except Exception as e:
        error_message = (
            f"Error in gslides_get_slide_content: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message

@utils.function_info
def gslides_delete_slide(presentation_id: str, slide_id: str):
    """
    Deletes a specific slide from a presentation.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_id: The ID of the slide to be deleted.
    :type slide_id: string
    :return: None
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        requests = [{"deleteObject": {"objectId": slide_id}}]
        body = {"requests": requests}
        service.presentations().batchUpdate(
            presentationId=presentation_id, body=body
        ).execute()
    except Exception as e:
        error_message = f"Error in gslides_delete_slide: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_get_speaker_notes(presentation_id: str, slide_id: str):
    """
    Retrieves the speaker notes for a specific slide.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_id: The ID of the slide.
    :type slide_id: string
    :return: The speaker notes of the slide.
    :rtype: string
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        slide = (
            service.presentations()
            .pages()
            .get(presentationId=presentation_id, pageObjectId=slide_id)
            .execute()
        )
        speaker_notes = (
            slide.get("slideProperties", {})
            .get("notesPage", {})
            .get("notesProperties", {})
            .get("speakerNotesObjectId", "")
        )
        return speaker_notes
    except Exception as e:
        error_message = (
            f"Error in gslides_get_speaker_notes: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_update_speaker_notes(
    presentation_id: str, slide_id: str, speaker_notes: str
):
    """
    Updates the speaker notes for a specific slide.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_id: The ID of the slide.
    :type slide_id: string
    :param speaker_notes: The new speaker notes string.
    :type speaker_notes: string
    :return: None
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        requests = [
            {
                "insertText": {
                    "objectId": slide_id,
                    "insertionIndex": 0,
                    "text": speaker_notes,
                }
            }
        ]
        body = {"requests": requests}
        service.presentations().batchUpdate(
            presentationId=presentation_id, body=body
        ).execute()
    except Exception as e:
        error_message = (
            f"Error in gslides_update_speaker_notes: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_duplicate_slide(presentation_id: str, slide_id: str, insertion_index: int):
    """
    Duplicates a specific slide within the presentation.

    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_id: The ID of the slide to be duplicated.
    :type slide_id: string
    :param insertion_index: The index at which the duplicated slide should be inserted.
    :type insertion_index: number
    :return: The ID of the new duplicated slide.
    :rtype: string
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        requests = [
            {
                "duplicateObject": {
                    "objectId": slide_id,
                    "insertionIndex": insertion_index,
                }
            }
        ]
        body = {"requests": requests}
        response = (
            service.presentations()
            .batchUpdate(presentationId=presentation_id, body=body)
            .execute()
        )
        new_slide_id = response.get("replies")[0].get("duplicateObject").get("objectId")
        return new_slide_id
    except Exception as e:
        error_message = (
            f"Error in gslides_duplicate_slide: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gslides_reorder_slides(presentation_id: str, slide_ids: list, insertion_index: int):
    """
    Changes the order of slides within the presentation.
    :param presentation_id: The ID of the presentation.
    :type presentation_id: string
    :param slide_ids: The list of slide IDs to be reordered.
    :type slide_ids: string
    :param insertion_index: The index at which the reordered slides should be inserted.
    :type insertion_index: number
    :return: None
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        requests = [
            {
                "updateSlidesPosition": {
                    "slideObjectIds": slide_ids,
                    "insertionIndex": insertion_index,
                }
            }
        ]
        body = {"requests": requests}
        service.presentations().batchUpdate(
            presentationId=presentation_id, body=body
        ).execute()
    except Exception as e:
        error_message = (
            f"Error in gslides_reorder_slides: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message
