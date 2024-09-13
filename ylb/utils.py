import inspect
import ast
import tiktoken
import os
import re
import textwrap


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


class Config:
    DEFAULT_COL_WIDTH = 100
    DEFAULT_TITLE_DECORATOR = "▬"  # ▬
    DEFAULT_SECTION_DECORATOR = "-"  # ▬
    DEFAULT_SECTION_START_DECORATOR = "-"
    DEFAULT_BAR_DECORATOR = "▬"
    DEFAULT_HEADER_DECORATOR = "="
    DEFAULT_FILLCHAR = "="
    DEFAULT_INPUT_BAR_DECORATOR = "╍"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_newlines(count: int = 1):
    for x in range(0, count):
        print()


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


def print_limited(
    text: str, cols: int = Config.DEFAULT_COL_WIDTH, center: bool = False
):
    """Prints the provided text and adds a NL after every 'cols' characters/columns,
    ignoring invisible characters like color codes.

    :param text: Text to print.
    :param cols: Column width character limit, defaults to Config.DEFAULT_COL_WIDTH
    :param center: Center align the text, defaults to False
    """
    # Regex to find invisible characters (e.g., ANSI color codes)
    invisible_chars = re.compile(r"(\x1b\[[0-9;]*m)")

    lines, current_line = [], ""
    current_length = 0
    for part in invisible_chars.split(text):
        if invisible_chars.match(part):
            # If it's an invisible sequence, add it without increasing the length
            current_line += part
        else:
            for char in part:
                if current_length == cols:
                    # If limit reached, append the line and reset
                    lines.append(current_line)
                    current_line, current_length = "", 0
                current_line += char
                current_length += 1

    # Add any remaining text
    if current_line:
        lines.append(current_line)

    # Print lines
    for line in lines:
        if center:
            print_centered(line)
        else:
            print(line)


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


def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    """
    Returns the number of tokens in a text string.

    :param string: The input text string.
    :type string: str
    :param encoding_name: The name of the encoding to use.
    :type encoding_name: str
    :return: The number of tokens in the text string.
    :rtype: int
    """
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


class FunctionWrapper:
    def __init__(self, func):
        """Initialize the class with function

        Args:
            func (function): Function to be analyzed
        """
        self.func = func
        self.info = self.extract_function_info()

    def extract_function_info(self):
        """Extracts and stores information about the given function"""
        source = inspect.getsource(self.func)

        # Use textwrap.dedent() to remove any extra indentation
        source = textwrap.dedent(source)
        tree = ast.parse(source)

        # Extract function name
        function_name = tree.body[0].name

        # Extract function description from docstring
        function_description = self.extract_description_from_docstring(
            self.func.__doc__
        )

        # Extract function arguments and their types
        args = tree.body[0].args
        parameters = {"type": "object", "properties": {}}
        for arg in args.args:
            argument_name = arg.arg
            if argument_name == "self":
                continue
            argument_type = self.extract_parameter_type(
                argument_name, self.func.__doc__
            )
            parameter_description = self.extract_parameter_description(
                argument_name, self.func.__doc__
            )
            parameters["properties"][argument_name] = {
                "type": argument_type,
                "description": parameter_description,
            }

        function_info = {
            "type": "function",
            "function": {
                "name": function_name,
                "description": function_description,
                "parameters": {
                    "type": "object",
                    "properties": parameters["properties"],
                    "required": list(parameters["properties"].keys()),
                },
            },
        }

        return function_info

    def extract_description_from_docstring(self, docstring):
        """Extracts description from the given docstring

        Args:
            docstring (str): Docstring of the given function
        """
        if docstring:
            lines = docstring.strip().split("\n")
            description_lines = []
            for line in lines:
                line = line.strip()
                if (
                    line.startswith(":param")
                    or line.startswith(":type")
                    or line.startswith(":return")
                ):
                    break
                if line:
                    description_lines.append(line)
            return "\n".join(description_lines)
        return None

    def extract_parameter_type(self, parameter_name, docstring):
        """Extracts parameter type from the given docstring

        Args:
            parameter_name (str): Name of the parameter
            docstring (str): Docstring of the given function
        """
        if docstring:
            type_prefix = f":type {parameter_name}:"
            lines = docstring.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith(type_prefix):
                    return line.replace(type_prefix, "").strip()
        return None

    def extract_parameter_description(self, parameter_name, docstring):
        """Extracts parameter description from the given docstring

        Args:
            parameter_name (str): Name of the parameter
            docstring (str): Docstring of the given function
        """
        if docstring:
            param_prefix = f":param {parameter_name}:"
            lines = docstring.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith(param_prefix):
                    return line.replace(param_prefix, "").strip()
        return None

    def __call__(self, *args, **kwargs):
        """Call the function with given arguments"""
        return self.func(*args, **kwargs)

    def function(self):
        """Returns the extracted function info"""
        return self.info


def function_info(func):
    return FunctionWrapper(func)
