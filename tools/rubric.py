"""
rubric.py
Rubric related operations.

Commands:
to - Exports a codePost rubric to a Google Sheet
from - Imports a codePost rubric from a Google Sheet
rename - Renames rubric comments

GitHub repo:
https://github.com/josephlou5/codepost-powertools
"""

# ===========================================================================

import os
import time
from functools import update_wrapper
from typing import (
    Any,
    Sequence, List, Tuple, Mapping, Dict,
    Optional, Union,
)

import click
import codepost
import gspread
from loguru import logger

from myworksheet import *
from shared import *

# ===========================================================================

# globals
SERVICE_ACCOUNT_FILE = 'service_account.json'

SHEET_HEADERS = {
    # info: header title on sheet
    'category': 'Category',
    'max points': 'Max',

    'name': 'Name',
    'new name': 'New name',
    'tier': 'Tier',
    'point delta': 'Points',
    'caption': 'Grader Caption',
    'explanation': 'Explanation',
    'instructions': 'Instructions',
    'is template': 'Template?',
}
HEADERS = [
    # A  B           C
    '', 'Category', 'Max',
    # D      E       F         G                 H              I               J
    'Name', 'Tier', 'Points', 'Grader Caption', 'Explanation', 'Instructions', 'Template?',
    # K           L        M    N          O
    'Instances', 'Upvote', '', 'Downvote', ''
]
# note: comments.py:track_comments also relies on knowing this format
TIER_FMT = '\\[T{tier}\\] {text}'
TEMPLATE_YES = ('x', 'yes', 'y')

# constants
CTX_SETTINGS = {
    'context_settings': {'ignore_unknown_options': True}
}
GREEN: Color = (109, 177, 84)
WHITE: Color = (255, 255, 255)


# ===========================================================================

def set_up_service_account() -> Optional[gspread.Client]:
    """Sets up the Google service account to connect with Google Sheets.

    Returns:
        gspread.Client: The client.
            Returns None if unsuccessful.
    """

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        logger.critical('"{}" file not found in directory', SERVICE_ACCOUNT_FILE)
        return None

    return gspread.service_account(SERVICE_ACCOUNT_FILE)


# ===========================================================================

def open_sheet(g_client: gspread.Client, sheet_name: str) -> Optional[GSpreadsheet]:
    """Opens a Google Sheet.

    Args:
        g_client (gspread.Client): The Client used.
        sheet_name (str): The name of the sheet to open.

    Returns:
        Spreadsheet: The spreadsheet.
            Returns None if unsuccessful.
    """

    try:
        return g_client.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        logger.critical('Spreadsheet "{}" not found', sheet_name)
        return None


def add_temp_worksheet(sheet: GSpreadsheet,
                       title: str = 'temp',
                       rows: int = 1,
                       cols: int = 1,
                       index: int = None
                       ) -> GWorksheet:
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
        GWorksheet: The temp worksheet.
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

def display_on_worksheet(worksheet: Worksheet,
                         values: List[Any],
                         cell_range: str = 'A1',
                         freeze: int = 0,
                         cell_formats: Sequence[Tuple[str, Mapping[str, Any]]] = None,
                         number_formats: Sequence[Tuple[str, Mapping[str, Any]]] = None,
                         col_widths: Sequence[Tuple[str, int]] = None,
                         merge: Sequence[str] = None,
                         hide_cols: Sequence[str] = None
                         ):
    """Displays values on a worksheet.

    Args:
        worksheet (Worksheet): The worksheet.
        values (List[Any]): The values.
        cell_range (str): The range to display the values.
        freeze (int): The number of rows to freeze.
            Default is 0.
        cell_formats (Sequence[Tuple[str, Mapping[str, Any]]]): The args for formatting a cell.
            Default is None.
        number_formats (Sequence[Tuple[str, Mapping[str, Any]]]): The args for formatting a number cell.
            Default is None.
        col_widths (Sequence[Tuple[str, int]]): The args for setting a column's width.
            Default is None.
        merge (Sequence[str]): The cell ranges to merge.
            Default is None.
        hide_cols (Sequence[str]): The columns to hide.
            Default is None.
    """

    # add empty rows to avoid freezing all rows error
    if len(values) < freeze:
        # reassigns `values`; doesn't mutate
        values = values + [''] * (freeze - len(values) + 1)

    worksheet.set_values(cell_range, values)

    if freeze > 0:
        worksheet.freeze_rows(freeze)
    if cell_formats is not None:
        for rnge, kwargs in cell_formats:
            worksheet.format_cell(rnge, **kwargs)
    if number_formats is not None:
        for rnge, kwargs in number_formats:
            worksheet.format_number_cell(rnge, **kwargs)
    if col_widths is not None:
        for args in col_widths:
            worksheet.set_col_width(*args)
    if merge is not None:
        for rnge in merge:
            worksheet.merge_cells(rnge)
    if hide_cols is not None:
        for rnge in hide_cols:
            worksheet.hide_col(rnge)

    worksheet.update()


# ===========================================================================

def get_codepost_rubric(assignment: Assignment) -> Dict[int, List]:
    """Gets the rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.

    Returns:
        Dict[int, List]: The rubric comments in the format:
            { comment_id: [values] }
    """

    a_name = assignment.name
    a_id = assignment.id

    logger.debug('Getting rubric comments for "{}" assignment', a_name)

    data = dict()

    data['row1'] = [a_id, f'Assignment: {a_name}']
    data['row2'] = HEADERS

    # loop through all categories for this assignment (sorted by sortKey)
    for category in sorted(assignment.rubricCategories, key=lambda c: c.sortKey):

        # get category info
        c_name = category.name
        max_points = category.pointLimit

        logger.debug('Getting rubric comments in "{}" rubric category', c_name)

        if max_points is None:
            max_points = ''
        else:
            max_points = -1 * max_points

        # loop through all comments for this category
        for comment in category.rubricComments:
            # get comment info
            c_id = comment.id
            name = comment.name
            points = -1 * comment.pointDelta
            tier = ''
            text = comment.text
            explanation = comment.explanation
            instruction = comment.instructionText
            template = 'Yes' if comment.templateTextOn else ''

            # get tier if has it
            if text[:3] == '\\[T' and text[4:6] == '\\]':
                try:
                    tier = int(text[3])
                    text = text[7:]
                except ValueError:
                    # tier is not a valid number; shouldn't happen
                    pass

            values = [c_id, c_name, max_points, name, tier, points, text, explanation, instruction, template]

            data[c_id] = values

    logger.debug('Got all rubric comments for "{}" assignment', a_name)

    return data


def get_all_codepost_rubrics(assignments: Sequence[Assignment]) -> Dict[int, Dict[int, List]]:
    """Gets the rubric comments for some assignments.

    Args:
        assignments (Sequence[Assignment]): The assignments.

    Returns:
        Dict[int, Dict[int, List]]: The rubric comments in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.info('Getting rubric comments for assignments')

    data = dict()

    for assignment in assignments:
        data[assignment.id] = get_codepost_rubric(assignment)

    logger.info('Got all rubric comments for assignments')

    return data


def get_sheet_rubric(assignment_name: str, worksheet: Worksheet) -> Dict[str, Tuple[int, List[Dict]]]:
    """Gets the rubric comments for an assignment from a worksheet.

    Args:
        assignment_name (str): The assignment name.
        worksheet (Worksheet): The worksheet.

    Returns:
        Dict[str, Tuple[int, List[Dict]]]: The rubric comments in the format:
            { category: (max_points, [comments]) }
    """

    logger.debug('Getting info for "{}" assignment', assignment_name)

    data = dict()

    # go through the rows of the worksheet
    values = worksheet.get_records(head=2)
    for row in values:

        # get category
        category = row.get(SHEET_HEADERS['category'], None)
        if category is None or category == '':
            continue

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

        # create entries for category and comment
        if category not in data:
            max_points = row.get(SHEET_HEADERS['max points'], None)
            if max_points == '':
                max_points = None
            else:
                max_points = -1 * int(max_points)
            data[category] = (max_points, list())
        data[category][1].append(comment)

    # if rubric category has no comments, remove it
    for category in list(data.keys()):
        if len(data[category][1]) == 0:
            data.pop(category)

    logger.debug('Got all info for "{}" assignment', assignment_name)

    return data


# ===========================================================================

def get_worksheets(sheet: GSpreadsheet,
                   assignments: Mapping[int, Assignment],
                   start_sheet: int = 0,
                   end_sheet: int = 0
                   ) -> Dict[int, Worksheet]:
    """Gets the worksheets in the given range.

    Args:
        sheet (GSpreadsheet): The sheet.
        assignments (Mapping[int, Assignment]): The assignments, in the format:
            { assignment_id: Assignment }
        start_sheet (int): The index of the first sheet (0-indexed).
            Default is 0.
        end_sheet (int): The index of the last sheet (0-indexed).
            Default is same as `start_sheet`.

    Returns:
        Dict[int, Worksheet]: The worksheets, in the format:
            { assignment_id: Worksheet }
    """

    if end_sheet < start_sheet:
        end_sheet = start_sheet

    worksheets: Dict[int, Worksheet] = dict()

    for index in range(start_sheet, end_sheet + 1):
        w = sheet.get_worksheet(index)
        if w is None: continue

        worksheet = Worksheet(w)

        # check assignment id in A1
        try:
            a_id = int(worksheet.get_cell('A1').value)
        except ValueError:
            continue

        assignment = assignments.get(a_id, None)
        if assignment is None:
            continue

        worksheets[a_id] = worksheet

    return worksheets


def get_assignment_worksheets(sheet: GSpreadsheet,
                              assignments: Sequence[Assignment],
                              wipe: bool = False,
                              replace: bool = False
                              ) -> Dict[int, Worksheet]:
    """Gets the worksheets for the given assignments.

    Args:
        sheet (GSpreadsheet): The sheet.
        assignments (Sequence[Assignment]): The assignments.
        wipe (bool): Whether to wipe the existing sheet.
            Default is False.
        replace (bool): Whether to replace the existing sheets.
            Default is False.

    Returns:
        Dict[int, Worksheet]: The Worksheet objects in the format:
            { assignment_id: worksheet }
    """

    existing = sheet.worksheets()
    temp = add_temp_worksheet(sheet)

    # delete all current sheets
    if wipe:
        logger.debug('Deleting existing worksheets')
        num_existing = len(existing)
        for _ in range(num_existing):
            sheet.del_worksheet(existing.pop())
        logger.debug('Deleted all worksheets')

    logger.info('Finding worksheets for each assignment')

    worksheets = dict()

    for assignment in assignments:
        a_id = assignment.id
        a_name = assignment.name

        this_worksheet = None

        if replace:
            # look for matching worksheet according to ids
            for index, w in enumerate(existing):
                worksheet = Worksheet(w)
                if str(a_id) == worksheet.get_cell('A1').value:
                    # TODO: keep existing columns rather than deleting and adding new worksheet
                    # delete old worksheet
                    title = w.title
                    sheet.del_worksheet(w)
                    # add new worksheet in same place
                    new_w = add_temp_worksheet(sheet, title=title, index=index)
                    existing[index] = new_w
                    this_worksheet = Worksheet(new_w)
                    break

        if this_worksheet is None:
            # create new worksheet
            this_worksheet = Worksheet(add_temp_worksheet(sheet, title=a_name))
            # format the sheet with default
            this_worksheet.format_cell('A1', font_family='Fira Code', update=True)

        worksheets[a_id] = this_worksheet

    sheet.del_worksheet(temp)

    return worksheets


def get_rubric_instances(assignment: Assignment, comment_ids: Sequence[int]) -> Dict[int, List[Union[int, float]]]:
    """Count the instances of each rubric comment in an assignment.

    Args:
        assignment (Assignment): The assignment.
        comment_ids (Sequence[int]): The rubric comment ids.

    Returns:
        Dict[int, List[Union[int, float]]]: The instances of each rubric comment in the format:
            { comment_id: [instances, upvote, upvote %, downvote, downvote %] }
    """

    a_name = assignment.name

    logger.debug('Counting instances for "{}" assignment', a_name)

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

    logger.debug('Counted all instances for "{}" assignment ({:.2f} sec)', a_name, end - start)

    return data


# ===========================================================================

def wipe_and_create_assignment_rubric(assignment: Assignment,
                                      rubric: Mapping[str, Tuple[int, List]],
                                      override: bool = False
                                      ):
    """Wipes the existing rubric of an assignment, then creates the new rubric comments.

    Args:
        assignment (Assignment): The assignment.
        rubric (Mapping[str, Tuple[int, List]]): The rubric comments in the format:
            { category: (max_points, [comments]) }
        override (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
    """

    a_id = assignment.id
    a_name = assignment.name

    logger.debug('Creating rubric for "{}" assignment', a_name)

    # check for existing submissions
    has_submissions = len(assignment.list_submissions()) > 0
    if has_submissions:
        logger.warning('"{}" assignment has existing submissions', a_name)
        if not override:
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


def create_assignment_rubric(assignment: Assignment,
                             rubric: Mapping[str, Tuple[int, List]],
                             override=False,
                             delete=False
                             ):
    """Creates the rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.
        rubric (Mapping[str, Tuple[int, List]]): The rubric comments in the format:
            { category: (max_points, [comments]) }
        override (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
        delete (bool): Whether to delete rubric comments that do not appear in the sheet.
            Default is False.
    """

    a_id = assignment.id
    a_name = assignment.name

    logger.debug('Creating rubric for "{}" assignment', a_name)

    # check for existing submissions
    has_submissions = len(assignment.list_submissions()) > 0
    if has_submissions:
        logger.warning('"{}" assignment has existing submissions', a_name)
        if not override:
            logger.debug('Rubric creation for "{}" assignment unsuccessful', a_name)
            return
        logger.warning('Overriding rubric')

    # get all existing rubric comments
    logger.debug('Getting existing rubric comments')
    codepost_comments: Dict[str, RubricComment] = dict()
    categories: Dict[str, RubricCategory] = dict()
    empty_categories: List[RubricCategory] = list()
    for category in assignment.rubricCategories:
        comments = category.rubricComments
        if len(comments) > 0:
            empty_categories.append(category)
            continue
        categories[category.name] = category
        for comment in category.rubricComments:
            codepost_comments[comment.name] = comment

    # get all rubric comments from sheet
    # maps comment name -> category name
    sheet_categories: Dict[str, str] = dict()
    # maps comment name -> comment info (in kwargs format)
    sheet_comments: Dict[str, Dict] = dict()
    for category_name, (_, comments) in rubric.items():
        for comment in comments:
            sheet_categories[comment['name']] = category_name
            sheet_comments[comment['name']] = comment

    # get missing and new comment names
    existing_names = set(codepost_comments.keys())
    sheet_names = set(sheet_comments.keys())
    missing_names = existing_names - sheet_names
    missing_comments: List[RubricComment] = [codepost_comments.pop(name) for name in missing_names]
    new_names = sheet_names - existing_names
    del existing_names, sheet_names, missing_names

    if len(missing_comments) > 0:
        logger.debug('Found {} comments not in the sheet: {}',
                     len(missing_comments), ','.join(c.name for c in missing_comments))

        # delete rubric comments not in the sheet
        if delete:
            logger.debug('Deleting comments not in the sheet')
            search = set()
            for comment in missing_comments:
                search.add(comment.rubricCategory)
                comment.delete()
            logger.debug('Deleted {} comments', len(missing_comments))

            # find possible empty categories
            if len(search) > 0:
                for c_name in list(categories.keys()):
                    category = categories[c_name]
                    c_id = category.id
                    if c_id not in search:
                        continue
                    search.remove(c_id)
                    if len(category.rubricComments) == 0:
                        empty_categories.append(categories.pop(c_name))

    if len(empty_categories) > 0:
        logger.debug('Found {} categories not in the sheet: {}',
                     len(empty_categories), ','.join(c.name for c in empty_categories))

        # delete categories not in the sheet
        if delete:
            logger.debug('Deleting empty categories')
            for category in empty_categories:
                category.delete()
            logger.debug('Deleted {} empty categories', len(empty_categories))

    # create new categories (if needed)
    existing_categories = set(categories.keys())
    new_categories = set(rubric.keys())
    missing_categories = new_categories - existing_categories
    del existing_categories, new_categories

    if len(missing_categories) > 0:
        logger.debug('Creating missing rubric categories')
        for c_name in missing_categories:
            max_points = rubric[c_name][0]
            category = codepost.rubric_category.create(
                name=c_name,
                assignment=a_id,
                pointLimit=max_points,
            )
            categories[c_name] = category
        logger.debug('Created {} missing rubric categories', len(missing_categories))

    # sort categories
    for sort_key, category_name in enumerate(rubric.keys()):
        codepost.rubric_category.update(
            id=categories[category_name].id,
            sortKey=sort_key,
        )

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
            logger.debug('Updated "{}"', name)

    # create new comments
    if len(new_names) == 0:
        logger.debug('No new rubric comments to create')
    else:
        logger.debug('Creating new rubric comments')
        for name in new_names:
            comment_info = sheet_comments[name]
            codepost.rubric_comment.create(**comment_info)
            logger.debug('Created "{}" in "{}"', name, sheet_categories[name])
        logger.debug('Created {} new rubric comments', len(new_names))

    logger.debug('Rubric creation for "{}" assignment successful', a_name)


def create_all_rubrics(rubrics: Mapping[int, Mapping[str, Tuple]],
                       assignments: Mapping[int, Assignment],
                       override: bool = False,
                       delete: bool = False,
                       wipe: bool = False
                       ):
    """Creates the rubric comments for a course.

    Args:
        rubrics (Mapping[int, Mapping[str, Tuple]]): The rubric comments in the format:
            { assignment_id: { category: (max_points, [comments]) } }
        assignments (Mapping[int, Assignment]): The assignments in the format:
            { assignment_id: Assignment }
        override (bool): Whether to override the rubric of an assignment that has existing submissions.
            Default is False.
        delete (bool): Whether to delete rubric comments that do not appear in the sheet.
            Default is False.
        wipe (bool): Whether to completely wipe the existing rubric.
            Default is False.
    """

    logger.info('Creating all assignment rubrics')

    for a_id, rubric in rubrics.items():
        assignment = assignments[a_id]
        if wipe:
            wipe_and_create_assignment_rubric(assignment, rubric, override)
        else:
            create_assignment_rubric(assignment, rubric, override, delete)

    logger.info('Created all rubrics')


# ===========================================================================

# https://github.com/pallets/click/issues/513#issuecomment-504158316
class NaturalOrderGroup(click.Group):
    def list_commands(self, ctx):
        return self.commands.keys()


@click.group(cls=NaturalOrderGroup)
def cli():
    """Grading related operations."""
    pass


def wrap(f):
    """Decorator for start and end."""

    @click.pass_context
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        start = time.time()
        logger.info('Start')

        # do function
        ctx.invoke(f, ctx, **kwargs)

        logger.info('Done')
        end = time.time()
        logger.info('Total time: {}', format_time(end - start))

    return update_wrapper(main, f)


def driver(f):
    """Decorator for main driver."""

    @click.pass_context
    @wrap
    def main(ctx, *args, **kwargs):

        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        course_period = kwargs['course_period']

        logger.info('Logging into codePost')
        success = log_in_codepost()
        if not success:
            return

        logger.info('Accessing codePost course')
        if kwargs.get('testing', False):
            logger.info('Running as test: Opening Joseph\'s Course')
            course = get_course("Joseph's Course", 'S2021')
        else:
            logger.info('Accessing COS126 course for period "{}"', course_period)
            course = get_126_course(course_period)
        if course is None:
            return

        kwargs['COURSE'] = course

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


def with_sheet(f):
    """Decorator for main driver with a sheet."""

    @click.pass_context
    @wrap
    def main(ctx, *args, **kwargs):

        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        course_period = kwargs['course_period']
        sheet_name = kwargs['sheet_name']

        logger.info('Logging into codePost')
        success = log_in_codepost()
        if not success:
            return

        logger.info('Setting up Google service account')
        g_client = set_up_service_account()
        if g_client is None:
            return

        logger.info('Accessing codePost course')
        if kwargs.get('testing', False):
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

        kwargs['COURSE'] = course
        kwargs['SHEET'] = sheet

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


# ===========================================================================

@cli.command(
    'to',
    **CTX_SETTINGS,
    help='Exports a codePost rubric to a Google Sheet.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('start_assignment', type=str, required=False)
@click.argument('end_assignment', type=str, required=False)
@click.option('-w', '--wipe', is_flag=True, default=False, flag_value=True,
              help='Whether to wipe the current sheet. Default is False.')
@click.option('-r', '--replace', is_flag=True, default=False, flag_value=True,
              help='Whether to replace the existing sheets. Default is False.')
@click.option('-i', '--instances', is_flag=True, default=False, flag_value=True,
              help='Whether to count instances of rubric comments. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@with_sheet
def to_cmd(*args, **kwargs):
    """Exports a codePost rubric to a Google Sheet."""

    # not using args, but needs it in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    sheet = kwargs['SHEET']

    start_assignment = kwargs.get('start_assignment', None)
    end_assignment = kwargs.get('end_assignment', None)
    wipe = kwargs.get('wipe', False)
    replace = kwargs.get('replace', False)
    instances = kwargs.get('instances', False)

    logger.info('Getting assignment range')
    assignments = sorted(course.assignments, key=lambda a: a.sortKey)
    if start_assignment is None and end_assignment is None:
        if kwargs['testing']:
            assignments = assignments[:1]
    else:
        indices = {a.name: i for i, a in enumerate(assignments)}
        first = 0
        last = 0
        if start_assignment is not None:
            first = indices.get(start_assignment, None)
            if first is None:
                logger.error('Invalid start assignment "{}"', start_assignment)
                return
        if end_assignment is not None:
            last = indices.get(end_assignment, None)
            if last is None:
                logger.error('Invalid end assignment "{}"', end_assignment)
                return
        if last < first:
            last = first
        assignments = assignments[first:last + 1]
    if len(assignments) == 0:
        logger.error('No assignments to parse through')
        return

    comments = get_all_codepost_rubrics(assignments)
    worksheets = get_assignment_worksheets(sheet, assignments, wipe, replace)

    logger.info('Displaying rubric comments on sheet')

    # sheet formatting
    rows = len(comments)
    freeze = 2
    cell_formats = [
        # header
        ('B1:2', {'bold': True, 'background_color': GREEN, 'text_color': WHITE}),
        ('B2:2', {'text_align': 'CENTER'}),
        # ids column
        ('A', {'vertical_align': 'MIDDLE'}),
        # all other rows
        (f'B3:{rows}', {'vertical_align': 'MIDDLE', 'wrap': 'WRAP'}),
    ]
    col_widths = [
        ('B', 100),  # category name
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

    for assignment in assignments:
        a_id = assignment.id
        a_name = assignment.name

        a_data = comments[a_id]
        values = list(a_data.values())
        worksheet = worksheets[a_id]

        logger.debug('Displaying rubric comments for "{}" assignment', a_name)

        display_on_worksheet(worksheet, values,
                             freeze=freeze, cell_formats=cell_formats,
                             col_widths=col_widths, merge=merge, hide_cols=hide_cols)

    logger.info('Displayed all rubric comments on sheet')

    if not instances: return

    logger.info('Getting instances of all rubric comments')

    # instances formatting
    number_formats = [
        ('M', {'fmt_type': 'PERCENT', 'pattern': '0.0%'}),
        ('O', {'fmt_type': 'PERCENT', 'pattern': '0.0%'}),
    ]

    for assignment in assignments:
        a_id = assignment.id
        a_name = assignment.name
        # skip first two header rows
        c_ids = list(comments[a_id].keys())[2:]
        worksheet = worksheets[a_id]

        instances = get_rubric_instances(assignment, c_ids)

        values = list(instances.values())

        logger.debug('Displaying instances for "{}" assignment', a_name)
        display_on_worksheet(worksheet, values, cell_range='K3', number_formats=number_formats)

    logger.info('Got all instances of all rubric comments')


# ===========================================================================

@cli.command(
    'from',
    **CTX_SETTINGS,
    help='Imports a codePost rubric from a Google Sheet.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('start_sheet', type=click.IntRange(0, None), default=0, required=False)
@click.argument('end_sheet', type=click.IntRange(0, None), default=0, required=False)
@click.option('-o', '--override', is_flag=True, default=False, flag_value=True,
              help='Whether to override rubrics of assignments. Default is False.')
@click.option('-d', '--delete', is_flag=True, default=False, flag_value=True,
              help='Whether to delete comments that are not in the sheet. Default is False.')
@click.option('-w', '--wipe', is_flag=True, default=False, flag_value=True,
              help='Whether to completely wipe the existing rubric. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def from_cmd(*args, **kwargs):
    """Imports a codePost rubric from a Google Sheet."""

    # not using args, but needs it in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    sheet = kwargs['SHEET']
    sheet_name = kwargs['sheet_name']

    start_sheet = kwargs.get('start_sheet', 0)
    end_sheet = kwargs.get('end_sheet', 0)
    override = kwargs.get('override', False)
    delete = kwargs.get('delete', False)
    wipe = kwargs.get('wipe', False)

    if end_sheet < start_sheet:
        end_sheet = start_sheet

    assignments: Dict[int, Assignment] = {a.id: a for a in course.assignments}
    worksheets = get_worksheets(sheet, assignments, start_sheet, end_sheet)

    logger.info('Getting info from "{}" sheet', sheet_name)
    rubrics = dict()
    for a_id, worksheet in worksheets.items():
        assignment = assignments[a_id]
        rubrics[a_id] = get_sheet_rubric(assignment.name, worksheet)
    logger.info('Got all info from "{}" sheet', sheet_name)

    create_all_rubrics(rubrics, assignments, override, delete, wipe)


# ===========================================================================

@cli.command(
    'rename',
    **CTX_SETTINGS,
    help='Renames rubric comments.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('start_sheet', type=click.IntRange(0, None), default=0, required=False)
@click.argument('end_sheet', type=click.IntRange(0, None), default=0, required=False)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def rename_cmd(*args, **kwargs):
    """Renames rubric comments."""

    # not using args, but needs it in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    sheet = kwargs['SHEET']

    start_sheet = kwargs.get('start_sheet', 0)
    end_sheet = kwargs.get('end_sheet', 0)

    if end_sheet < start_sheet:
        end_sheet = start_sheet

    assignments: Dict[int, Assignment] = {a.id: a for a in course.assignments}
    worksheets = get_worksheets(sheet, assignments, start_sheet, end_sheet)

    total_changed = 0
    for a_id, worksheet in worksheets.items():
        assignment = assignments[a_id]

        rubric: Dict[str: RubricComment] = dict()
        for category in assignment.rubricCategories:
            for comment in category.rubricComments:
                rubric[comment.name] = comment

        headers = worksheet.get_row_values(2)
        try:
            old_name_col = headers.index(SHEET_HEADERS['name'])
        except ValueError:
            old_name_col = -1
        try:
            new_name_col = headers.index(SHEET_HEADERS['new name'])
        except ValueError:
            new_name_col = -1

        if old_name_col == new_name_col == -1:
            logger.error('Worksheet "{}" does not have the name columns', worksheet.title)
            continue
        if old_name_col == -1:
            logger.error('Worksheet "{}" does not have a name column', worksheet.title)
        if new_name_col == -1:
            logger.error('Worksheet "{}" does not have a new name column', worksheet.title)
            continue

        values = worksheet.get_values()
        replaced_name_values = list()
        changed = 0
        for i, row in enumerate(values):
            # skip first two header rows
            if i < 2: continue

            old_name = row[old_name_col]
            new_name = row[new_name_col]

            if new_name is None or new_name == '' or old_name is None or old_name == '':
                replaced_name_values.append([old_name])
                continue
            if old_name not in rubric:
                logger.warning('Comment "{}" not in rubric', old_name)
                replaced_name_values.append([old_name])
                continue

            c_id = rubric[old_name].id
            logger.debug('Changing comment {} name "{}" to "{}"', c_id, old_name, new_name)
            codepost.rubric_comment.update(c_id, name=new_name)
            changed += 1
            replaced_name_values.append([new_name])

        logger.debug('Worksheet "{}": Changed {} comment names', worksheet.title, changed)
        total_changed += changed

        # replace old name column with new names
        cell_range = Worksheet.to_a1(3, old_name_col + 1)
        display_on_worksheet(worksheet, replaced_name_values, cell_range=cell_range)

    logger.debug('Changed {} total comment names', total_changed)


# ===========================================================================

if __name__ == '__main__':
    cli()
