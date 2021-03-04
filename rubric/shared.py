"""
shared.py
Shared methods.
"""

__all__ = [
    'log_in_codepost', 'set_up_service_account',
    'get_course', 'get_126_course', 'make_email', 'validate_grader', 'get_assignment',
    'open_sheet', 'add_temp_worksheet',
]

# ===========================================================================

import os
from loguru import logger
import codepost
# to get rid of error messages
from codepost.models import (courses, assignments)
import gspread

# ===========================================================================

SERVICE_ACCOUNT_FILE = 'service_account.json'


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


def set_up_service_account() -> gspread.Client:
    """Sets up the Google service account to connect with Google Sheets.

    Returns:
        gspread.Client: The client.
            Returns None if unsuccessful.
    """

    g_client = None
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        g_client = gspread.service_account(SERVICE_ACCOUNT_FILE)
    else:
        logger.critical('"{}" file not found in directory', SERVICE_ACCOUNT_FILE)
    return g_client


# ===========================================================================

def get_course(name, period) -> codepost.models.courses.Courses:
    """Gets a course from codePost.
    If there are duplicates, returns the first one found.

    Args:
        name (str): The name of the course.
        period (str): The period of the course.

    Returns:
        codepost.models.courses.Courses: The course.
            Returns None if unsuccessful.
    """

    course = None
    courses = codepost.course.list_available(name=name, period=period)
    if len(courses) == 0:
        logger.critical('No course found with name "{}" and period "{}"', name, period)
    else:
        course = courses[0]
    return course


def get_126_course(period) -> codepost.models.courses.Courses:
    """Gets a COS126 course from codePost.
    If there are duplicates, returns the first one found.

    Args:
        period (str): The period of the course.

    Returns:
        codepost.models.courses.Courses: The course.
            Returns None if unsuccessful.
    """

    return get_course('COS126', period)


# ===========================================================================

def course_str(course) -> str:
    """Returns a str representation of a course.

    Args:
        course (codepost.models.courses.Courses): The course.

    Returns:
        str: The str representation.
    """
    return f'{course.name} {course.period}'


# ===========================================================================

def make_email(netid) -> str:
    """Turns a potential netid into an email.

    Args:
        netid (str): The netid.

    Returns:
        str: The email.
    """

    if netid.endswith('@princeton.edu'):
        return netid
    return netid + '@princeton.edu'


def validate_grader(course, grader) -> bool:
    """Validates a grader for a course.

    Args:
        course (codepost.models.courses.Courses): The course.
        grader (str): The grader. Accepts netid or email.
    """

    grader = make_email(grader)
    validated = grader in codepost.roster.retrieve(course.id).graders
    if not validated:
        logger.error('Invalid grader in {}: "{}"', course_str(course), grader)
    return validated


# ===========================================================================

def get_assignment(course, a_name) -> codepost.models.assignments.Assignments:
    """Get an assignment from a course.

    Args:
         course (codepost.models.courses.Courses): The course.
         a_name (str): The name of the assignment.

    Returns:
        codepost.models.assignments.Assignments: The assignment.
            Returns None if no assignment exists with that name.
    """

    assignment = None
    for a in course.assignments:
        if a.name == a_name:
            assignment = a
            break
    if assignment is None:
        logger.critical('Assignment "{}" not found', a_name)
    return assignment


# ===========================================================================

def open_sheet(g_client, sheet_name) -> gspread.models.Spreadsheet:
    """Opens a Google Sheet.

    Args:
        g_client (gspread.Client): The Client used.
        sheet_name (str): The name of the sheet to open.

    Returns:
        gspread.models.Spreadsheet: The spreadsheet.
            Returns None if unsuccessful.
    """
    sheet = None
    try:
        sheet = g_client.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        logger.critical('Spreadsheet "{}" not found', sheet_name)
    return sheet


# ===========================================================================

def add_temp_worksheet(sheet, title='temp', rows=1, cols=1, index=None) -> gspread.models.Worksheet:
    """Adds a temp worksheet to a sheet.

    Args:
        sheet (gspread.models.Spreadsheet): The sheet.
        title (str): The title of the temp worksheet.
            Default is 'temp'. Will add numbers if the name already exists.
        rows (int): The number of rows.
            Default is 1.
        cols (int): The number of cols.
            Default is 1.
        index (int): The index where the temp worksheet should go.
            Default is None.

    Returns:
        gspread.models.Worksheet: The temp worksheet.
    """

    try:
        return sheet.add_worksheet(title, rows, cols, index)
    except gspread.exceptions.APIError:
        pass
    count = 1
    while True:
        try:
            return sheet.add_worksheet(f'{title}{count}', rows, cols, index)
        except gspread.exceptions.APIError:
            count += 1

# ===========================================================================
