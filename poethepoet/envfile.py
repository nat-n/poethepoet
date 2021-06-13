from enum import Enum
import re
from typing import Dict, List, Optional, TextIO


class ParserException(ValueError):
    def __init__(self, message: str, position: int):
        super().__init__(message)
        self.message = message
        self.position = position


class ParserState(Enum):
    # Scanning for a new assignment
    SCAN_VAR_NAME = 0
    # In a value with no quoting
    SCAN_VALUE = 1
    # Inside single quotes
    IN_SINGLE_QUOTE = 2
    # Inside double quotes
    IN_DOUBLE_QUOTE = 3


def load_env_file(envfile: TextIO) -> Dict[str, str]:
    """
    Parses variable assignments from the given string. Expects a subset of bash syntax.
    """

    content_lines = envfile.readlines()
    try:
        return parse_env_file("".join(content_lines))
    except ParserException as error:
        line_num, position = _get_line_number(content_lines, error.position)
        raise ValueError(f"{error.message} at line {line_num} position {position}.")


VARNAME_PATTERN = r"^[\s\t;]*(?:export[\s\t]+)?([a-zA-Z_][a-zA-Z_0-9]*)"
ASSIGNMENT_PATTERN = f"{VARNAME_PATTERN}="
COMMENT_SUFFIX_PATTERN = r"^[\s\t;]*\#.*?\n"
WHITESPACE_PATTERN = r"^[\s\t;]*"
UNQUOTED_VALUE_PATTERN = r"^(.*?)(?:(\t|\s|;|'|\"|\\+))"
SINGLE_QUOTE_VALUE_PATTERN = r"^((?:.|\n)*?)'"
DOUBLE_QUOTE_VALUE_PATTERN = r"^((?:.|\n)*?)(\"|\\+)"


def parse_env_file(content: str):
    content = content + "\n"
    result = {}
    cursor = 0
    state = ParserState.SCAN_VAR_NAME
    var_name: Optional[str] = ""
    var_content = []

    while cursor < len(content):
        if state == ParserState.SCAN_VAR_NAME:
            # scan for new variable assignment
            match = re.search(ASSIGNMENT_PATTERN, content[cursor:], re.MULTILINE)

            if match is None:
                comment_match = re.match(COMMENT_SUFFIX_PATTERN, content[cursor:])
                if comment_match:
                    cursor += comment_match.end()
                    continue

                if (
                    re.match(WHITESPACE_PATTERN, content[cursor:], re.MULTILINE).end()  # type: ignore
                    == len(content) - cursor
                ):
                    # The rest of the input is whitespace or semicolons
                    break

                # skip any immediate whitespace
                cursor += re.match(  # type: ignore
                    r"[\s\t\n]*", content[cursor:]
                ).span()[1]

                var_name_match = re.match(VARNAME_PATTERN, content[cursor:])
                if var_name_match:
                    cursor += var_name_match.span()[1]
                    raise ParserException(
                        f"Expected assignment operator", cursor,
                    )

                raise ParserException(f"Expected variable assignment", cursor)

            var_name = match.group(1)
            cursor += match.end()
            state = ParserState.SCAN_VALUE

        if state == ParserState.SCAN_VALUE:
            # collect up until the first quote, whitespace, or group of backslashes
            match = re.search(UNQUOTED_VALUE_PATTERN, content[cursor:], re.MULTILINE)
            assert match
            new_var_content, match_terminator = match.groups()
            var_content.append(new_var_content)
            cursor += len(new_var_content)

            if match_terminator.isspace() or match_terminator == ";":
                assert var_name
                result[var_name] = "".join(var_content)
                var_name = None
                var_content = []
                state = ParserState.SCAN_VAR_NAME
                continue

            if match_terminator == "'":
                cursor += 1
                state = ParserState.IN_SINGLE_QUOTE

            elif match_terminator == '"':
                cursor += 1
                state = ParserState.IN_DOUBLE_QUOTE
                continue

            else:
                # We found one or more backslashes
                num_backslashes = len(match_terminator)
                # Keep the excess (escaped) backslashes
                var_content.append("\\" * (num_backslashes // 2))
                cursor += num_backslashes

                if num_backslashes % 2 > 0:
                    # Odd number of backslashes, means the next char is escaped
                    next_char = content[cursor]
                    var_content.append(next_char)
                    cursor += 1
                    continue

        if state == ParserState.IN_SINGLE_QUOTE:
            # collect characters up until a single quote
            match = re.search(
                SINGLE_QUOTE_VALUE_PATTERN, content[cursor:], re.MULTILINE
            )
            if match is None:
                raise ParserException(f"Unmatched single quote", cursor - 1)
            var_content.append(match.group(1))
            cursor += match.end()
            state = ParserState.SCAN_VALUE
            continue

        if state == ParserState.IN_DOUBLE_QUOTE:
            # collect characters up until a run of backslashes or double quote
            match = re.search(
                DOUBLE_QUOTE_VALUE_PATTERN, content[cursor:], re.MULTILINE
            )
            if match is None:
                raise ParserException(f"Unmatched double quote", cursor - 1)
            new_var_content, backslashes_or_dquote = match.groups()
            var_content.append(new_var_content)
            cursor += match.end()

            if backslashes_or_dquote == '"':
                state = ParserState.SCAN_VALUE
                continue

            # Keep the excess (escaped) backslashes
            var_content.append("\\" * (len(backslashes_or_dquote) // 2))

            if len(backslashes_or_dquote) % 2 == 0:
                # whatever follows is escaped
                next_char = content[cursor]
                var_content.append(next_char)
                cursor += 1

    return result


def _get_line_number(lines: List[str], position: int):
    line_num = 1
    for line in lines:
        if len(line) > position:
            break
        line_num += 1
        position -= len(line)
    return line_num, position
