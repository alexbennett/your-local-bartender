import subprocess
import logging

from ylb import utils


@utils.function_info
def execute_bash_command(command: str) -> str:
    """
    Execute a bash command and return the response.

    :param command: The bash command to execute.
    :type command: string
    :return: The response from executing the bash command.
    :rtype: string
    """
    try:
        if not command:
            return "No command provided."
        result = subprocess.check_output(
            command, shell=True, stderr=subprocess.STDOUT, text=True
        )
        logging.info(f"Executing bash command: {command}")
        return f"Result: {result}"
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing bash command: {str(e)}")
        return f"Error executing bash command: {str(e)}"
