"""
shared_output.py
Shared methods for output.
"""

__all__ = [
    # methods
    'get_path',
    'save_csv',
    'validate_file',
]

# ===========================================================================

import os
from typing import (
    Any,
    Sequence, List, Dict,
    Optional,
)

import comma
from loguru import logger

from shared import *
from shared_codepost import course_str

# ===========================================================================

# globals
OUTPUT_FOLDER = 'output'
DEFAULT_EXTS = ('.txt', '.csv')


# ===========================================================================

def get_path(file: str = None,
             course: Course = None,
             assignment: Assignment = None,
             folder: str = None,
             create: bool = True
             ) -> str:
    """Gets the path "[course]/[assignment]/[folder]/[file]".
    If either of `course` or `assignment` is None, neither will be included.

    Args:
        file (str): The file.
            Default is None.
        course (Course): The course.
            Default is None.
        assignment (Assignment): The assignment.
            Default is None.
        folder (str): The output folder.
            Default is None.
        create (bool): Whether to create missing directories.
            Default is True.

    Returns:
        str: The path of the file.
    """

    path = ''

    if course is not None and assignment is not None:
        path = os.path.join(path, course_str(course))
        if create and not os.path.exists(path):
            os.mkdir(path)
        path = os.path.join(path, assignment.name)
        if create and not os.path.exists(path):
            os.mkdir(path)

    if folder is not None:
        path = os.path.join(path, folder)
        if create and not os.path.exists(path):
            os.mkdir(path)

    if file is not None:
        path = os.path.join(path, file)

    return path


# ===========================================================================

def save_csv(data: List[Dict[str, Any]],
             filepath: str,
             description: str = 'data',
             log: bool = False
             ):
    """Saves data into a csv file.

    Args:
        data (List[Dict[str, Any]]): The data.
        filepath (str): The path of the file.
        description (str): The description of the log message.
            Default is 'data'.
        log (bool): Whether to show log messages.
            Default is False.
    """

    if log: logger.info('Saving {} to "{}"', description, filepath)
    comma.dump(data, filepath)


# ===========================================================================

def validate_file(file: str,
                  exts: Sequence[str] = DEFAULT_EXTS,
                  log: bool = False
                  ) -> Optional[str]:
    """Validates a file.

    Args:
        file (str): The file to validate.
        exts (Sequence[str]): The valid extensions.
            Default is `DEFAULT_EXTS`.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Optional[str]:
            If the validation is successful, returns the file extension.
            If the validation is unsuccessful, returns None.
    """

    # check file existence
    if not os.path.exists(file):
        msg = f'File "{file}" not found'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return None

    # check file extension
    _, ext = os.path.splitext(file)
    if ext not in exts:
        msg = f'Unsupported file type "{ext}"'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return None

    return ext

# ===========================================================================
