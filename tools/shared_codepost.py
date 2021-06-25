"""
shared_codepost.py
Shared methods for codePost.
"""

__all__ = [
    # globals
    'DUMMY_GRADER',
    'TIER_FORMAT', 'TIER_PATTERN',

    # methods
    'log_in_codepost',
    'get_course', 'get_assignment',
    'course_str',
    'validate_grader', 'validate_student',
]

# ===========================================================================

import re
from typing import (
    Tuple,
    Optional,
)

import codepost
from loguru import logger

from shared import *

# ===========================================================================

# globals

DUMMY_GRADER = 'jdlou+dummygrader@princeton.edu'

# tier format
TIER_FORMAT = '\\[T{tier}\\] {text}'
TIER_PATTERN = re.compile(r'\\\[T(\d+)\\]')


# ===========================================================================

def log_in_codepost(log: bool = False
                    ) -> bool:
    """Logs in to codePost using the YAML config file.

    Args:
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        bool: Whether the login was successful.
    """

    if log: logger.info('Logging in to codePost')

    config = codepost.read_config_file()
    if config is None:
        msg = 'codePost config file not found in directory'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return False
    if 'api_key' not in config:
        msg = 'codePost config file does not contain an API key'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return False
    codepost.configure_api_key(config['api_key'])
    return True


# ===========================================================================

def get_course(name: str,
               period: str,
               log: bool = False
               ) -> Tuple[bool, Optional[Course]]:
    """Gets a course from codePost.
    If there are duplicates, returns the first one found.

    Args:
        name (str): The name of the course.
        period (str): The period of the course.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Tuple[bool, Optional[Course]]:
            If the retrieval was successful, returns True and the course.
            If the retrieval was unsuccessful, returns False and None.
    """

    if log: logger.info('Getting course "{} - {}"', name, period)

    # specifying the name and period in `list_available()` works,
    # but empty strings are ignored so it doesn't work for this method
    for course in codepost.course.list_available():
        if course.name == name and course.period == period:
            return True, course

    msg = f'No course found with name "{name}" and period "{period}"'
    if not log: raise ValueError(msg)
    logger.error(msg)
    return False, None


# ===========================================================================

def get_assignment(course: Course,
                   assignment_name: str,
                   log: bool = False
                   ) -> Tuple[bool, Optional[Assignment]]:
    """Get an assignment from a course.

    Args:
         course (Course): The course.
         assignment_name (str): The name of the assignment.
         log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Tuple[bool, Optional[Assignment]]:
            If the retrieval was successful, returns True and the assignment.
            If the retrieval was unsuccessful, returns False and None.
    """

    for assignment in course.assignments:
        if assignment.name == assignment_name:
            return True, assignment

    msg = f'Assignment "{assignment_name}" not found'
    if not log: raise ValueError(msg)
    logger.error(msg)
    return False, None


# ===========================================================================

def course_str(course: Course,
               delim: str = ' '
               ) -> str:
    """Returns a str representation of a course.

    Args:
        course (Course): The course.
        delim (str): The deliminating str between the name and the period.
            Default is a space.

    Returns:
        str: The str representation.
    """
    return f'{course.name}{delim}{course.period}'


# ===========================================================================

def validate_grader(course: Course,
                    grader: str,
                    log: bool = False,
                    ) -> bool:
    """Validates a grader for a course.

    Args:
        course (Course): The course.
        grader (str): The grader email.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        bool: Whether the grader is a valid grader in the course.
    """

    if grader in codepost.roster.retrieve(course.id).graders:
        return True
    msg = f'Invalid grader "{grader}" in {course_str(course)}'
    if not log: raise ValueError(msg)
    logger.error(msg)
    return False


def validate_student(course: Course,
                     student: str,
                     log: bool = False,
                     ) -> bool:
    """Validates a student for a course.

    Args:
        course (Course): The course.
        student (str): The student email.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        bool: Whether the student is a valid student in the course.
    """

    if student in codepost.roster.retrieve(course.id).students:
        return True
    msg = f'Invalid student "{student}" in {course_str(course)}'
    if not log: raise ValueError(msg)
    logger.error(msg)
    return False

# ===========================================================================
