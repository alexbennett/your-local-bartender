#!/usr/bin/env python3
#
# Copyright (C) 2020 Elexa Consumer Product, Inc.
#
# This file is part of the Guardian Ecosystem.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import math


class Config:
    DEFAULT_COL_WIDTH = 80
    DEFAULT_TITLE_DECORATOR = "▬"  # ▬
    DEFAULT_SECTION_DECORATOR = "-"  # ▬
    DEFAULT_SECTION_START_DECORATOR = "-"
    DEFAULT_BAR_DECORATOR = "▬"
    DEFAULT_HEADER_DECORATOR = "="
    DEFAULT_FILLCHAR = "="
    DEFAULT_INPUT_BAR_DECORATOR = "╍"


# Console output colors
class TextColor:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    GRAY = "\033[1;30;40m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_newline(count: int = 1):
    for x in range(0, count):
        print()


def print_waiting_for_enter():
    input("Press enter to continue...")


def print_bar(
    decorator: str = Config.DEFAULT_BAR_DECORATOR,
    cols: int = Config.DEFAULT_COL_WIDTH,
    color: str = "",
):
    print(color + "".join([decorator * cols]))


def print_request_option():
    option = input("Choose an option by number: ")
    try:
        option = int(option)
    except:
        option = -1
    return option


def print_centered(text: str, decorator: str = None):
    if decorator is None:
        print(text.center(Config.DEFAULT_COL_WIDTH))
    else:
        text = " " + text + " "  # add whitespace to start & end
        print(text.center(Config.DEFAULT_COL_WIDTH, decorator))


def print_title(
    text: str, color: str = "", pretext: str = "", reset_color: bool = True
):
    print_newline()
    # print_bar(color=color, decorator="-")
    if len(pretext):
        pretext = " " + pretext  # add whitespace at start
    text = " " + text  # add whitespace at start
    if reset_color:
        text = text + TextColor.ENDC
    print(color + pretext + TextColor.BOLD + text)
    print_bar(color=color, decorator=Config.DEFAULT_TITLE_DECORATOR)


def print_section(text: str, color: str = "", depth: int = 1, reset_color: bool = True):
    text = Config.DEFAULT_SECTION_START_DECORATOR * depth + "> " + text + " "
    text_length = len(text)
    decorators = Config.DEFAULT_SECTION_DECORATOR * (
        Config.DEFAULT_COL_WIDTH - text_length
    )
    text = TextColor.BOLD + color + text + decorators
    if reset_color:
        text = text + TextColor.ENDC
    print(text)
    print_newline()


def make_instruction(text: str):
    return " ► " + text + TextColor.ENDC


def make_whisper(text: str):
    return TextColor.GRAY + text + TextColor.ENDC


def make_shout(text: str, color: TextColor = TextColor.WARNING):
    return color + " ★ " + TextColor.UNDERLINE + text + TextColor.ENDC


def apply_color(color, text):
    """
    Apply ANSI color codes to text.

    :param color: The color code to apply. Example: "green", "red", "blue", etc.
    :param text: The text to colorize.
    :return: Colorized text with ANSI escape codes.
    """
    color_codes = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "reset": "\033[0m",
        "bold": "\033[1m",
        "fail": "\033[91m",  # Bright Red
    }

    # Check if the requested color exists, default to reset if not found
    color_code = color_codes.get(color.lower(), color_codes["reset"])

    return f"{color_code}{text}{color_codes['reset']}"


def make_bold(
    text: str, followup: str = None, color: str = "", reset_color: bool = True
):
    text = TextColor.BOLD + color + str(text)
    if followup is not None:
        text = text + TextColor.ENDC + color + followup
    if reset_color:
        text = text + TextColor.ENDC
    return text


def print_limited(
    text: str, cols: int = Config.DEFAULT_COL_WIDTH, center: bool = False
):
    """Prints the provided text and adds a NL at after every
    'cols' characters/columns.

    :param text: Text to print.
    :type text: str
    :param cols: Column width character limit, defaults to Config.DEFAULT_COL_WIDTH
    :type limicolst: int, optional
    """
    nls = math.floor(len(text) / cols)  # number of newline characters required
    chars = list(text)  # to character list
    for x in range(0, nls):  # insert NL every Config.DEFAULT_COL_WIDTH chars
        chars.insert(Config.DEFAULT_COL_WIDTH * (x + 1), "\n")
    text = "".join(chars)
    if center:
        for line in text.split("\n"):
            print_centered(line)
    else:
        print(text)


def select_menu_item(options, title):
    """
    Display a menu with options and prompt the user to select an option.

    :param options: List of options to display.
    :param title: Title of the menu.
    :return: User's menu choice as an integer.
    """
    clear_screen()
    print_title(title)
    print_newline()
    for idx, option in enumerate(options):
        print(f"{TextColor.BOLD}  [{idx + 1}] {option}{TextColor.ENDC}")
    print_newline()
    print_bar()
    menu_choice = print_request_option()
    return menu_choice


def print_padded(text: str, padding: int = 1):
    print("".join([" " * padding]) + text)


def print_joined(items: list, separator: str = ", "):
    print(separator.join(items))


def print_list(
    items: list,
    color: str = "",
    reset_color: bool = True,
    decorator: str = "-",
    tabsize: int = 2,
):
    [
        print(
            "{color}{tab}{decorator} {item}".format(
                color=color, tab=" " * tabsize, decorator=decorator, item=item
            )
        )
        for item in items
    ]
    if reset_color:
        print(TextColor.ENDC, end="")


def convert_cell_number_to_label(cell_number, num_rows, num_cols):
    """
    Converts a cell number to the corresponding label in the format "{ROW LETTER}{COLUMN NUMBER}".
    The number of rows and columns are specified by `num_rows` and `num_cols`.
    """
    if cell_number < 1 or cell_number > num_rows * num_cols:
        raise ValueError(f"Cell number must be between 1 and {num_rows * num_cols}")

    # Define row labels (A, B, C, ...)
    row_labels = [chr(ord("A") + i) for i in range(num_rows)]

    # Calculate row and column indices
    row_index = (cell_number - 1) // num_cols
    col_index = (cell_number - 1) % num_cols + 1  # Column numbering starts from 1

    # Form the label
    label = f"{row_labels[row_index]}{col_index}"
    return label


def print_ascii_table_with_labels_and_heading(box_number, cell_number, box_layer):
    if cell_number < 1 or cell_number > 50:
        raise ValueError("Cell number must be between 1 and 50")
    if box_layer not in ["Top", "Bottom"]:
        raise ValueError("Box Layer must be 'Top' or 'Bottom'")

    # Unicode box drawing characters for bold border
    horizontal_line = "─"
    vertical_line = "│"
    bold_horizontal_line = "━"
    bold_vertical_line = "┃"
    top_left_corner = "┏"
    top_right_corner = "┓"
    bottom_left_corner = "┗"
    bottom_right_corner = "┛"
    intersection = "┼"

    num_cols = 5
    num_rows = 10

    # Cell width and content
    cell_width = 6
    cell_format = f"{{: ^{cell_width}}}"

    # Initialize the grid with empty spaces
    grid = [[cell_format.format("") for _ in range(num_cols)] for _ in range(num_rows)]

    # Fill the specified cell with 'X'
    row, col = (cell_number - 1) // num_rows, (cell_number - 1) % num_cols
    grid[row][col] = cell_format.format("█" * cell_width)

    # Row and column labels
    col_labels = ["1", "2", "3", "4", "5"]
    row_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

    # Print the heading
    heading = f" BOX #{box_number} — {box_layer.upper()} LAYER — CELL #{cell_number} / {convert_cell_number_to_label(cell_number, num_rows, num_cols)} "
    print(
        " " * (len(row_labels[0]) + 1)
        + top_left_corner
        + bold_horizontal_line * len(heading)
        + top_right_corner
    )
    print(
        " " * (len(row_labels[0]) + 1)
        + bold_vertical_line
        + heading.center(len(heading))
        + bold_vertical_line
    )
    print(
        " " * (len(row_labels[0]) + 1)
        + bottom_left_corner
        + bold_horizontal_line * len(heading)
        + bottom_right_corner
    )

    # Print column labels
    print(
        " " * len(row_labels[0])
        + " "
        + " "
        + " ".join([cell_format.format(label) for label in col_labels])
        + " "
    )
    print(
        " " * (len(row_labels[0]) + 1)
        + top_left_corner
        + (bold_horizontal_line * cell_width + "┳") * 4
        + bold_horizontal_line * cell_width
        + top_right_corner
    )

    # Print the grid with side borders and row labels
    for i, row in enumerate(grid):
        print(
            row_labels[i]
            + " "
            + bold_vertical_line
            + bold_vertical_line.join(row)
            + bold_vertical_line
        )

    # Print the bottom bold border
    print(
        " " * (len(row_labels[0]) + 1)
        + bottom_left_corner
        + (bold_horizontal_line * cell_width + "┻") * 4
        + bold_horizontal_line * cell_width
        + bottom_right_corner
    )
