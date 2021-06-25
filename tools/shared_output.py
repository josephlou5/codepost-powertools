"""
shared_output.py
Shared methods for output.
"""

__all__ = [
    # methods
    'get_path',
    'save_csv',
    'validate_file',
    'read_submissions_from_file',
]

# ===========================================================================

import os
from typing import (
    Any,
    Sequence, List, Dict,
    Optional,
)

import codepost.errors
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

def read_submissions_from_file(file: str,
                               log: bool = False
                               ) -> List[Submission]:
    """Reads submission ids from a file.

    Args:
        file (str): The file.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Submission]: The submissions.
    """

    if log: logger.info('Reading submissions from file "{}"', file)

    # validate file
    ext = validate_file(file, log=log)
    if ext is None:
        return list()

    ids = list()

    # txt file: one submission id per line
    if ext == '.txt':
        with open(file, 'r') as f:
            for line in f.read().split('\n'):
                line = line.strip()
                if line.isdigit():
                    ids.append(int(line))
    # csv file: "submission_id" column
    elif ext == '.csv':
        data = comma.load(file, force_header=True)
        S_ID_KEY = 'submission_id'
        if S_ID_KEY not in data.header:
            if log: logger.warning('File "{}" does not have a "{}" column', file, S_ID_KEY)
            return list()
        for val in data[S_ID_KEY]:
            s_id = val.strip()
            if s_id.isdigit():
                ids.append(int(s_id))

    # gets submissions
    submissions = list()
    for s_id in ids:
        try:
            submissions.append(codepost.submission.retrieve(s_id))
        except codepost.errors.NotFoundAPIError:
            if log: logger.warning('Invalid submission ID: {}', s_id)
        except codepost.errors.AuthorizationAPIError:
            if log: logger.warning('No access to submission: {}', s_id)

    if log: logger.debug('Found {} submissions', len(submissions))

    return submissions

# ===========================================================================
