"""
rubric_to_sheet.py
Exports a codePost rubric to a Google Sheet.
"""

# ===========================================================================

import time
from typing import (
    List, Dict,
    Iterable,
    Union,
)

from loguru import logger

from shared import *
from shared_codepost import *
from shared_gspread import *

# ===========================================================================

HEADERS = (
    # A  B           C
    '', 'Category', 'Max',
    # D      E       F         G                 H              I               J
    'Name', 'Tier', 'Points', 'Grader Caption', 'Explanation', 'Instructions', 'Template?',
    # K           L        M    N          O
    'Instances', 'Upvote', '', 'Downvote', ''
)

TEMPLATE_YES = 'Yes'

# constants
GREEN: Color = (109, 177, 84)
WHITE: Color = (255, 255, 255)


# ===========================================================================

def get_assignment_range(course: Course,
                         start_assignment: str = None,
                         end_assignment: str = None,
                         log: bool = False
                         ) -> List[Assignment]:
    """Gets the range of assignments from a course.

    Args:
        course (Course): The course.
        start_assignment (str): The start assignment.
            Default is the first assignment.
        end_assignment (str): The end assignment (inclusive).
            Default is same as `start_assignment`.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Assignment]: The assignments.
    """

    if log: logger.info('Getting assignment range')

    assignments = sorted(course.assignments, key=lambda a: a.sortKey)
    indices = {a.name: i for i, a in enumerate(assignments)}

    first = 0
    last = 0
    if start_assignment is not None:
        first = indices.get(start_assignment, None)
        if first is None:
            msg = f'Invalid start assignment "{start_assignment}"'
            if not log: raise ValueError(msg)
            logger.error(msg)
            return list()
    if end_assignment is not None:
        last = indices.get(end_assignment, None)
        if last is None:
            msg = f'Invalid end assignment "{end_assignment}"'
            if not log: raise ValueError(msg)
            logger.error(msg)
            return list()

    if last < first:
        last = first
    return assignments[first:last + 1]


# ===========================================================================

def get_worksheets(sheet: GSpreadsheet,
                   assignments: Iterable[Assignment],
                   wipe: bool = False,
                   replace: bool = False,
                   log: bool = False
                   ) -> List[Worksheet]:
    """Gets the worksheets for the given assignments.

    Args:
        sheet (GSpreadsheet): The sheet.
        assignments (Iterable[Assignment]): The assignments.
        wipe (bool): Whether to wipe the existing sheet.
            Default is False.
        replace (bool): Whether to replace the existing sheets.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Worksheet]: The Worksheets in parallel with `assignments`.
    """

    temp = add_worksheet(sheet)

    a_worksheets = dict()

    # delete all current sheets
    if wipe:
        if log: logger.debug('Deleting existing worksheets')
        existing = sheet.worksheets()
        num_existing = len(existing)
        for _ in range(num_existing):
            sheet.del_worksheet(existing.pop())
        if log: logger.debug('Deleted all worksheets')
    # get worksheets for each assignment
    else:
        for index, worksheet in enumerate(sheet.worksheets()):
            a1 = Worksheet(worksheet).get_cell('A1').value
            if a1.isdigit():
                a_worksheets[int(a1)] = (worksheet, index)

    if log: logger.info('Finding worksheets for each assignment')

    worksheets = list()

    for assignment in assignments:
        a_id = assignment.id
        a_name = assignment.name

        this_worksheet = None

        if replace:
            if a_id in a_worksheets:
                worksheet, index = a_worksheets.pop(a_id)
                # TODO: keep existing columns rather than deleting and adding new worksheet
                # delete old worksheet
                title = worksheet.title
                sheet.del_worksheet(worksheet)
                # add new worksheet in same place
                this_worksheet = Worksheet(add_worksheet(sheet, title=title, index=index))

        if this_worksheet is None:
            # create new worksheet
            this_worksheet = Worksheet(add_worksheet(sheet, title=a_name))

        # format the sheet with default
        this_worksheet.format_cell('A1', font_family='Fira Code', update=True)

        worksheets.append(this_worksheet)

    sheet.del_worksheet(temp)

    if log: logger.debug('Found worksheets for each assignment')

    return worksheets


# ===========================================================================

def get_codepost_rubric(assignment: Assignment, log: bool = False) -> Dict[int, List]:
    """Gets the rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Dict[int, List]: The rubric comments in the format:
            { comment_id: [values] }
    """

    a_name = assignment.name

    if log: logger.debug('Getting codePost rubric for "{}" assignment', a_name)

    data = dict()

    # loop through all categories for this assignment (sorted by sortKey)
    for category in sorted(assignment.rubricCategories, key=lambda c: c.sortKey):

        # get category info
        c_name = category.name
        max_points = category.pointLimit

        if log: logger.debug('Getting rubric comments in "{}" rubric category', c_name)

        if max_points is None:
            max_points = ''
        else:
            max_points = -1 * max_points

        for comment in category.rubricComments:
            c_id = comment.id
            name = comment.name
            points = -1 * comment.pointDelta
            text = comment.text
            explanation = comment.explanation
            instruction = comment.instructionText
            template = TEMPLATE_YES if comment.templateTextOn else ''

            # get tier if has it
            match = TIER_PATTERN.match(text)
            if match is None:
                tier = ''
            else:
                tier = match.groups()[0]
                text = text[6 + len(tier):]
                # unnecessary
                tier = int(tier)

            values = [c_id, c_name, max_points, name, tier, points, text, explanation, instruction, template]

            data[c_id] = values

    if log: logger.debug('Got all rubric comments for "{}" assignment', a_name)

    return data


# ===========================================================================

def get_rubric_instances(assignment: Assignment,
                         comment_ids: Iterable[int],
                         log: bool = False
                         ) -> Dict[int, List[Union[int, float]]]:
    """Count the instances of each rubric comment in an assignment.

    Args:
        assignment (Assignment): The assignment.
        comment_ids (Iterable[int]): The rubric comment ids.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Dict[int, List[Union[int, float]]]: The instances of each rubric comment in the format:
            { comment_id: [instances, upvote, upvote %, downvote, downvote %] }
    """

    a_name = assignment.name

    if log: logger.debug('Counting instances for "{}" assignment', a_name)

    counts = {c_id: [0, 0, 0] for c_id in comment_ids}

    start = time.time()

    for submission in assignment.list_submissions():
        for file in submission.files:
            for comment in file.comments:

                # is this comment a rubric comment?
                comment_id = comment.rubricComment
                if comment_id is None:
                    continue

                counts[comment_id][0] += 1

                # feedback votes
                feedback = comment.feedback
                if feedback == 0:
                    pass
                elif feedback == 1:
                    counts[comment_id][1] += 1
                elif feedback == -1:
                    counts[comment_id][2] += 1

    end = time.time()

    # calculate percentages
    data = dict()
    for c_id, vals in counts.items():

        # no instances
        if vals[0] == 0:
            data[c_id] = [0]
            continue

        data[c_id] = [
            vals[0],
            vals[1], vals[1] / vals[0],
            vals[2], vals[2] / vals[0]
        ]

    if log: logger.debug('Counted all instances for "{}" assignment ({:.2f} sec)', a_name, end - start)

    return data


# ===========================================================================

def main(course_name: str,
         course_period: str,
         sheet_name: str,
         start_assignment: str = None,
         end_assignment: str = None,
         wipe: bool = False,
         replace: bool = False,
         count_instances: bool = False,
         log: bool = False
         ):
    """Exports a codePost rubric to a Google Sheet.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        start_assignment (str): The start assignment.
            Default is the first assignment.
        end_assignment (str): The end assignment (inclusive).
            Default is same as `start_assignment`.
        sheet_name (str): The sheet name.
        wipe (bool): Whether to wipe the existing worksheets.
            Default is False.
        replace (bool): Whether to replace the existing worksheets.
            Default is False.
        count_instances (bool): Whether to count the instances of the rubric comments.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.
    """

    success = log_in_codepost(log=log)
    if not success: return

    success, g_client = set_up_service_account(log=log)
    if not success: return

    success, course = get_course(course_name, course_period, log=log)
    if not success: return

    success, sheet = open_sheet(g_client, sheet_name, log=log)
    if not success: return

    assignments = get_assignment_range(course, start_assignment, end_assignment, log=log)

    if len(assignments) == 0:
        msg = 'No assignments to parse through'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return

    worksheets = get_worksheets(sheet, assignments, wipe=wipe, replace=replace, log=log)

    # sheet formatting
    freeze = 2
    cell_formats = [
        # header
        ('B1:2', {'bold': True, 'background_color': GREEN, 'text_color': WHITE}),
        ('B2:2', {'text_align': 'CENTER'}),
        # ids column
        ('A', {'vertical_align': 'MIDDLE'}),
    ]
    col_widths = [
        # ('B', 100),  # category name
        ('C', 50),  # max category points
        ('D', 150),  # name
        ('E', 50),  # tier
        ('F', 75),  # points
        ('G', 200),  # grader caption
        ('H', 650),  # explanation
        ('I', 300),  # instructions
        # ('J', 100),  # is template
        ('K:O', 75),  # instances columns
    ]
    # merge instances columns
    merge = ['L2:M2', 'N2:O2']
    # hide id and explanation columns
    hide_cols = ['A', 'H']

    comments = [get_codepost_rubric(assignment, log=log) for assignment in assignments]

    for assignment, worksheet, data in zip(assignments, worksheets, comments):
        a_name = assignment.name

        values = [[assignment.id, f'Assignment: {a_name}'], HEADERS, *data.values()]

        rows = len(values)
        other_rows = [(f'B3:{rows}', {'vertical_align': 'MIDDLE', 'wrap': 'WRAP'})]

        if log: logger.debug('Displaying rubric comments for "{}" assignment', a_name)

        display_on_worksheet(worksheet, values,
                             freeze=freeze, cell_formats=cell_formats + other_rows,
                             col_widths=col_widths, merge=merge, hide_cols=hide_cols)

    if log: logger.info('Displayed all rubric comments on sheet')

    if not count_instances:
        return

    if log: logger.info('Counting instances of all rubric comments')

    # instances formatting
    number_formats = [
        ('M', {'fmt_type': 'PERCENT', 'pattern': '0.0%'}),
        ('O', {'fmt_type': 'PERCENT', 'pattern': '0.0%'}),
    ]

    for assignment, worksheet, data in zip(assignments, worksheets, comments):
        a_name = assignment.name

        c_ids = list(data.keys())
        instances = get_rubric_instances(assignment, c_ids, log=log)

        values = list(instances.values())

        if log: logger.debug('Displaying instances for "{}" assignment', a_name)
        display_on_worksheet(worksheet, values, cell_range='K3', number_formats=number_formats)

    if log: logger.info('Counted instances of all rubric comments')

# ===========================================================================
