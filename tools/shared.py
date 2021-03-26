"""
shared.py
Shared methods.
"""

__all__ = [
    # types
    'Color',
    'Course', 'Assignment', 'Submission', 'File', 'Comment',

    # globals
    'OUTPUT_FOLDER',

    # methods
    'log_in_codepost',
    'get_course', 'get_126_course', 'get_assignment',
    'course_str', 'make_email', 'validate_grader',
    'format_time',
    'validate_file',
]

# ===========================================================================
import os
from typing import (
    NewType,
    Sequence, Tuple,
    Optional, Union,
)

import codepost
from codepost.models import (courses, assignments, submissions, files, comments)
from loguru import logger

# ===========================================================================

# types
Color = Tuple[int, int, int]

Course = NewType('Course', codepost.models.courses.Courses)
Assignment = NewType('Assignment', codepost.models.assignments.Assignments)
Submission = NewType('Submission', codepost.models.submissions.Submissions)
File = NewType('File', codepost.models.files.Files)
Comment = NewType('Comment', codepost.models.comments.Comments)

# globals
OUTPUT_FOLDER = 'output'
DEFAULT_EXTS = ('.txt', '.csv')


# ===========================================================================

def log_in_codepost() -> bool:
    """Logs into codePost using the YAML config file.

    Returns:
        bool: Whether the login was successful.
    """

    config = codepost.read_config_file()
    if config is None:
        logger.critical('codePost config file not found in directory')
        return False
    if 'api_key' not in config:
        logger.critical('codePost config file does not contain an API key')
        return False
    codepost.configure_api_key(config['api_key'])
    return True


# ===========================================================================

def get_course(name: str, period: str) -> Optional[Course]:
    """Gets a course from codePost.
    If there are duplicates, returns the first one found.

    Args:
        name (str): The name of the course.
        period (str): The period of the course.

    Returns:
        Course: The course.
            Returns None if unsuccessful.
    """

    matches = codepost.course.list_available(name=name, period=period)
    if len(matches) == 0:
        logger.critical('No course found with name "{}" and period "{}"', name, period)
        return None
    return matches[0]


def get_126_course(period: str) -> Optional[Course]:
    """Gets a COS126 course from codePost.
    If there are duplicates, returns the first one found.

    Args:
        period (str): The period of the course.

    Returns:
        Course: The course.
            Returns None if unsuccessful.
    """
    return get_course('COS126', period)


# ===========================================================================

def get_assignment(course: Course, assignment_name: str) -> Optional[Assignment]:
    """Get an assignment from a course.

    Args:
         course (Course): The course.
         assignment_name (str): The name of the assignment.

    Returns:
        Assignment: The assignment.
            Returns None if unsuccessful.
    """

    for assignment in course.assignments:
        if assignment.name == assignment_name:
            return assignment

    logger.critical('Assignment "{}" not found', assignment_name)
    return None


# ===========================================================================

def course_str(course: Course, delim: str = ' ') -> str:
    """Returns a str representation of a course.

    Args:
        course (Course): The course.
        delim (str): The deliminating str between the name and the period.

    Returns:
        str: The str representation.
    """
    return f'{course.name}{delim}{course.period}'


# ===========================================================================

def make_email(netid: str) -> str:
    """Turns a potential netid into an email.

    Args:
        netid (str): The netid.

    Returns:
        str: The email.
    """

    if netid.endswith('@princeton.edu'):
        return netid
    return netid + '@princeton.edu'


def validate_grader(course: Course, grader: str) -> bool:
    """Validates a grader for a course.

    Args:
        course (Course): The course.
        grader (str): The grader. Accepts netid or email.

    Returns:
        bool: Whether the grader is a valid grader in the course.
    """

    grader = make_email(grader)
    validated = grader in codepost.roster.retrieve(course.id).graders
    if not validated:
        logger.error('Invalid grader in {}: "{}"', course_str(course), grader)
    return validated


# ===========================================================================

def format_time(seconds: float) -> str:
    """Formats seconds into minutes or higher units of time.

    Args:
        seconds (float): The number of seconds.

    Returns:
        str: The formatted time.
    """

    remaining, secs = map(int, divmod(seconds, 60))
    hrs, mins = map(int, divmod(remaining, 60))

    if remaining == 0:
        return f'{seconds:.2f} sec'

    time_str = ''
    if hrs > 0:
        time_str += f'{hrs} hr '
    if mins > 0:
        time_str += f'{mins} min '
    if secs > 0:
        time_str += f'{secs} sec '
    time_str += f'({seconds:.2f})'

    return time_str


# ===========================================================================

def validate_file(file: str,
                  output_folder: str = OUTPUT_FOLDER,
                  exts: Sequence[str] = DEFAULT_EXTS
                  ) -> Union[Tuple[None, None], Tuple[str, str]]:
    """Validates a file.

    Args:
        file (str): The file to validate.
        output_folder (str): The output folder.
            Default is `OUTPUT_FOLDER`.
        exts (Sequence[str]): The valid extensions.
            Default is `DEFAULT_EXTS`.

    Returns:
        Tuple[Optional[str], Optional[str]]: The filepath and file extension.
            Returns None, None if not found.
    """

    if file is None:
        return None, None

    # check file existence
    filepath = file
    if not os.path.exists(filepath):
        filepath = os.path.join(output_folder, filepath)
        if not os.path.exists(filepath):
            logger.error('File "{}" not found', file)
            return None, None

    # check file extension
    _, ext = os.path.splitext(filepath)
    if ext not in exts:
        logger.warning('Unsupported file type "{}"', ext)
        return None, None

    return filepath, ext

# ===========================================================================
