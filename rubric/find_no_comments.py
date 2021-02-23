"""
find_no_comments.py
Find all submissions that have no comments.

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
    if assignment is None:
        logger.critical('Assignment "{}" not found', a_name)
    return assignment


# ===========================================================================

def get_no_comment_submissions(assignment) -> (dict, dict):
    """Gets all submissions with no comments in the assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        (dict, dict): The finalized submissions with no comments
            and unfinalized submissions with no comments (not including unclaimed),
            in the format:
                { submission_id: grader }
    """

    logger.info('Getting submissions with no comments')

    finalized = dict()
    submissions = dict()

    for s in assignment.list_submissions():
        has_comments = False
        for f in s.files:
            if len(f.comments) > 0:
                has_comments = True
                break
        if has_comments: continue

        if s.isFinalized:
            if s.grader is None:
                # no grader, finalized with no comments
                finalized[s.id] = None
            else:
                # grader finalized with no comments
                finalized[s.id] = s.grader
        else:
            if s.grader is None:
                # no grader and not finalized; unclaimed submission
                pass
            else:
                # grader, not finalized, but no comments; assume still working
                submissions[s.id] = s.grader

    logger.debug('Got {} finalized submissions and {} unfinalized submissions', len(finalized), len(submissions))

    return finalized, submissions


# ===========================================================================

def list_submissions(finalized, submissions=None):
    """Lists submissions and their graders.

    Args:
        finalized (dict): The finalized submissions in the format:
            {submission_id: grader}
        submissions (dict): The unfinalized submissions in the format:
            {submission_id: grader}
            Default is None.
    """

    logger.info('  '.join(('ID'.ljust(6),'Final?','Grader')))
    for s_id, grader in finalized.items():
        logger.info('  '.join((f'{s_id:6}', 'Yes'.ljust(6), grader)))
    if submissions is not None:
        for s_id, grader in submissions.items():
            logger.info('  '.join((f'{s_id:6}', 'No'.ljust(6), grader)))

# ===========================================================================

def open_submissions(submissions):
    """Makes submissions "open": unfinalized with no grader.

    Args:
        submissions (Iterable): The ids of the submissions to open.
    """

    logger.info('Opening submissions')

    for s_id in submissions:
        codepost.submission.update(s_id, grader='', isFinalized=False)

    logger.debug('Opened {} submissions', len(submissions))


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-lf', '--list-finalized', is_flag=True, default=False, flag_value=True,
              help='Whether to list finalized submissions that have no comments. Default is False.')
@click.option('-la', '--list-all', is_flag=True, default=False, flag_value=True,
              help='Whether to list all submissions that have no comments. Default is False.')
@click.option('-of', '--open-finalized', is_flag=True, default=False, flag_value=True,
              help='Whether to open finalized submissions that have no comments. Default is False.')
@click.option('-oa', '--open-all', is_flag=True, default=False, flag_value=True,
              help='Whether to open all submissions that have no comments. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, list_finalized, list_all, open_finalized, open_all, testing):
    """
    Find all submissions that have no comments.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment. \f
        list_finalized (bool): Whether to list finalized submissions that have no comments.
            Default is False.
        list_all (bool): Whether to list all submissions that have no comments.
            Default is False.
        open_finalized (bool): Whether to open finalized submissions that have no comments.
            Default is False.
        open_all (bool): Whether to open all submissions that have no comments.
            Default is False.
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

    logger.info(f'Getting "{assignment_name}" assignment')
    assignment = get_assignment(course, assignment_name)
    if assignment is None:
        return

    finalized, submissions = get_no_comment_submissions(assignment)

    if list_all:
        list_submissions(finalized, submissions)
    elif list_finalized:
        list_submissions(finalized)

    if open_all:
        open_submissions(list(finalized.keys()) + list(submissions.keys()))
    elif open_finalized:
        open_submissions(finalized.keys())

    logger.info('Done')


# ===========================================================================

if __name__ == '__main__':
    main()
