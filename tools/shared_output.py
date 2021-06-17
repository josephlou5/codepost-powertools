"""
shared_output.py
Shared methods for output.
"""

__all__ = [
    # methods
    'get_path',
    'validate_file',
]

# ===========================================================================

import os
from typing import (
    Sequence, Tuple,
    Union,
)

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
    """Gets the path "output/[course]/[assignment]/[folder]/[file]".
    If either of `course` or `assignment` is None, neither will be included.

    Args:
        file (str): The file.
            Default is None.
        course (Course): The course.
            Default is None.
        assignment (Assignment): The assignment.
            Default is None.
        folder (str): The output folder.
            Default is `OUTPUT_FOLDER`.
        create (bool): Whether to create missing directories.
            Default is True.

    Returns:
        str: The path of the file.
    """

    path = OUTPUT_FOLDER
    if create and not os.path.exists(path):
        os.mkdir(path)

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

def validate_file(file: str,
                  folder: str = OUTPUT_FOLDER,
                  exts: Sequence[str] = DEFAULT_EXTS,
                  log: bool = False
                  ) -> Union[Tuple[str, str], Tuple[None, None]]:
    """Validates a file.

    Args:
        file (str): The file to validate.
        folder (str): The output folder.
            Default is `OUTPUT_FOLDER`.
        exts (Sequence[str]): The valid extensions.
            Default is `DEFAULT_EXTS`.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Union[Tuple[str, str], Tuple[None, None]]:
            If the validation is successful, returns the filepath and the file extension.
            If the validation is unsuccessful, returns None and None.
    """

    # check file existence
    filepath = file
    if not os.path.exists(filepath):
        filepath = os.path.join(folder, filepath)
        if not os.path.exists(filepath):
            msg = f'File "{file}" not found'
            if not log: raise RuntimeError(msg)
            logger.error(msg)
            return None, None

    # check file extension
    _, ext = os.path.splitext(filepath)
    if ext not in exts:
        msg = f'Unsupported file type "{ext}"'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return None, None

    return filepath, ext

# ===========================================================================
