"""
claim.py
Claims submissions.
"""

# ===========================================================================

from typing import (
    List,
)

import codepost
from loguru import logger

from shared import *
from shared_codepost import *
from shared_output import *

# ===========================================================================

# globals

CLAIMED_FILE = 'claimed.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         file: str = None,
         grader: str = DUMMY_GRADER,
         num: int = None,
         percentage: int = 100,
         log: bool = False
         ) -> List[Submission]:
    """Claims submissions.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        file (str): The file of submissions to claim.
            Default is None.
        grader (str): The grader to claim to.
            Default is `DUMMY_GRADER`.
        num (int): The number of submissions to claim.
            Overrides `percentage` if both given.
            Default is all.
        percentage (int): The percentage of submissions to claim, as an int (e.g. 60% is 60).
            Default is 100%.
        log (bool): Whether to show log messages.
            Default is False.

    Raises:
        ValueError:
            If `num` is not positive.
            If `percentage` is not between 1-100.

    Returns:
        List[Submission]: The submissions claimed.
    """

    # check args
    if num is not None and num <= 0:
        raise ValueError('`num` must be positive')
    if not 1 <= percentage <= 100:
        raise ValueError('`percentage` must be between 1-100')

    success = log_in_codepost(log=log)
    if not success: return list()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return list()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return list()

    # reading from file
    if file is not None:
        submissions = read_submissions_from_file(file, log=log)
    # getting from queue
    else:
        if log: logger.info('Getting submissions from grading queue')
        submissions = sorted(filter(lambda s: not s.isFinalized, assignment.list_submissions()),
                             key=lambda s: s.sortKey)
        if log: logger.debug('Found {} submissions', len(submissions))

    num_submissions = len(submissions)

    # get number of submissions to claim
    if num is not None:
        num = min(num, num_submissions)
    else:
        num = int(percentage / 100 * num_submissions)

    if num <= 0:
        if log: logger.info('No submissions to claim')
        return list()

    # claim submissions
    if log:
        if num == num_submissions:
            logger.info('Claiming all {} submissions', num_submissions)
        else:
            logger.info('Claiming {} of {} submissions', num, num_submissions)

    claiming = submissions[:num]
    data = list()

    for submission in claiming:
        s_id = submission.id

        data.append({
            'submission_id': s_id,
            'students': ';'.join(submission.students),
            'old_grader': submission.grader,
            'new_grader': grader,
            'finalized': submission.isFinalized,
        })

        codepost.submission.update(s_id, grader=grader)

    if log: logger.info('Claimed {} submissions', num)

    filepath = get_path(file=CLAIMED_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='claimed submissions', log=log)

    return claiming

# ===========================================================================
