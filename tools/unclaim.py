"""
unclaim.py
Unclaims submissions.
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

UNCLAIMED_FILE = 'unclaimed.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         file: str = None,
         grader: str = DUMMY_GRADER,
         num: int = None,
         percentage: int = 100,
         unfinalize: bool = False,
         log: bool = False
         ) -> List[Submission]:
    """Unclaims submissions.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        file (str): The file of submissions to unclaim.
            Default is None.
        grader (str): The grader to unclaim from.
            Default is `DUMMY_GRADER`.
        num (int): The number of submissions to unclaim.
            Overrides `percentage` if both given.
            Default is all.
        percentage (int): The percentage of submissions to unclaim, as an int (e.g. 60% is 60).
            Default is 100%.
        unfinalize (bool): Whether to unclaim and unfinalize finalized submissions.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.

    Raises:
        ValueError:
            If `num` is not positive.
            If `percentage` is not between 1-100.

    Returns:
        List[Submission]: The submissions unclaimed.
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
    # getting from grader
    else:
        if log: logger.info('Getting submissions claimed by grader "{}"', grader)
        submissions = list(filter(lambda s: s.grader == grader, assignment.list_submissions()))
        if log: logger.debug('Found {} submissions', len(submissions))

    num_submissions = len(submissions)

    # get number of submissions to unclaim
    if num is not None:
        num = min(num, num_submissions)
    else:
        num = int(percentage / 100 * num_submissions)

    if num <= 0:
        if log: logger.info('No submissions to unclaim')
        return list()

    # unclaim submissions
    if log:
        if num == num_submissions:
            logger.info('Unclaiming all {} submissions', num_submissions)
        else:
            logger.info('Unclaiming {} of {} submissions', num, num_submissions)

    unclaiming = submissions[:num]
    unclaimed = list()
    data = list()

    for submission in unclaiming:
        s_id = submission.id

        if submission.isFinalized:
            if not unfinalize:
                if log: logger.warning('Submission {} is finalized; unfinalizing', s_id)
            else:
                if log: logger.warning('Submission {} is finalized; cannot unclaim', s_id)
                continue

        unclaimed.append(submission)

        data.append({
            'submission_id': s_id,
            'students': ';'.join(submission.students),
            'old_grader': submission.grader,
            'was_finalized': submission.isFinalized,
        })

        codepost.submission.update(s_id, isFinalized=False, grader='')

    if log: logger.info('Unclaimed {} submissions', len(unclaimed))

    filepath = get_path(file=UNCLAIMED_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='unclaimed submissions', log=log)

    return unclaimed

# ===========================================================================
