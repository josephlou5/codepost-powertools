"""
assign_failed.py
Assign all submissions that fail any tests to a grader.

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs
"""

# ===========================================================================

import click
from loguru import logger
import codepost
import codepost.models.assignments

from shared import *


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
    return assignment


# ===========================================================================

def validate_grader(course, grader) -> bool:
    """Checks if a grader is a valid grader in a course."""

    roster = codepost.roster.retrieve(course.id)
    return grader in roster.graders


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('grader', type=str, required=True)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def assign_failed(course_period, assignment_name, grader, testing):
    """Assign all submissions that fail any tests to a grader.

    \b
    Args:
        course_period (str): The period of the COS126 course to import to.
        assignment_name (str): The name of the assignment.
        grader (str): The grader to assign the submissions to. \f
        testing (bool): Whether to run as a test.
            Default is False.
    """

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

    validated = validate_grader(course, grader)
    if not validated:
        logger.error(f'Grader "{grader}" is not a valid grader in this course')
        return
    logger.info('Grader validated')

    logger.info(f'Getting "{assignment_name}" assignment')
    assignment = get_assignment(course, assignment_name)

    logger.info('Searching for submissions that failed at least one test')

    failed_submissions = list()

    submissions = assignment.list_submissions(grader=None)
    for submission in submissions:
        if submission.isFinalized: continue
        for t in submission.tests:
            if not t.passed:
                failed_submissions.append(submission.id)
                break

    num_failed = len(failed_submissions)
    logger.debug(f'Found {num_failed} submissions')

    if num_failed > 0:
        logger.info('Assigning submissions to grader')
        for s_id in failed_submissions:
            codepost.submission.update(s_id, grader=grader)

    logger.info('Done')


# ===========================================================================

if __name__ == '__main__':
    assign_failed()
