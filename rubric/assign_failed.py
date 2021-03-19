"""
assign_failed.py
Assign all submissions that fail tests to a grader.

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
import time
import comma

from shared import *

# ===========================================================================

DUMP_FILE = 'output/failed_tests_submissions.csv'


# ===========================================================================

def get_num_tests(assignment) -> int:
    """Gets the number of tests for this assignment.

    Args:
        assignment (codepost.models.assignments.Assignment): The assignment.

    Returns:
        int: The number of tests.
    """
    return sum(len(category.testCases) for category in assignment.testCategories)


# ===========================================================================

def get_failed_submissions(assignment, cutoff, total_tests, search_all=False) -> dict[int, tuple[str, int]]:
    """Gets all the failed submissions from an assignment.

    Args:
        assignment (codepost.models.assignments.Assignment): The assignment.
        cutoff (int): The number of tests that denote "passed". Must be positive.
        total_tests (int): The total number of tests for this assignment.
        search_all (bool): Whether to search all submissions, not just those with no grader.
            Default is False.

    Returns:
        dict[int, tuple[str, int]]: The failed submissions, in the format:
            { submission_id: (students, tests_passed) }
    """

    if cutoff > total_tests:
        logger.info('All submissions will pass less than {} out of {} tests', cutoff, total_tests)
        return dict()
    if cutoff == total_tests:
        logger.info('Searching for submissions that failed any of {} tests', total_tests)
    else:
        logger.info('Searching for submissions that pass less than {} out of {} tests', cutoff, total_tests)

    failed_submissions = dict()
    num_failed = 0

    submissions = assignment.list_submissions()
    for i, submission in enumerate(submissions):
        if submission.isFinalized: continue

        # only submissions that have no grader
        if not search_all and submission.grader is not None: continue

        s_id = submission.id
        students = ';'.join(submission.students)

        # count tests
        all_tests = submission.tests
        total_tests = len(all_tests)
        failed_count = len([test for test in all_tests if not test.passed])
        passed_count = total_tests - failed_count

        if total_tests == 0 or passed_count < cutoff:
            # no tests at all (compile error or related) or didn't meet cutoff
            failed_submissions[s_id] = (students, passed_count)
            num_failed += 1

        if i % 100 == 99:
            logger.debug('Done with submission {}', i + 1)

    logger.debug('Found {} failed submissions', num_failed)

    return failed_submissions


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
@click.option('-c', '--cutoff', type=click.IntRange(1, None),
              help='The number of tests that denote "passed". Must be positive. Default is all passed.')
@click.option('-sa', '--search-all', is_flag=True, default=False, flag_value=True,
              help='Whether to search all submissions, not just those with no grader. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, grader, cutoff, search_all, testing):
    """Assign all submissions that fail tests to a grader.
    Saves all failed submissions to a `.csv` file.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment.
        grader (str): The grader to assign the submissions to. Accepts netid or email. \f
        cutoff (int): The number of tests that denote "passed". Must be positive.
            Default is all passed.
        search_all (bool): Whether to search all submissions, not just those with no grader.
            Default is False.
        testing (bool): Whether to run as a test.
            Default is False.
    """

    start = time.time()

    logger.info('Start')

    logger.info('Logging in to codePost')
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

    grader = make_email(grader)
    logger.info('Validating grader "{}"', grader)
    validated = validate_grader(course, grader)
    if not validated:
        logger.error('Grader "{}" is not a valid grader in this course', grader)
        return

    logger.info('Getting "{}" assignment', assignment_name)
    assignment = get_assignment(course, assignment_name)
    if assignment is None:
        return

    total_tests = get_num_tests(assignment)

    if cutoff is None:
        cutoff = total_tests

    failed_submissions = get_failed_submissions(assignment, cutoff, total_tests, search_all)

    if len(failed_submissions) > 0:
        # save to file
        data = list()
        tests_key = f'passed_out_of_{total_tests}'
        for s_id, (student_names, passed) in failed_submissions.items():
            row = {
                'submission_id': s_id,
                'students': student_names,
                tests_key: passed,
            }
            data.append(row)
        data.sort(key=lambda r: r[tests_key])
        comma.dump(data, DUMP_FILE)

        # assign submissions
        assign_submissions(grader, list(failed_submissions.keys()))

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {}', format_time(end - start))


# ===========================================================================

if __name__ == '__main__':
    main()
