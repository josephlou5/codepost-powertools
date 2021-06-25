"""
finalize.py
Finalizes submissions.
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

FINALIZED_FILE = 'finalized.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         file: str,
         log: bool = False
         ) -> List[Submission]:
    """Finalizes submissions.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        file (str): The file of submissions to finalize.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Submission]: The submissions finalized.
    """

    success = log_in_codepost(log=log)
    if not success: return list()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return list()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return list()

    # reading from file
    submissions = read_submissions_from_file(file, log=log)

    # finalize submissions
    if log: logger.info('Finalizing {} submissions', len(submissions))

    finalized = list()
    data = list()

    for submission in submissions:
        s_id = submission.id

        if submission.grader is None:
            if log: logger.warning('Submission {} has no grader; cannot finalize', s_id)
            continue
        if submission.isFinalized:
            if log: logger.warning('Submission {} is already finalized', s_id)
            continue

        finalized.append(submission)

        data.append({
            'submission_id': s_id,
            'students': ';'.join(submission.students),
            'grader': submission.grader,
        })

        codepost.submission.update(s_id, isFinalized=True)

    if log: logger.info('Finalized {} submissions', len(finalized))

    filepath = get_path(file=FINALIZED_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='finalized submissions', log=log)

    return finalized

# ===========================================================================
