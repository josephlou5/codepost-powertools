"""
track_comments.py
Track rubric comment usage for students and graders.

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs
"""

# ===========================================================================

import datetime
import click
from loguru import logger
import codepost
import time

from shared import *

# ===========================================================================

# report file template
"""
REPORT.txt
Last updated 2021/02/23

SUMMARY
Hello: submitted, graded, viewed
Loops: submitted, graded, not viewed
NBody: submitted, not graded, not viewed

COMMENTS
Hello
    comment1
    comment2
Loops
    comment1
    comment3
"""

REPORT_FILENAME = 'REPORT.txt'
REPORT_EXT = '.txt'

TODAY = datetime.date.today()


# ===========================================================================

def summary(assignment_name, submitted=False, graded=False, viewed=False) -> str:
    """Create summary string for an assignment.

    Args:
        assignment_name (str): The assignment name.
        submitted (bool): Whether the submission was submitted.
        graded (bool): Whether the submission was graded.
        viewed (bool): Whether the submission was viewed by the student.

    Returns:
        str: The summary string.
    """

    # return (assignment_name + ': '
    #         + ('submitted' if submitted else 'not submitted') + ', '
    #         + ('graded' if graded else 'not graded') + ', '
    #         + ('viewed' if viewed else 'not viewed'))

    return (assignment_name + ': '
            + ('submitted' if submitted else 'not submitted') + ', '
            + ('graded' if graded else 'not graded'))


def remove_duplicates(lst) -> list:
    """Remove duplicates from a list of strings while preserving order.

    Args:
        lst (list): The list with possible duplicates.

    Returns:
        list: The elements in the same order with duplicates removed.
    """

    return list(dict.fromkeys(lst).keys())


# ===========================================================================


def get_rubric_comments(assignment) -> dict:
    """Gets all the rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The comments in the format:
            { comment_id: comment_name }
    """

    comments = dict()

    for category in assignment.rubricCategories:
        for comment in category.rubricComments:
            comments[comment.id] = comment.name

    return comments


# ===========================================================================

def get_student_assignment_comments(assignment) -> dict:
    """Gets student rubric comment usage on an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The data in the format:
            { student: (assignment_summary, [comments]) }
    """

    data = dict()

    submissions = assignment.list_submissions()
    if len(submissions) == 0:
        return data

    comments = get_rubric_comments(assignment)

    for submission in submissions:

        assignment_summary = summary(assignment.name,
                                     submitted=True,
                                     graded=submission.isFinalized and assignment.isReleased)

        submission_comments = list()
        for f in submission.files:
            for c in f.comments:
                if c.rubricComment is None:
                    continue
                submission_comments.append(comments[c.rubricComment])

        for student in submission.students:
            # each student should only appear once in each assignment,
            # so this shouldn't be overriding any students
            data[student] = (assignment_summary, submission_comments)

    return data


def get_student_comments(course, stop_assignment_name, by='assignment') -> dict:
    """Gets student rubric comment usage on all assignments.

    Args:
        course (codepost.models.courses.Courses): The course.
        stop_assignment_name (str): The name of the assignment to stop at (does not parse this assignment).
        by (str): The format to return the data.
                assignment: { student: ( [summaries], { assignment_name: [comments] } ) }
                comment: { student: ( [summaries], { comment: [assignments] } ) }
            Default is 'assignment'. Invalid values will be set to default.

    Returns:
        dict: The data in the specified format.
    """

    by = by.lower()
    if by not in ('assignment', 'comment'):
        logger.warning('Invalid value for "by": "{}"', by)
        by = 'assignment'

    logger.info('Getting student rubric comment usage by {}', by.upper())

    data = dict()

    all_students = set()

    for assignment in sorted(course.assignments, key=lambda a: a.sortKey):

        a_name = assignment.name

        if a_name == stop_assignment_name:
            break

        # get data for this assignment
        logger.debug('Getting rubric comment usage for "{}" assignment', a_name)
        this_assignment = get_student_assignment_comments(assignment)

        # save data
        students_in_assignment = set(this_assignment.keys())
        students_to_add = students_in_assignment - all_students
        students_not_here = all_students - students_in_assignment

        for student in students_to_add:
            data[student] = (list(), dict())
            all_students.add(student)

        for student, (assignment_summary, comments) in this_assignment.items():

            data[student][0].append(assignment_summary)

            if by == 'assignment':
                # each student should only appear once in each assignment,
                # so a student shouldn't have this assignment yet
                data[student][1][a_name] = comments

            elif by == 'comment':
                for comment in comments:
                    if comment not in data[student][1]:
                        data[student][1][comment] = list()
                    data[student][1][comment].append(a_name)

        for student in students_not_here:
            data[student][0].append(summary(a_name))
            if by == 'assignment':
                data[student][1][a_name] = list()

    return data


# ===========================================================================

# TODO: get grader rubric comment usage as well

def get_grader_assignment_comments(assignment) -> dict:
    """Gets grader rubric comment usage on an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The data in the format:
            { grader: [comments] }
            { grader: { student: [comments] }
    """
    pass


def get_grader_comments(by='assignment') -> dict:
    """Gets grader rubric comment usage on all assignments.

    Args:
        by (str): The format to return the data.
            assignment: { grader: { assignment_name: [comments] } }
            comment: { grader: { comment: [assignments] } }

    Raises:
        ValueError: If by does not receive a proper argument.

    Returns:
        dict: The data in the specified format.
    """
    pass


# ===========================================================================

def create_reports(data, by='assignment') -> dict:
    """Creates the report files for each student.

    Args:
        data (dict): The data.
        by (str): The format of the data.

    Returns:
        dict: The reports in the format:
            { student: report_code }
    """

    logger.info('Creating report files for each student')

    reports = dict()

    for student, (summaries, info) in data.items():
        report_str = ''

        # summary
        report_str += 'SUMMARY\n' + '\n'.join(summaries) + '\n\n'

        # comments
        report_str += 'COMMENTS\n'
        if by == 'assignment':
            for a_name, comments in info.items():
                report_str += a_name + '\n'
                for comment in comments:
                    report_str += (' ' * 4) + comment + '\n'
        elif by == 'comment':
            for comment, assignments in info.items():
                report_str += comment + '\n'
                for assignment in remove_duplicates(assignments):
                    report_str += (' ' * 4) + assignment + '\n'

        reports[student] = report_str + '\n'

    return reports


# ===========================================================================

def apply_reports(assignment, reports):
    """Applies the report files to each student's submission.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
        reports (dict): The reports in the format:
            { student: report_str }
    """

    logger.info('Applying reports to assignment "{}"', assignment.name)

    for i, submission in enumerate(assignment.list_submissions()):

        if submission.isFinalized: continue

        report_code = (REPORT_FILENAME + '\nLast updated: ' + str(TODAY) + '\n\n' +
                       '\n'.join(reports[student] for student in submission.students if student in reports))

        # no reports exist for the students
        if report_code == '':
            logger.debug('Submission {}: Students had no reports', submission.id)
            continue

        # replace file if exists
        for file in submission.files:
            if file.name == REPORT_FILENAME:
                codepost.file.update(
                    id=file.id,
                    code=report_code,
                )
                break
        else:
            # create new file
            codepost.file.create(
                name=REPORT_FILENAME,
                code=report_code,
                extension=REPORT_EXT,
                submission=submission.id,
            )

        # DEBUG
        # logger.debug('Submission {}: Created "{}"', submission.id, REPORT_FILENAME)

        if i > 0 and i % 100 == 0:
            logger.debug('Done with submission {}', i + 1)


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('by', type=str, required=False)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, by, testing):
    """
    Track rubric comment usage for students and graders.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment to apply the reports to.
        by (str): The format to return the data.
                assignment: assignment_name -> [comments]
                comment: comment -> [assignments]
            Default is 'assignment'. Invalid values will be set to default. \f
        testing (bool): Whether to run as a test.
            Default is False.
    """

    start = time.time()

    logger.info('Start')

    logger.info('Logging into codePost')
    success = log_in_codepost()
    if not success:
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

    logger.info(f'Getting "{assignment_name}" assignment')
    assignment = get_assignment(course, assignment_name)
    if assignment is None:
        return

    if by is not None:
        by = by.lower()
    if by not in ('assignment', 'comment'):
        by = 'assignment'

    logger.info('Getting ')
    data = get_student_comments(course, assignment_name, by)

    reports = create_reports(data, by)

    apply_reports(assignment, reports)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {:.2f} sec', end - start)


# ===========================================================================

if __name__ == '__main__':
    main()