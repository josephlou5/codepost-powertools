"""
rubric_to_sheet.py
Exports a codePost rubric to a Google Sheet.

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs

gspread API
https://gspread.readthedocs.io/en/latest/index.html
"""

# TODO: master tab of all comments

# ===========================================================================

import click
from loguru import logger
import codepost
import gspread
import time

from shared import *
from myworksheet import Worksheet

# ===========================================================================

GREEN = (109, 177, 84)
WHITE = (255, 255, 255)

HEADERS = [
    # A  B           C
    '', 'Category', 'Max',
    # D      E         F                 G              H               I
    'Name', 'Points', 'Grader Caption', 'Explanation', 'Instructions', 'Template?',
    # J           K        L    M          N
    'Instances', 'Upvote', '', 'Downvote', ''
]


# ===========================================================================

def get_assignment_rubric(assignment) -> dict:
    """Gets the rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The rubric comments in the format:
            { comment_id: [values] }
    """

    a_name = assignment.name
    a_id = assignment.id

    logger.debug('Getting rubric comments for "{}" assignment', a_name)

    data = dict()

    data['row1'] = [a_id, f'Assignment: {a_name}']
    data['row2'] = HEADERS

    # loop through all categories for this assignment
    for category in assignment.rubricCategories:

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
            text = comment.text
            explanation = comment.explanation
            instruction = comment.instructionText
            template = 'Yes' if comment.templateTextOn else ''

            values = [c_id, c_name, max_points, name, points, text, explanation, instruction, template]

            data[c_id] = values

    logger.debug('Got all rubric comments for "{}" assignment', a_name)

    return data


def get_all_rubric_comments(course, num_assignments=None) -> dict:
    """Gets the rubric comments for a course.

    Args:
        course (codepost.models.courses.Courses): The course.
        num_assignments (int): The number of assignments to get.
            Default is None. Anything other than a valid number will get all.

    Returns:
        dict: The rubric comments in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.info('Getting rubric comments from course')

    data = dict()

    assignments = sorted(course.assignments, key=lambda a: a.sortKey)

    for i, assignment in enumerate(assignments):

        if i == num_assignments:
            break

        # get assignment info
        a_id = assignment.id

        data[a_id] = get_assignment_rubric(assignment)

    logger.info('Got all rubric comments from course')

    return data


# ===========================================================================

def count_comment_instances(assignment_id, comment_ids) -> dict:
    """Count the instances of each rubric comment in an assignment.

    Args:
        assignment_id (int): The id of the assignment.
        comment_ids (list): The ids of the rubric comments.

    Returns:
        dict: The instances of each rubric comment in the format
            { comment_id: [instances, upvote, upvote %, downvote, downvote %] }
    """

    assignment = codepost.assignment.retrieve(assignment_id)
    a_name = assignment.name

    logger.debug('Counting instances for "{}" assignment', a_name)

    counts = dict()

    for c_id in comment_ids:
        counts[c_id] = [0, 0, 0]

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
    # TODO: replace with a formula instead?
    data = dict()
    for c_id, vals in counts.items():

        # no instances
        if vals[0] == 0:
            data[c_id] = [0]
            continue

        data[c_id] = [vals[0],
                      vals[1], vals[1] / vals[0],
                      vals[2], vals[2] / vals[0]]

    logger.debug('Counted all instances for "{}" assignment (Time: {:.2f} sec)', a_name, end - start)

    return data


def get_all_instances(ids) -> dict:
    """Get all the instances of all rubric comments for assignments.

    Args:
        ids (dict): The assignment and comment ids in the format:
            { assignment_id: [ comment_ids ] }

    Returns:
        dict: The instances in the format:
            { assignment_id: { comment_id: [instances, upvote, upvote %, downvote, downvote %] } }
    """

    logger.info('Getting instances of all rubric comments')

    instances = dict()

    for a_id, c_ids in ids.items():
        instances[a_id] = count_comment_instances(a_id, c_ids)

    logger.info('Got all instances of all rubric comments')

    return instances


# ===========================================================================

def display_assignment_comments(worksheet, values):
    """Displays rubric comments for an assignment on a worksheet.

    Args:
        worksheet (Worksheet): The worksheet.
        values (list): The rubric comments.
    """

    rows = len(values)

    worksheet.format_cell('A1', font_family='Fira Code', update=True)

    # if no values, add dummy row to avoid freezing all 2 rows error
    if rows == 2:
        values.append([''])

    # add values
    logger.debug('Setting values of the sheet')
    try:
        worksheet.set_values(values)
    except gspread.exceptions.APIError:
        logger.debug('Request too large: splitting values')
        rows = len(values)
        half = rows // 2
        vals1 = values[:half]
        vals2 = values[half:]
        worksheet.set_values(vals1)
        worksheet.set_values(f'A{half + 1}', vals2)

    # formatting
    logger.debug('Formatting the sheet')

    worksheet.freeze_rows(2)

    worksheet.format_cell('B1:2', bold=True, background_color=GREEN, text_color=WHITE)
    worksheet.format_cell('B2:2', text_align='CENTER')
    worksheet.format_cell(f'B3:{rows}', vertical_align='MIDDLE', wrap='WRAP')

    worksheet.set_col_width('C', 50)  # max category points
    worksheet.set_col_width('D', 150)  # name
    worksheet.set_col_width('E', 75)  # points
    worksheet.set_col_width('F', 200)  # grader caption
    worksheet.set_col_width('G', 650)  # explanation
    worksheet.set_col_width('H', 300)  # instructions
    worksheet.set_col_width('J:N', 75)  # instances columns

    worksheet.merge_cells('K2:L2')
    worksheet.merge_cells('M2:N2')

    # hide id and explanation columns
    worksheet.hide_col('A')
    worksheet.hide_col('G')

    # update worksheet
    worksheet.update()


def display_all_rubric_comments(sheet, comments):
    """Displays rubric comments on a sheet.

    Args:
        sheet (gspread.models.Spreadsheet): The sheet.
        comments (dict): The rubric comments in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.debug('Displaying rubric comments on sheet')

    # delete all current sheets
    logger.debug('Deleting existing worksheets')
    worksheets = sheet.worksheets()
    temp = add_temp_worksheet(sheet)
    for w in worksheets:
        sheet.del_worksheet(w)
    logger.debug('Deleted all worksheets')

    # display all assignments
    for a_id, a_data in comments.items():

        assignment = codepost.assignment.retrieve(a_id)
        a_name = assignment.name

        # create new worksheet
        worksheet = Worksheet(sheet.add_worksheet(title=a_name, rows=1, cols=1))

        # delete the temp worksheet
        if temp is not None:
            sheet.del_worksheet(temp)
            temp = None

        logger.debug('Displaying rubric comments for "{}" assignment', a_name)
        display_assignment_comments(worksheet, list(a_data.values()))
        logger.debug('Displayed all rubric comments for "{}" assignment', a_name)

    logger.debug('Displayed all rubric comments on sheet')


# ===========================================================================

def display_assignment_instances(worksheet, values):
    """Displays instance counts for an assignment on a worksheet.

    Args:
        worksheet (Worksheet): The worksheet.
        values (list): The instance counts.
    """

    # add values
    worksheet.set_values('J3', values)

    # format feedback columns
    worksheet.format_number_cell('L', 'PERCENT', '0.0%')
    worksheet.format_number_cell('N', 'PERCENT', '0.0%')

    # update worksheet
    worksheet.update()


def display_all_instances(sheet, instances):
    """Displays instance counts on a Google Sheet.

    Args:
        sheet (gspread.models.Spreadsheet): The sheet.
        instances (dict): The instance counts in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.info('Displaying instance counts on sheet')

    for index, (a_id, a_data) in enumerate(instances.items()):

        g_worksheet = sheet.get_worksheet(index)
        if g_worksheet is None:
            logger.warning('Not enough sheets exist to display instances for the given input')
            return
        worksheet = Worksheet(g_worksheet)

        if worksheet.get_cell('A1').value != str(a_id):
            logger.warning('Assignments in sheet not in same order as the given input')
            return

        a_name = codepost.assignment.retrieve(a_id).name
        logger.debug('Displaying instance counts for "{}" assignment', a_name)
        display_assignment_instances(worksheet, list(a_data.values()))
        logger.debug('Displayed all instance counts for "{}" assignment', a_name)

    logger.info('Displayed all instance counts on sheet')


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('num_assignments', type=int, required=False)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@click.option('-i', '--instances', is_flag=True, default=False, flag_value=True,
              help='Whether to count instances of rubric comments. Default is False.')
def main(course_period, sheet_name, num_assignments, testing, instances):
    """
    Exports a codePost rubric to a Google Sheet.

    \b
    Args:
        course_period (str): The period of the COS126 course to export from.
        sheet_name (str): The name of the sheet to import the rubrics to.
        num_assignments (int): The number of assignments to get from the course.
            Default is ALL. \f
        testing (bool): Whether to run as a test.
            Default is False.
        instances (bool): Whether to count instances of rubric comments.
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

    logger.info('Accessing COS126 course for period "{}"', course_period)
    course = get_126_course(course_period)
    if course is None:
        return

    logger.info('Opening "{}" sheet', sheet_name)
    sheet = open_sheet(g_client, sheet_name)
    if sheet is None:
        return

    if testing and num_assignments is None:
        num_assignments = 1
    comments = get_all_rubric_comments(course, num_assignments)

    display_all_rubric_comments(sheet, comments)

    if instances:

        ids = dict()
        for a_id, values in comments.items():
            # need to skip the first 2 rows to get only comment ids
            ids[a_id] = list(values.keys())[2:]

        instances = get_all_instances(ids)

        display_all_instances(sheet, instances)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {:.2f} sec', end - start)


# ===========================================================================

if __name__ == '__main__':
    main()
