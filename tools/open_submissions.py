"""
open_submissions.py
Opens submissions (unfinalizes and unclaims).
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

OPENED_FILE = 'opened.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         file: str,
         drafts: bool = False,
         log: bool = False
         ) -> List[Submission]:
    """Opens submissions (unfinalizes and unclaims).

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        file (str): The file of submissions to open.
        drafts (bool): Whether to open draft submissions.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Submission]: The submissions opened.
    """

    success = log_in_codepost(log=log)
    if not success: return list()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return list()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return list()

    # reading from file
    submissions = read_submissions_from_file(file, log=log)

    # open submissions
    if log: logger.info('Opening {} submissions', len(submissions))

    opened = list()
    data = list()

    for submission in submissions:
        s_id = submission.id

        if submission.grader is None:
            if log: logger.warning('Submission {} is already opened', s_id)
            continue
        if not submission.isFinalized:
            if log: logger.warning('Submission {} is a draft', s_id)
            if not drafts: continue

        opened.append(submission)

        data.append({
            'submission_id': s_id,
            'students': ';'.join(submission.students),
            'old_grader': submission.grader,
            'was_finalized': submission.isFinalized,
        })

        codepost.submission.update(s_id, isFinalized=False, grader='')

    if log: logger.info('Opened {} submissions', len(opened))

    filepath = get_path(file=OPENED_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='opened submissions', log=log)

    return opened

# ===========================================================================
