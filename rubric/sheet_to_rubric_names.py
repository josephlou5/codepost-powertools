"""
sheet_to_rubric_names.py
Imports a codePost rubric from a Google Sheet.

Requires a pre-existing course and assignments.
Will update comments with the same name and add comments not in the assignment.
Has option to delete comments on codePost that are not in the sheet.
Assignments on codePost will only be changed if it is present in the sheet.

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs

gspread API
https://gspread.readthedocs.io/en/latest/index.html
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

    'name': 'Name',
    'tier': 'Tier',
    'point delta': 'Points',
    'caption': 'Grader Caption',
    'explanation': 'Explanation',
    'instructions': 'Instructions',
    'is template': 'Template?',
}

TIER_FMT = '\\[T{tier}\\] {text}'

TEMPLATE_YES = ('x', 'yes', 'y')


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

        # if name does not exist, skip
        name = row.get(SHEET_HEADERS['name'], None)
        if name is None or name == '':
            continue
        # if tier does not exist, do not add it
        tier = row.get(SHEET_HEADERS['tier'], None)
        # if points does not exist, default is 0
        points = -1 * row.get(SHEET_HEADERS['point delta'], 0)
        # if text does not exist, skip
        text = row.get(SHEET_HEADERS['caption'], None)
        if text is None or text == '':
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
            text = TIER_FMT.format(tier=tier, text=text)

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


def get_all_rubric_comments(course, sheet, start_sheet=0, end_sheet=None) -> dict:
    """Gets the rubric comments for a course from a sheet.

    Args:
        course (codepost.models.courses.Courses): The course.
        sheet (gspread.models.Spreadsheet): The sheet.
        start_sheet (int): The index of the first sheet to pull from (0-indexed).
            Default is 0.
        end_sheet (int): The index of the last sheet to pull from (0-indexed).
            Default is the same as start_sheet.

    Returns:
        dict: The rubric comments in the format:
            { assignment_id: { category: (max_points, [comments]) } }
    """

    logger.info('Getting info from "{}" sheet', sheet.title)

    if end_sheet is None:
        end_sheet = start_sheet

    # get the assignments to get rubrics for
    a_ids = set(a.id for a in course.assignments)

    # go through the sheet and find the assignments
    data = dict()
    for index in range(start_sheet, end_sheet + 1):
        w = sheet.get_worksheet(index)
        if w is None: continue

        worksheet = Worksheet(w)

        # check assignment id in A1
        try:
            a_id = int(worksheet.get_cell('A1').value)
        except ValueError:
            continue

        if a_id not in a_ids:
            continue

        a_name = codepost.assignment.retrieve(a_id).name

        logger.debug('Getting info for "{}" assignment', a_name)
        data[a_id] = get_assignment_rubric(worksheet)
        logger.debug('Got all info for "{}" assignment', a_name)

        a_ids.remove(a_id)

    logger.info('Got all info from "{}" sheet', sheet.title)

    return data


# ===========================================================================

def wipe_and_create_assignment_rubric(a_id, rubric, override_rubric=False):
    """Wipes the existing rubric of an assignment, then creates the new rubric comments.

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

    # wipe existing rubric
    logger.debug('Deleting existing rubric')
    for category in assignment.rubricCategories:
        logger.debug('Deleting "{}" rubric category', category.name)
        category.delete()
    logger.debug('Deleted rubric')

    # create new comments
    logger.debug('Creating new rubric categories')
    for sort_key, (c_name, (max_points, comments)) in enumerate(rubric.items()):

        logger.debug('Creating "{}" rubric category', c_name)

        category = codepost.rubric_category.create(
            name=c_name,
            assignment=a_id,
            pointLimit=max_points,
            sortKey=sort_key,
        )
        c_id = category.id

        # create comments
        for comment in comments:
            codepost.rubric_comment.create(category=c_id, **comment)

        logger.debug('Created "{}" rubric category with {} comments', c_name, len(comments))

    logger.debug('Rubric creation for "{}" assignment successful', a_name)


def create_assignment_rubric(a_id, rubric, override_rubric=False, delete_missing=False):
    """Creates the rubric comments for an assignment.

    Args:
        a_id (int): The assignment id.
        rubric (dict): The rubric comments in the format:
            { category: (max_points, [comments]) }
        override_rubric (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
        delete_missing (bool): Whether to delete rubric comments that do not appear in the sheet.
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

    # get all existing rubric comments
    logger.debug('Getting existing rubric comments')
    codepost_comments = dict()
    categories = dict()
    for category in assignment.rubricCategories:
        categories[category.name] = category
        for comment in category.rubricComments:
            codepost_comments[comment.name] = comment

    # get all rubric comments from sheet
    sheet_categories = dict()
    sheet_comments = dict()
    for category, (_, comments) in rubric.items():
        for comment in comments:
            sheet_categories[comment['name']] = category
            sheet_comments[comment['name']] = comment

    # get missing and new comment names
    existing_names = set(codepost_comments.keys())
    sheet_names = set(sheet_comments.keys())
    missing_names = existing_names - sheet_names
    missing_comments = [codepost_comments.pop(name) for name in missing_names]
    new_names = sheet_names - existing_names
    del existing_names, sheet_names

    if len(missing_comments) > 0:
        logger.debug('Comments not in the sheet: ({})', ','.join(c.name for c in missing_comments))

        # delete rubric comments not in the sheet
        if delete_missing:
            logger.debug('Deleting comments not in the sheet')
            for comment in missing_comments:
                # logger.debug(f'Deleting "{comment.name}" rubric comment')
                comment.delete()
            logger.debug('Deleted {} comments', len(missing_comments))

            # delete old rubric categories if they have no more comments
            empty_categories = list()
            for c_name in list(categories.keys()):
                if len(categories[c_name].rubricComments) == 0:
                    empty_categories.append(categories.pop(c_name))
            if len(empty_categories) > 0:
                logger.debug('Deleting empty categories')
                for category in empty_categories:
                    logger.debug('Deleting "{}" rubric category', category.name)
                    category.delete()
                logger.debug('Deleted {} empty categories', len(empty_categories))

    # create new categories (if needed)
    existing_categories = set(categories.keys())
    new_categories = set(rubric.keys())
    missing_categories = new_categories - existing_categories
    if len(missing_categories) > 0:
        logger.debug('Creating missing rubric categories')
        for c_name in missing_categories:
            logger.debug('Creating "{}" rubric category', c_name)

            max_points = rubric[c_name][0]
            category = codepost.rubric_category.create(
                name=c_name,
                assignment=a_id,
                pointLimit=max_points,
            )
            categories[c_name] = category

            logger.debug('Created "{}" rubric category', c_name)

    # include category id in comment info
    for name, comment_info in sheet_comments.items():
        category_id = categories[sheet_categories[name]].id
        comment_info['category'] = category_id

    # update existing comments
    logger.debug('Updating existing rubric comments')
    for name, comment in codepost_comments.items():
        old_comment = {
            'name': comment.name,
            'text': comment.text,
            'pointDelta': comment.pointDelta,
            'category': comment.category,
            'explanation': comment.explanation,
            'instructionText': comment.instructionText,
            'templateTextOn': comment.templateTextOn,
        }
        comment_info = sheet_comments[name]

        # if anything isn't the same, update the comment
        if old_comment != comment_info:
            codepost.rubric_comment.update(comment.id, **comment_info)
            logger.debug(f'Updated {name}')
            break

    # create new comments
    if len(new_names) == 0:
        logger.debug('No new rubric comments to create')
    else:
        logger.debug('Creating new rubric comments')
        for name in new_names:
            comment_info = sheet_comments[name]
            codepost.rubric_comment.create(**comment_info)
            logger.debug(f'Created "{name}" in "{sheet_categories[name]}"')

    logger.debug('Rubric creation for "{}" assignment successful', a_name)


def create_all_rubrics(rubrics, override_rubric=False, delete_missing=False, wipe_existing=False):
    """Creates the rubric comments for a course.

    Args:
        rubrics (dict): The rubric comments in the format:
            { assignment_id: { category: (max_points, [comments]) } }
        override_rubric (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
        delete_missing (bool): Whether to delete rubric comments that do not appear in the sheet.
            Default is False.
        wipe_existing (bool): Whether to completely wipe the existing rubric.
            Default is False.
    """

    logger.info('Creating all assignment rubrics')

    for a_id, rubric in rubrics.items():
        if wipe_existing:
            wipe_and_create_assignment_rubric(a_id, rubric, override_rubric)
        else:
            create_assignment_rubric(a_id, rubric, override_rubric, delete_missing)

    logger.info('Created all rubrics')


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('start_sheet', type=int, required=False)
@click.argument('end_sheet', type=int, required=False)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@click.option('-o', '--override', is_flag=True, default=False, flag_value=True,
              help='Whether to override rubrics of assignments. Default is False.')
@click.option('-d', '--delete', is_flag=True, default=False, flag_value=True,
              help='Whether to delete comments that are not in the sheet. Default is False.')
@click.option('-w', '--wipe', is_flag=True, default=False, flag_value=True,
              help='Whether to completely wipe the existing rubric. Default is False.')
def main(course_period, sheet_name, start_sheet, end_sheet, testing, override, delete, wipe):
    """
    Imports a codePost rubric from a Google Sheet.

    \b
    Args:
        course_period (str): The period of the COS126 course to import to.
        sheet_name (str): The name of the sheet to pull the rubrics from.
        start_sheet (int): The index of the first sheet to pull from (0-indexed).
            Default is 0.
        end_sheet (int): The index of the last sheet to pull from (0-indexed).
            Default is same as start_sheet. \f
        testing (bool): Whether to run as a test.
            Default is False.
        override (bool): Whether to override rubrics of assignments.
            Default is False.
        delete (bool): Whether to delete comments that are not in the sheet.
            Default is False.
        wipe (bool): Whether to completely wipe the existing rubric.
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
        logger.info('Accessing COS126 course for period "{}"', course_period)
        course = get_126_course(course_period)
    if course is None:
        return

    logger.info('Opening "{}" sheet', sheet_name)
    sheet = open_sheet(g_client, sheet_name)
    if sheet is None:
        return

    if testing and start_sheet is None and end_sheet is None:
        start_sheet = 0
    rubrics = get_all_rubric_comments(course, sheet, start_sheet, end_sheet)

    create_all_rubrics(rubrics, override, delete, wipe)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {:.2f} sec', end - start)


# ===========================================================================

if __name__ == '__main__':
    main()
