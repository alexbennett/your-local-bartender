from ga import config
from ga.llm import ConversationManager

# Assume the necessary imports are made for the tools you mentioned:
from ga.helpers.file import create_file, edit_file, read_file
from ga.helpers.folder import list_folder, create_folder
from ga.helpers.os import execute_bash_command
from ga.helpers.gdrive import (
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
from ga.helpers.gsheets import gsheets_read_spreadsheet, gsheets_write_spreadsheet
from ga.helpers.gslides import (
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
from ga.helpers.slack import (
    slack_read_messages_from_channel,
    slack_send_message_to_channel,
    slack_read_messages_from_user,
    slack_send_message_to_user,
    slack_list_channels,
    slack_list_users,
)
from ga.helpers.gps import (
    gps_api_add_thing,
    gps_api_create_location,
    gps_api_get_companies,
    gps_api_get_locations,
    gps_api_get_things,
    gps_api_get_user_id_by_email,
    gps_api_get_thing_by_hardware_id,
    gps_api_get_readings_for_thing,
    gps_api_get_rules_for_thing,
    gps_api_get_rules_for_location,
    gps_api_get_rule_ids_for_location,
    gps_api_get_rule,
    gps_api_delete_user_email_notifications_for_rule,
    gps_api_delete_user_sms_notifications_for_rule,
    gps_api_update_rule,
    gps_api_rename_thing,
    gps_api_search_users,
    gps_api_search_thing_by_name,
)
from ga.helpers.openai import (
    openai_read_file_into_vector_store,
    openai_get_vector_store_file_ids,
    openai_update_assistant_vector_store,
    openai_update_assistant_code_interpreter,
)

from ga.cortex.memory import remember, recall, list_short_memory, list_reminders

from ga.helpers.audio import speak, listen


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
        slack_list_users,
        slack_list_channels,
        slack_send_message_to_user,
        slack_read_messages_from_user,
        slack_send_message_to_channel,
        slack_read_messages_from_channel,
        gps_api_get_companies,
        gps_api_get_locations,
        gps_api_get_things,
        gps_api_get_thing_by_hardware_id,
        gps_api_get_readings_for_thing,
        gps_api_get_rules_for_thing,
        gps_api_get_rules_for_location,
        gps_api_get_rule_ids_for_location,
        gps_api_get_rule,
        gps_api_delete_user_email_notifications_for_rule,
        gps_api_delete_user_sms_notifications_for_rule,
        gps_api_update_rule,
        gps_api_search_thing_by_name,
        gps_api_search_users,
        gps_api_get_user_id_by_email,
        gps_api_add_thing,
        gps_api_create_location,
        gps_api_rename_thing,
        openai_read_file_into_vector_store,
        openai_get_vector_store_file_ids,
        # openai_update_assistant_vector_store,
        openai_update_assistant_code_interpreter,
    ]
    conversation = ConversationManager(
        tools=tools,
        #         prompt="""We (Alex and Neil) are working on reviewing site survey videos of upcoming covered properties we will be adding under `ProdigyLink` company on Guardian Property Systems. We need to determine the number of gateways needed for each new property and note the physical location of each gateway.
        # Background information:
        # A gateway may be 'hidden', ie installed in an electrical closet or similar location, or 'exposed', ie installed in a hallway or communal area. We also need to determine the number of leak detectors needed per unit within the property, and the room specific assignments. From this information we will extrapolate the number of leak detector security cases required, and the number of gateway security boxes required. Gateway security boxes are required for exposed gateways only. Leak detector security cases are required for all leak detectors unless specifically noted otherwise. Leak detectors may be installed with screws or adhesive according to the material within each room of the property. If screws are used, 2 are required. If adhesive is used, 4 pieces are required.
        # Each gateway security box requires the following materials:
        # - 1x 1/2 inch IP68 strain relief NPT cable gland
        # - 1x single-gang IP66 weatherproof electrical box
        # - 1x 6 inch RP-SMA male to RP-SMA female extension cable
        # - 2x 3/4 inch adhesive zip tie anchor
        # - 4x 6 inch zip tie
        # - 5ft 1/4 inch split wire conduit
        # - 1x 7.9x7.9x3.1 inch IP65 electrical project box enclosure
        # - 1x 2 inch hook and loop fastener
        # Each leak detector security case requires the following:
        # - 4530 seconds of 3D printing for the main shell
        # - 39.75 grams of PLA plastic (13.315 meters of 1.75mm filament) for the main case
        # - 588 seconds of printer for the probe cap
        # - 2.36 grams of PLA plastic (0.79 meters of 1.75mm filament) for the main case
        # - 2x pogo pins for the probe cap
        # - 2x bottom pins for the probe cap
        # - 2x wire pieces for the probe cap
        # - Unknown minutes of assembly time for the entire case
        # Here are a few notes we took during the recording of the site survey videos:
        # O’Farrell Towers
        # - Number of Floors: 12
        # - Number of Units: 101 residential, 1 commercial
        # - Number of Gateways: 6-7
        # - Common Area Rooms: 1 common room, 6 laundry rooms
        # - Staff Bathroom: 1
        # - Location for Gateways: Laundry rooms or hallways
        # Buena Vista Terrace
        # - Number of Units: (not specified)
        # - Number of Floors: 4
        # - Number of Gateways: 2-3
        # - Common Area Rooms: 1
        # - Staff Bathroom: 1 on 1st floor
        # - Location for Gateways: Telecom rooms
        # - General notes: Poor cellular service
        # 939-951 Eddy Street Apartments
        # - Buildings: 2 separate buildings
        # - Number of Units: (not specified)
        # - Number of Floors: 4
        # - Number of Gateways: 4-5
        # - Common Area Rooms: 2 laundry rooms
        # - Staff Bathroom: 1 in 951 building
        # - Location for Gateways: Hallways
        # Turk and Eddy Street Apartments (249 Eddy St)
        # - Number of Units: 55
        # - Number of Floors: 7
        # - Number of Gateways: 3
        # - Common Area Rooms: 2
        # - Staff Bathrooms: 2
        # - Location for Gateways: Hallways
        # Turk and Eddy Street Apartments (165 Turk St)
        # - Number of Units: 26
        # - Number of Floors: 6
        # - Number of Gateways: 3
        # - Common Area Rooms: 1 common room, 1 laundry room
        # - Staff Bathroom: 1 (tiled)
        # - Location for Gateways: Stairwells
        # Willie B. Kennedy Apartments
        # - Number of Floors: 5 (only 4 with units)
        # - Number of Units: 98
        # - Number of Gateways: 3-4
        # - Common Area Rooms: 3, 1 laundry room
        # - Staff Bathrooms: 3
        # - Location for Gateways: Several options, check video
        # Gateway Summary
        # - O’Farrell Towers: 7
        # - Buena Vista Terrace: 3
        # - 939-951 Eddy Street Apartments: 5
        # - Turk and Eddy Street Apartments: 6
        # - Willie B. Kennedy Apartments: 4
        # Join us in conversation to help work through reviewing the site survey videos. There is no specific task or action you need to take. For now, we will only discuss and provide you with more notes. Use `speak()` anytime you need to communicate with us.
        # """,
        # prompt="I need to rename all of the sensors for the location 'Snowden Ridge' under 'ProdigyLink' company on Guardian Property Systems. Before renaming, help me verify the naming convention. The convention is currently '[building #]-[unit #] [room name] [sensor # or empty if only one sensor]'. Make sure every sensor matches this naming convention. Use `speak()` to tell me when you are finished.",
        # prompt="Generate a status report of all devices at the 'Snowden Ridge' location under 'ProdigyLink' company on Guardian Property Systems. Open the Google Slides presentation with ID '1NqmrrkByU_azK7WmYxz8lpnY7Uq8XbNyAT20xWPnWY0' for updating. The goal of this presentation is to summarize the completion of rolling out Guardian Property Systems services to the new location. Add a slide containing a summary of the number of gateways and devices installed. Add a slide with more detail about gateways specifically, including the gateway names. Next, create a new slide for each unique room in the location as inferred from all sensor names. In the slide for the room, include the following data for each contained sensor: name, hardware id, temperature, tampered, top/bottom status, last updated. Use `speak()` to keep me updated on your progress. Be brief when speaking. The information you add to the slides should be verbose. Do not forget any devices and gateways and do not leave information incomplete in the presentation. Provide an example of the data you will add to the slides before you begin.",
        # prompt="Analyze the `gslides.py` file in code interpreter. This is the source code for your Google Slides tool integration. Next, experiement by using tool calls to the Google Slides API. Modify the presentation with ID `13Fb5UhHbEcxS_W7uAMM2OKd0dllA2QiBSfZ_XS8Zlk4`. Before calling any functions, formulate a plan to systematically test each of them to verify the correct response. For example, your first test should be adding a new slide with demo content. Another test should attempt to duplicate a slide that has existing content, then you should check that the slide exists. Use `speak()` to tell me your plan BEFORE you begin testing.",
        # prompt="First get the Google Slides presentation with ID `13Fb5UhHbEcxS_W7uAMM2OKd0dllA2QiBSfZ_XS8Zlk4`. Next, upload the local file `./presentation.txt` to your vector store. Use code interpreter to analyze the file, then add 3 new slides, each containing different content including a title and 2 sentences in the body. Write the entire updated file to `./presentation2.json`. Use `speak()` to tell me when you are finished.",
        # prompt="Get all gateway devices for all locations under 'ProdigyLink' company on Guardian Property Systems. Compare the names of all gateways and generate a report on the different naming conventions used. Use `speak()` to tell me when you are finished.",
        # prompt="Get all gateway devices for all locations under 'ProdigyLink' company on Guardian Property Systems. Then grab the rules for each gateway. Generate a report that includes the last time each rule was triggered and summarize the result. Send the report to Slack channel '#gwen' and include that you are generating this report from the request of @alex. Use `speak()` to tell me when you are finished.",
        # prompt="Let's work on combining two projects I am working on. First, upload the file `/Users/alex/Documents/Github_Repositories/guardian-assistant/to-upload/bartender.py` to your vector store. Next, upload the file `/Users/alex/Documents/Github_Repositories/guardian-assistant/run-conversation.py` to your vector store. The goal will be to combine the usage of `ConversationManager` as demonstrated in `run-conversation.py` into the `>join` command of the `bartender.py` program. Begin by using code interpreter to analyze both files. Next, formulate a plan to create a new file called `bartender2.py` that contains the combined functionality. Describe your plan to me in detail. We will discuss good and bad parts together before you create the final file. You must obtain permission from me before generating the final file. Always use `speak()` to communicate with me. Let's get started!",
        # prompt="Grab all LWGLD1 DevEUIs from the Google Sheet `1IZga0io_yyyPTnfgZJmRt5fy11Y98CN34mjlB4mSP08`. This sheet contains a list of scanned LWGLD1 devices or 'things' in our office. We need to add all of the devices to GPS via the API to figure out what devices are good and bad. Attempt to add every DevEUI from this spreadsheet to the 'KY Office' location under the company `Elexa Consumer Products, Inc.` in Guardian Property Systems. Record the result of each attempt and create a summary report of all of the devices that succeeded and failed to be added, including the reason for the failure. Use `speak()` to tell me how many devices you will attempt to add when you are ready to proceed. Finally, tell me when you are finished and include a summary of the results.",
        # prompt="Open the 'Test Presentation' Google Slides document from Google Drive. Then modify it by adding a new slide with a funny joke about a sea sponge and sea star sitting on a beach.",
        # prompt="Upload the file `./tests/test_gdrive.py` to your vector store. Next, analyze the file in code interpreter. Formulate a plan to prepare the test for running, for example you may need to create files for the test suite to use. Store them in `tests/test_files/`. Use `speak()` to tell me when you are finished and ask if I would like to proceed with the changes. If yes, output the updated file to `./tests/test_gdrive.py`.",
        # prompt="Upload the file `./ga/helpers/gslides.py` to your vector store. Next, analyze the file in code interpreter and consider the next most logical functions to add to the file. For example, there may need to be a function to delete a slide or get the speaker notes for a slide. Return no fewer than 5 improvements. Use `speak()` to tell me when you are finished and ask if I would like to proceed with the changes. If yes, output the updated file to `./ga/helpers/glides-v2.py`."
        # prompt="Upload the file `./ga/helpers/gslides.py` to your vector store. DO NOT DELETE OR CREATE THE FILE FIRST. IT ALREADY EXISTS. Next, analyze the file in code interpreter and create a full test suite to test all available funtions. Output the test suit to `./tests/test_gslides.py`.",
        # prompt="Analyze `llm.py` and suggest improvements to the `ConversationManager` class. Use `speak()` to tell me when you are finished. Provide a summary of the changes made."
        # prompt="You are an expert electronics designer and specialize in digital circuits and PCB design. Analyze the contents of the `board.txt` and `schematic.txt` files in your memory and create a presentation in Google Slides to summarize the key points. Use this existing Google Slides project: `13Fb5UhHbEcxS_W7uAMM2OKd0dllA2QiBSfZ_XS8Zlk4`. Use `speak()` to tell me when you are finished."
        # prompt="Test your ability to work on Google Sheets. You can find the source code in `ga/helper/gsheets.py` and test file in `tests/test_gsheets.py`. Test the system by creating a spreadsheet to calculate the cost of running a 3D printer. After completition, review the spreadsheet for accuracy and fix any issues. Formulate your plan and explain it before proceeding. Use `speak()` to tell me.",
    )

    conversation.run()
