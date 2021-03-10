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

# TODO: master tab of all comments?

# ===========================================================================

import click
from loguru import logger
import codepost
import codepost.models.assignments  # to get rid of an error message
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
    # D      E       F         G                 H              I               J
    'Name', 'Tier', 'Points', 'Grader Caption', 'Explanation', 'Instructions', 'Template?',
    # K           L        M    N          O
    'Instances', 'Upvote', '', 'Downvote', ''
]

TEMPLATE_YES = 'Yes'


# ===========================================================================

def get_assignments_range(course, start=None, end=None) -> list[codepost.models.assignments.Assignments]:
    """Gets the assignments to get the rubrics for.

    Args:
        course (codepost.models.courses.Courses): The course.
        start (str): The assignment to start getting rubrics for.
            Default is the first one.
        end (str): The assignment to stop getting rubrics for.
            If `start` is not given, default is the last one.
            If `start` is given, default is the same as `start`.

    Returns:
        list[codepost.models.assignments.Assignments]: The assignments.
    """

    assignments = sorted(course.assignments, key=lambda a: a.sortKey)
    indices = {a.name: i for i, a in enumerate(assignments)}

    if start is None and end is None:
        return assignments

    first = 0
    last = 0

    if start is not None:
        first = indices.get(start, None)
        if first is None:
            logger.error('Invalid start assignment "{}"', start)
            return list()
    if end is not None:
        last = indices.get(end, None)
        if last is None:
            logger.error('Invalid end assignment "{}"', end)
            return list()

    if last < first:
        last = first

    return assignments[first:last + 1]


# ===========================================================================

def get_assignment_rubric(assignment) -> dict[int, list]:
    """Gets the rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict[int, list]: The rubric comments in the format:
            { comment_id: [values] }
    """

    a_name = assignment.name
    a_id = assignment.id

    logger.debug('Getting rubric comments for "{}" assignment', a_name)

    data = dict()

    data['row1'] = [a_id, f'Assignment: {a_name}']
    data['row2'] = HEADERS

    # loop through all categories for this assignment (sorted by sortKey)
    for category in sorted(assignment.rubricCategories, key=lambda rc: rc.sortKey):

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
            template = TEMPLATE_YES if comment.templateTextOn else ''

            # get tier if has it
            if text[:3] == '\\[T' and text[4:6] == '\\]':
                try:
                    tier = int(text[3])
                    text = text[7:]
                except ValueError:
                    # not a valid number; shouldn't happen
                    pass

            values = [c_id, c_name, max_points, name, tier, points, text, explanation, instruction, template]

            data[c_id] = values

    logger.debug('Got all rubric comments for "{}" assignment', a_name)

    return data


def get_all_rubric_comments(assignments) -> dict[id, dict[id, list]]:
    """Gets the rubric comments for a course.

    Args:
        assignments (list[codepost.models.assignments.Assignments]): The assignments to get.

    Returns:
        dict[id, dict[id, list]]: The rubric comments in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.info('Getting rubric comments from course')

    data = dict()

    for assignment in assignments:
        data[assignment.id] = get_assignment_rubric(assignment)

    logger.info('Got all rubric comments from course')

    return data


# ===========================================================================

def get_assignment_instances(assignment, comment_ids) -> dict[int, list]:
    """Count the instances of each rubric comment in an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
        comment_ids (list[int]): The ids of the rubric comments.

    Returns:
        dict[int, list]: The instances of each rubric comment in the format:
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

    logger.debug('Counted all instances for "{}" assignment ({:.2f} sec)', a_name, end - start)

    return data


def get_all_instances(assignments, ids) -> dict[int, dict[int, list]]:
    """Get all the instances of all rubric comments for assignments.

    Args:
        assignments (list[codepost.models.assignments.Assignments]): The assignments.
        ids (dict[int, list]): The assignment and comment ids in the format:
            { assignment_id: [ comment_ids ] }

    Returns:
        dict[int, dict[int, list]]: The instances in the format:
            { assignment_id: { comment_id: [instances, upvote, upvote %, downvote, downvote %] } }
    """

    logger.info('Getting instances of all rubric comments')

    instances = dict()

    for assignment in assignments:
        a_id = assignment.id
        c_ids = ids[a_id]
        instances[a_id] = get_assignment_instances(assignment, c_ids)

    logger.info('Got all instances of all rubric comments')

    return instances


# ===========================================================================

def get_worksheets(sheet, assignments, wipe=False, replace=False) -> dict[int, Worksheet]:
    """Gets the worksheets to display data on.

    Args:
        sheet (gspread.models.Spreadsheet): The sheet.
        assignments (list[codepost.models.assignments.Assignments]): The assignments.
        wipe (bool): Whether to wipe the existing sheet.
            Default is False.
        replace (bool): Whether to replace the existing sheets.
            Default is False.

    Returns:
        dict[int, Worksheet]: The Worksheet objects in the format:
            { assignment_id: worksheet }
    """

    worksheets = dict()

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

        worksheets[a_id] = this_worksheet

    sheet.del_worksheet(temp)

    return worksheets


# ===========================================================================

def display_assignment_comments(a_name, worksheet, values):
    """Displays rubric comments for an assignment on a worksheet.

    Args:
        a_name (str): The assignment name.
        worksheet (Worksheet): The worksheet.
        values (list): The rubric comments.
    """

    logger.debug('Displaying rubric comments for "{}" assignment', a_name)

    rows = len(values)

    # worksheet should only have A1, so this will format the entire sheet
    worksheet.format_cell('A1', font_family='Fira Code', update=True)

    # if no values, add dummy row to avoid freezing all 2 rows error
    if rows == 2:
        values.append([''])

    # add values
    # logger.debug('Setting values of the sheet')
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
    # logger.debug('Formatting the sheet')

    worksheet.freeze_rows(2)

    # header format
    worksheet.format_cell('B1:2', bold=True, background_color=GREEN, text_color=WHITE)
    worksheet.format_cell('B2:2', text_align='CENTER')

    # ids column format
    worksheet.format_cell('A', vertical_align='MIDDLE')

    # all other rows format
    worksheet.format_cell(f'B3:{rows}', vertical_align='MIDDLE', wrap='WRAP')

    # worksheet.set_col_width('B', 100)  # category name
    worksheet.set_col_width('C', 50)  # max category points
    worksheet.set_col_width('D', 150)  # name
    worksheet.set_col_width('E', 50)  # tier
    worksheet.set_col_width('F', 75)  # points
    worksheet.set_col_width('G', 200)  # grader caption
    worksheet.set_col_width('H', 650)  # explanation
    worksheet.set_col_width('I', 300)  # instructions
    # worksheet.set_col_width('J', 100)  # is template
    worksheet.set_col_width('K:O', 75)  # instances columns

    # TODO: conditional formatting for instances?
    #  https://developers.google.com/sheets/api/samples/conditional-formatting
    #  would need to update Worksheet (or at least add custom requests method)

    # merge upvote and downvote header
    worksheet.merge_cells('L2:M2')
    worksheet.merge_cells('N2:O2')

    # hide id and explanation columns
    worksheet.hide_col('A')
    worksheet.hide_col('H')

    # update worksheet
    worksheet.update()

    logger.debug('Displayed all rubric comments for "{}" assignment', a_name)


def display_all_rubric_comments(assignments, worksheets, comments):
    """Displays rubric comments on a sheet.

    Args:
        assignments (list[codepost.models.assignments.Assignments]): The assignments.
        worksheets (dict[int, Worksheet]): The Worksheet objects in the format:
            { assignment_id: worksheet }
        comments (dict[int, dict[int, list]]): The rubric comments in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.info('Displaying rubric comments on sheet')

    # display all assignments
    for assignment in assignments:
        a_id = assignment.id
        a_name = assignment.name

        worksheet = worksheets[a_id]
        a_data = comments[a_id]

        display_assignment_comments(a_name, worksheet, list(a_data.values()))

    logger.info('Displayed all rubric comments on sheet')


# ===========================================================================

def display_assignment_instances(a_name, worksheet, values):
    """Displays instance counts for an assignment on a worksheet.

    Args:
        a_name (str): The assignment name.
        worksheet (Worksheet): The worksheet.
        values (list): The instance counts.
    """

    logger.debug('Displaying instance counts for "{}" assignment', a_name)

    # add values
    worksheet.set_values('K3', values)

    # format feedback percent columns
    worksheet.format_number_cell('M', 'PERCENT', '0.0%')
    worksheet.format_number_cell('O', 'PERCENT', '0.0%')

    # update worksheet
    worksheet.update()

    logger.debug('Displayed all instance counts for "{}" assignment', a_name)


def display_all_instances(assignments, worksheets, instances):
    """Displays instance counts on a Google Sheet.

    Args:
        assignments (list[codepost.models.assignments.Assignments]): The assignments.
        worksheets (dict[int, Worksheet]): The Worksheet objects in the format:
            { assignment_id: worksheet }
        instances (dict[int, dict[int, list]]): The instance counts in the format:
            { assignment_id: { comment_id: [values] } }
    """

    logger.info('Displaying instance counts on sheet')

    for assignment in assignments:
        a_id = assignment.id
        a_name = assignment.name

        worksheet = worksheets[a_id]
        a_data = instances[a_id]

        display_assignment_instances(a_name, worksheet, list(a_data.values()))

    logger.info('Displayed all instance counts on sheet')


# ===========================================================================

@click.command()
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
def main(course_period, sheet_name, start_assignment, end_assignment, wipe, replace, instances, testing):
    """
    Exports a codePost rubric to a Google Sheet.

    \b
    Args:
        course_period (str): The period of the COS126 course to export from.
        sheet_name (str): The name of the sheet to import the rubrics to.
        start_assignment (str): The assignment to start getting rubrics for.
            Default is the first one.
        end_assignment (str): The assignment to stop getting rubrics for (inclusive).
            If `start_assignment` is not given, default is the last one.
            If `start_assignment` is given, default is the same as `start_assignment`. \f
        wipe (bool): Whether to wipe the current sheet.
            Default is False.
        replace (bool): Whether to replace the existing sheets.
            Default is False.
        instances (bool): Whether to count instances of rubric comments.
            Default is False.
        testing (bool): Whether to run as a test.
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

    logger.info('Getting assignments range')
    if testing and start_assignment is None and end_assignment is None:
        assignments = [min(course.assignments, key=lambda a: a.sortKey)]
    else:
        assignments = get_assignments_range(course, start_assignment, end_assignment)
    if len(assignments) == 0:
        logger.error('No assignments to parse through')
        return

    comments = get_all_rubric_comments(assignments)

    worksheets = get_worksheets(sheet, assignments, wipe, replace)

    display_all_rubric_comments(assignments, worksheets, comments)

    if instances:

        # count and display for each assignment (avoids runtime errors)
        logger.info('Getting instances of all rubric comments')
        for assignment in assignments:
            a_id = assignment.id
            a_name = assignment.name
            c_ids = list(comments[a_id].keys())[2:]
            worksheet = worksheets[a_id]

            # need to skip the first 2 rows to get only comment ids
            instances = get_assignment_instances(assignment, c_ids)

            display_assignment_instances(a_name, worksheet, list(instances.values()))
        logger.info('Got all instances of all rubric comments')

        # count all instances, then display all instances
        # ids = dict()
        # for a_id, values in comments.items():
        #     # need to skip the first 2 rows to get only comment ids
        #     ids[a_id] = list(values.keys())[2:]
        #
        # instances = get_all_instances(assignments, ids)
        #
        # display_all_instances(assignments, worksheets, instances)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {}', format_time(end - start))


# ===========================================================================

if __name__ == '__main__':
    main()
