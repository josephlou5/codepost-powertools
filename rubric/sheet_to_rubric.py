"""
sheet_to_rubric.py
Imports a codePost rubric from a Google Sheet.

Requires a pre-existing course and assignments. Will replace the entire rubric.
Assignments on codePost will only be changed if it is present in the sheet.

Share sheet with
codepost-rubrics-id@codepost-rubrics.iam.gserviceaccount.com

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs

gspread API
https://gspread.readthedocs.io/en/latest/index.html
"""

"""
including short names:

dictionary of codepost short names : comment
set of all short names in sheet
option to delete or ignore codepost short names not in sheet
    difference of sets

"""

# ===========================================================================

import click
from loguru import logger
import codepost
import gspread
import time

from shared import *
from myworksheet import Worksheet

# ===========================================================================

SHEET_HEADERS = {
    # info: header title on sheet
    'category': 'Category',
    'max points': 'Max',

    'short name': 'Short Name',
    'tier': 'Tier',
    'point delta': 'Points',
    'caption': 'Grader Caption',
    'explanation': 'Explanation',
    'instructions': 'Instructions',
    'is template': 'Template?',
}

TIER_FMT = '\\[T{tier}\\] {text}'

TEMPLATE_YES = ('x', 'yes')


# ===========================================================================

def get_assignment_rubric(worksheet) -> dict:
    """Gets the rubric comments for an assignment from a worksheet.

    Args:
        worksheet (Worksheet): The Worksheet.

    Returns:
        dict: The rubric comments in the format:
            { category: (max_points, [comments]) }
    """

    rubric = dict()

    # parse the rest of the data
    values = worksheet.get_records(head=2)
    for row in values:

        # get category
        category = row.get(SHEET_HEADERS['category'], None)
        if category is None or category == '':
            continue

        if category not in rubric:
            max_points = row.get(SHEET_HEADERS['max points'], None)
            if max_points == '':
                max_points = None
            else:
                max_points = -1 * int(max_points)

            rubric[category] = (max_points, list())

        # get comment info

        # if short name does not exist, default is None
        name = row.get(SHEET_HEADERS['short name'], None)
        # if tier does not exist, do not add it
        tier = row.get(SHEET_HEADERS['tier'], None)
        # if points does not exist, default is 0
        points = -1 * row.get(SHEET_HEADERS['point delta'], 0)
        # if text does not exist, skip
        text = row.get(SHEET_HEADERS['caption'], None)
        if text is None:
            continue
        # if explanation does not exist, default is None
        explanation = row.get(SHEET_HEADERS['explanation'], None)
        # if instructions does not exist, default is None
        instructions = row.get(SHEET_HEADERS['instructions'], None)
        # if template does not exist, default is False
        template = row.get(SHEET_HEADERS['is template'], '')
        is_template = (template.lower() in TEMPLATE_YES)

        # add tier to comment text
        if tier is not None and tier != '':
            text = TIER_FMT.format(tier, text=text)

        comment = {
            'name': name,
            'text': text,
            'pointDelta': points,
            'explanation': explanation,
            'instructionText': instructions,
            'templateTextOn': is_template,
        }

        rubric[category][1].append(comment)

    return rubric


def get_all_rubric_comments(course, sheet, num_assignments=None) -> dict:
    """Gets the rubric comments for a course from a sheet.

    Args:
        course (codepost.models.courses.Courses): The course.
        sheet (gspread.models.Spreadsheet): The sheet.
        num_assignments (int): The number of assignments to get.
            Default is None. Anything other than a valid number will get all.

    Returns:
        dict: The rubric comments in the format:
            { assignment_id: { category: (max_points, [comments]) } }
    """

    logger.info('Getting info from "{}" sheet', sheet.title)

    # get the assignments to get rubrics for
    a_ids = [a.id for a in course.assignments]

    # go through the sheet and find the assignments
    data = dict()
    i = 0
    for w in sheet.worksheets():
        worksheet = Worksheet(w)

        # check assignment id in A1
        a_id = int(worksheet.get_cell('A1').value)

        if a_id in a_ids:
            a_name = codepost.assignment.retrieve(a_id).name

            logger.debug('Getting info for "{}" assignment', a_name)
            data[a_id] = get_assignment_rubric(worksheet)
            logger.debug('Got all info for "{}" assignment', a_name)
            a_ids.remove(a_id)

            i += 1
            if i == num_assignments:
                break

    logger.info('Got all info from "{}" sheet', sheet.title)

    return data


# ===========================================================================

def create_assignment_rubric(a_id, rubric, override_rubric=False):
    """Creates the rubric comments for an assignment.

    Args:
        a_id (int): The assignment id.
        rubric (dict): The rubric comments in the format:
            { category: (max_points, [comments]) }
        override_rubric (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
    """

    assignment = codepost.assignment.retrieve(a_id)
    a_name = assignment.name

    logger.debug('Creating rubric for "{}" assignment', a_name)

    # check for existing submissions
    has_submissions = len(assignment.list_submissions()) > 0
    if has_submissions:
        logger.warning('"{}" assignment has existing submissions', a_name)
        if not override_rubric:
            logger.debug('Rubric creation for "{}" assignment unsuccessful', a_name)
            return
        logger.warning('Overriding rubric')

    # delete all existing rubric comments
    logger.debug('Deleting existing rubric categories')
    for category in assignment.rubricCategories:
        logger.debug('Deleting "{}" rubric category', category.name)
        category.delete()
    logger.debug('Deleted all rubric categories')

    # create new categories
    logger.debug('Creating new rubric categories')
    for c_name, (max_points, comments) in rubric.items():

        logger.debug('Creating "{}" rubric category', c_name)

        category = codepost.rubric_category.create(
            name=c_name,
            assignment=a_id,
            pointLimit=max_points
        )
        c_id = category.id

        # create comments
        for comment in comments:
            codepost.rubric_comment.create(category=c_id, **comment)

        logger.debug('Created "{}" rubric category with {} comments', c_name, len(comments))

    logger.debug('Rubric creation for "{}" assignment successful', a_name)


def create_all_rubrics(rubrics, override_rubric=False):
    """Creates the rubric comments for a course.

    Args:
        rubrics (dict): The rubric comments in the format:
            { assignment_id: { category: (max_points, [comments]) } }
        override_rubric (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
    """

    logger.info('Creating all assignment rubrics')

    for a_id, rubric in rubrics.items():
        create_assignment_rubric(a_id, rubric, override_rubric)

    logger.info('Created all rubrics')


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('num_assignments', type=int, required=False)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@click.option('-o', '--override', is_flag=True, default=False, flag_value=True,
              help='Whether to override rubrics of assignments. Default is False.')
def sheet_to_rubric(course_period, sheet_name, num_assignments, testing, override):
    """
    Imports a codePost rubric from a Google Sheet.

    \b
    Args:
        course_period (str): The period of the COS126 course to import to.
        sheet_name (str): The name of the sheet to pull the rubrics from.
        num_assignments (int): The number of assignments to get from the sheet.
            Default is ALL. \f
        testing (bool): Whether to run as a test.
            Default is False.
        override (bool): Whether to override rubrics of assignments.
            Default is False.
    """

    start = time.time()

    logger.info('Start')

    logger.info('Logging into codePost')
    success = log_in_codepost()
    if not success:
        return

    logger.info('Setting up Google service account')
    g_client = set_up_service_account()
    if g_client is None:
        return

    logger.info('Accessing codePost course')
    if testing:
        logger.info('Running as test: Opening Joseph\'s Course')
        course = get_course("Joseph's Course", 'S2021')
    else:
        logger.info('Accessing COS126 course for period "{}"...', course_period)
        course = get_126_course(course_period)
    if course is None:
        return

    logger.info('Opening "{}" sheet', sheet_name)
    sheet = open_sheet(g_client, sheet_name)
    if sheet is None:
        return

    if testing and num_assignments is None:
        num_assignments = 1
    rubrics = get_all_rubric_comments(course, sheet, num_assignments)

    create_all_rubrics(rubrics, override)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {:.2f} sec', end - start)


# ===========================================================================

if __name__ == '__main__':
    sheet_to_rubric()
