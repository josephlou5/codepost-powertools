"""
claim.py
Claims all remaining submissions to a dummy grader account,
or unclaims all submissions assigned to the dummy grader account.

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
import json

from shared import *

# ===========================================================================

DUMMY_GRADER = 'jdlou+dummygrader@princeton.edu'

DUMP_FILE = 'old_submission_graders.json'


# ===========================================================================

def validate_dummy_grader(course) -> bool:
    """Checks if the dummy grader is a valid grader in a course."""

    roster = codepost.roster.retrieve(course.id)
    return DUMMY_GRADER in roster.graders


# ===========================================================================

def claim_all_unclaimed(assignment) -> dict:
    """Claims all unclaimed submission to the dummy grader.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The old graders of all submissions, in the format:
            { submission_id: grader }
    """

    logger.info('Claiming submissions')

    old_graders = dict()
    count = 0

    for s in assignment.list_submissions():
        old_graders[s.id] = s.grader
        if s.grader is not None: continue
        count += 1
        codepost.submission.update(s.id, grader=DUMMY_GRADER)

    logger.debug('Claimed {} submissions', count)

    return old_graders


def unclaim_all_claimed(assignment):
    """Unclaims all claimed submission by the dummy grader.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
    """

    logger.info('Unclaiming submissions')

    submissions = assignment.list_submissions(grader=DUMMY_GRADER)
    for s in submissions:
        codepost.submission.update(s.id, grader='')

    logger.debug('Unclaimed {} submissions', len(submissions))


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('claiming', type=bool, required=True)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, claiming, testing):
    """
    Claims all remaining submissions to a dummy grader account,
    or unclaims all submissions assigned to the dummy grader account.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment.
        claiming (bool): Whether to claim or unclaim submissions. \f
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

    validated = validate_dummy_grader(course)
    if not validated:
        logger.error(f'Dummy grader "{DUMMY_GRADER}" is not a valid grader in this course')
        return
    logger.info('Dummy grader validated')

    logger.info(f'Getting "{assignment_name}" assignment')
    assignment = get_assignment(course, assignment_name)

    if claiming:
        old_graders = claim_all_unclaimed(assignment)
        logger.info('Dumping old graders in "{}"', DUMP_FILE)
        with open(DUMP_FILE, 'w') as f:
            json.dump(old_graders, f)
    else:
        unclaim_all_claimed(assignment)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {:.2f} sec', end - start)


# ===========================================================================

if __name__ == '__main__':
    main()
