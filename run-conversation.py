from ylb import config
from ylb.llm import ConversationManager

# Assume the necessary imports are made for the tools you mentioned:
from ylb.helpers.file import create_file, edit_file, read_file
from ylb.helpers.folder import list_folder, create_folder
from ylb.helpers.os import execute_bash_command
from ylb.helpers.gdrive import (
    gdrive_find_file,
    gdrive_read_file,
    gdrive_upload_file,
    gdrive_upload_document,
    gdrive_upload_spreadsheet,
    gdrive_move_file_to_folder,
    gdrive_list_files,
    gdrive_share_file,
    gdrive_create_folder,
)
from ylb.helpers.gsheets import gsheets_read_spreadsheet, gsheets_write_spreadsheet
from ylb.helpers.gslides import (
    gslides_create_presentation,
    gslides_open_presentation,
    gslides_get_slide_content,
    gslides_create_slide,
    gslides_update_slide,
    gslides_delete_slide,
    gslides_duplicate_slide,
    gslides_reorder_slides,
    gslides_get_speaker_notes,
    gslides_update_speaker_notes,
)
from ylb.helpers.openai import (
    openai_read_file_into_vector_store,
    openai_get_vector_store_file_ids,
    openai_update_assistant_vector_store,
    openai_update_assistant_code_interpreter,
)

from ylb.cortex.memory import remember, recall, list_short_memory, list_reminders

from ylb.helpers.audio import speak, listen


if __name__ == "__main__":
    tools = [
        create_file,
        edit_file,
        read_file,
        execute_bash_command,
        list_folder,
        create_folder,
        listen,
        speak,
        # remember,
        # recall,
        # list_short_memory,
        # list_reminders,
        gdrive_list_files,
        gdrive_find_file,
        gdrive_move_file_to_folder,
        gdrive_read_file,
        gdrive_create_folder,
        gdrive_upload_file,
        gdrive_upload_document,
        gdrive_upload_spreadsheet,
        gdrive_share_file,
        gslides_create_presentation,
        gslides_open_presentation,
        gslides_create_slide,
        gslides_update_slide,
        gslides_get_slide_content,
        gslides_delete_slide,
        gslides_duplicate_slide,
        gslides_reorder_slides,
        gslides_get_speaker_notes,
        gslides_update_speaker_notes,
        gsheets_read_spreadsheet,
        gsheets_write_spreadsheet,
        openai_read_file_into_vector_store,
        openai_get_vector_store_file_ids,
        # openai_update_assistant_vector_store,
        openai_update_assistant_code_interpreter,
    ]
    conversation = ConversationManager(
        tools=tools,
        #         prompt="""We (Alex and Neil) are working on reviewing site survey videos of upcoming covered properties we will be adding under `ProdigyLink` company on Guardian Property Systems. We need to determine the number of gateways needed for each new property and note the physical location of each gateway.
    )

    conversation.run()
