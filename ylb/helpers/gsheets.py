import os
import logging
import traceback

from ylb import config
from ylb import utils

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_service():
    """
    Returns a service that connects to the Google Sheets API.

    :return: An instance of the Google Sheets API service.
    :rtype: service
    """
    try:
        creds = Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        error_message = f"Error in get_service: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        return error_message


@utils.function_info
def gsheets_read_spreadsheet(spreadsheet_id: str, range_name: str):
    """
    Reads data from a spreadsheet.

    :param spreadsheet_id: The ID of the spreadsheet.
    :type spreadsheet_id: string
    :param range_name: The range of cells to retrieve data from.
    :type range_name: string
    :return: A message indicating the number of rows read and the values retrieved.
             If no data is found, it returns "No data found."
    :rtype: string
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        sheet = service.spreadsheets()
        result = (
            sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        )
        values = result.get("values", [])

        if not values:
            return "No data found."
        else:
            return f"Read {len(values)} rows: {values}"
    except Exception as e:
        error_message = (
            f"Error in gsheets_read_spreadsheet: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message


@utils.function_info
def gsheets_write_spreadsheet(spreadsheet_id: str, range_name: str, values: list):
    """
    Writes data to a Google Sheets spreadsheet.

    :param spreadsheet_id: The ID of the spreadsheet.
    :type spreadsheet_id: string
    :param range_name: The range to write the data to.
    :type range_name: string
    :param values: The data to be written.
    :type values: string
    :return: A message indicating the number of cells updated.
    :rtype: string
    """
    try:
        service = get_service()
        if isinstance(service, str):  # Check if service is an error message
            return service
        body = {"values": values}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body,
            )
            .execute()
        )
        return f"{result.get('updatedCells')} cells updated."
    except Exception as e:
        error_message = (
            f"Error in gsheets_write_spreadsheet: {e}\n{traceback.format_exc()}"
        )
        logging.error(error_message)
        return error_message
