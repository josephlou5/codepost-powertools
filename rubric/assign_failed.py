"""
assign_failed.py
Assign all submissions that fail tests to a grader.
Cannot detect cases of all tests not running (0 total tests).

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

from shared import *

# ===========================================================================

FAILED_FILE = 'failed_tests_submissions.txt'


# ===========================================================================

def validate_grader(course, grader) -> bool:
    """Checks if a grader is a valid grader in a course."""

    roster = codepost.roster.retrieve(course.id)
    return grader in roster.graders


# ===========================================================================

def get_failed_submissions(assignment, cutoff, search_all) -> (list, list, int):
    """Gets all the failed submissions from an assignment.

    Args:
        assignment (codepost.models.assignments.Assignment): The assignment.
        cutoff (int): The number of tests that denote "passed".
        search_all (bool): Whether to search all submissions, not just those with no grader.

    Returns:
        (list, list, int): The failed submission ids, the name of the students,
            and the number of failed submissions.
    """

    failed_submissions = list()
    student_names = list()

    submissions = assignment.list_submissions()
    for submission in submissions:
        if submission.isFinalized: continue
        # only submissions that have no grader
        if not search_all and submission.grader is not None: continue
        if len(submission.tests) == 0:
            # no tests, add
            failed_submissions.append(submission.id)
            student_names += submission.students
        elif cutoff is None:
            # if fail one test, add
            if not next((t.passed for t in submission.tests if not t.passed), True):
                failed_submissions.append(submission.id)
                student_names += submission.students
        else:
            # if passed less than cutoff, add
            if len([t for t in submission.tests if t.passed]) < cutoff:
                failed_submissions.append(submission.id)
                student_names += submission.students

    num_failed = len(failed_submissions)
    logger.debug('Found {} failed submissions', num_failed)

    return failed_submissions, student_names, num_failed


# ===========================================================================

def assign_submissions(grader, submissions):
    """Assign submissions to a grader.

    Args:
        grader (str): The grader to assign to. Assumed to be a valid grader.
        submissions (list): The submission ids.
    """

    logger.info('Assigning submissions to grader')
    for s_id in submissions:
        codepost.submission.update(s_id, grader=grader)


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('grader', type=str, required=True)
@click.argument('cutoff', type=int, required=False)
@click.option('-sa', '--search-all', is_flag=True, default=False, flag_value=True,
              help='Whether to search all submissions, not just those with no grader. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, grader, cutoff, search_all, testing):
    """Assign all submissions that fail tests to a grader.
    Cannot detect cases of all tests not running (0 total tests).

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment.
        grader (str): The grader to assign the submissions to.
        cutoff (int): The number of tests that denote "passed".
            Default is all passed. \f
        search_all (bool): Whether to search all submissions, not just those with no grader.
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

    validated = validate_grader(course, grader)
    if not validated:
        logger.error('Grader "{}" is not a valid grader in this course', grader)
        return
    logger.info('Grader validated')

    logger.info('Getting "{}" assignment', assignment_name)
    assignment = get_assignment(course, assignment_name)
    if assignment is None:
        return

    if cutoff is None:
        logger.info('Searching for submissions that failed any tests')
    else:
        logger.info('Searching for submissions that passed less than {} tests', cutoff)

    failed_submissions, student_names, num_failed = get_failed_submissions(assignment, cutoff, search_all)

    if num_failed > 0:
        # save in file
        with open(FAILED_FILE, 'w') as f:
            f.write('\n'.join(student_names) + '\n')
        # assign submissions
        assign_submissions(grader, failed_submissions)

    logger.info('Done')


# ===========================================================================

if __name__ == '__main__':
    main()
