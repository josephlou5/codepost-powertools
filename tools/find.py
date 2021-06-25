"""
find.py
Finds submissions by given search flags.
"""

# ===========================================================================

from typing import (
    List,
)

from loguru import logger

from shared import *
from shared_codepost import *
from shared_output import *

# ===========================================================================

# globals

FOUND_FILE = 'found.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         grader: str = None,
         student: str = None,
         search_all: bool = False,
         finalized: bool = False,
         drafts: bool = False,
         unclaimed: bool = False,
         log: bool = False
         ) -> List[Submission]:
    """Finds submissions by given search flags.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        grader (str): The grader to filter.
            Default is None.
        student (str): The student to filter.
            Ignores all other arguments.
            Default is None.
        search_all (bool): Find all submissions.
            Default is False.
        finalized (bool): Find the finalized submissions.
            Default is False.
        drafts (bool): Find the draft submissions.
            Default is False.
        unclaimed (bool): Find the unclaimed submissions.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Submission]: The submissions found.
    """

    if (search_all, finalized, drafts, unclaimed) == (False,) * 4:
        if log: logger.info('All search flags are false; no submissions found')
        return list()
    if grader is not None and unclaimed and not finalized and not drafts:
        if log: logger.info('No submissions are unclaimed and claimed by a grader')
        return list()

    success = log_in_codepost(log=log)
    if not success: return list()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return list()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return list()

    # filter student
    if student is not None:
        success = validate_student(course, student, log=log)
        if not success: return list()

        submissions = assignment.list_submissions(student=student)
        if len(submissions) == 0:
            if log: logger.info('Student "{}" does not have a submission for "{}"', student, assignment_name)
            return list()

        if log:
            submission = submissions[0]
            logger.info('Submission {}', submission.id)
            logger.info('Student: {}', ','.join(submission.students))
            logger.info('Grader: {}', submission.grader)
            logger.info('Finalized: {}', submission.isFinalized)

        return submissions

    # filter grader
    if grader is not None:
        success = validate_grader(course, grader, log=log)
        if not success: return list()
        submissions = assignment.list_submissions(grader=grader)

        # no matter what `unclaimed` is, doesn't change the result
        if finalized and drafts:
            adj = 'all submissions claimed'
        elif finalized:
            adj = 'submissions finalized'
        elif drafts:
            adj = 'draft submissions claimed'
        else:
            adj = 'never happens'
        if log: logger.info('Finding {} by "{}"', adj, grader)

    else:
        submissions = assignment.list_submissions()

        if log:
            if search_all or (finalized and drafts and unclaimed):
                adj = 'all'
            else:
                # two flags are true
                if finalized and drafts:
                    adj = 'claimed'
                elif finalized and unclaimed:
                    adj = 'non-draft'
                elif drafts and unclaimed:
                    adj = 'unfinalized'
                # one flag is true
                elif finalized:
                    adj = 'finalized'
                elif drafts:
                    adj = 'draft'
                elif unclaimed:
                    adj = 'unclaimed'
                # no flags are true; shouldn't happen
                else:
                    adj = 'never happens'
            logger.info('Finding {} submissions', adj)

    found = list()
    data = list()

    for submission in submissions:

        # if a search flag is false, don't allow those submissions
        if ((not finalized and submission.isFinalized) or
                (not drafts and (submission.grader is not None and not submission.isFinalized)) or
                (not unclaimed and submission.grader is None)):
            continue

        found.append(submission)

        data.append({
            'submission_id': submission.id,
            'grader': submission.grader,
            'finalized': submission.isFinalized,
        })

    if log: logger.debug('Found {} submissions', len(found))

    filepath = get_path(file=FOUND_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='found submissions', log=log)

    return found

# ===========================================================================
