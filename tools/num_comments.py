"""
num_comments.py
Counts the number of applied comments.
"""

# ===========================================================================

from typing import (
    List, Dict,
)

from loguru import logger

from shared import *
from shared_codepost import *
from shared_output import *

# ===========================================================================

# globals

COMMENTS_FILE = 'num_comments.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         count_rubric: bool = True,
         count_custom: bool = True,
         search_all: bool = False,
         search_finalized: bool = False,
         search_drafts: bool = False,
         search_unclaimed: bool = False,
         log: bool = False
         ) -> Dict[int, List[Submission]]:
    """Counts the number of applied comments.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        count_rubric (bool): Whether to count rubric comments.
            Default is True.
        count_custom (bool): Whether to count custom comments.
            Default is True.
        search_all (bool): Search all submissions.
            Default is False.
        search_finalized (bool): Search the finalized submissions.
            Default is False.
        search_drafts (bool): Search the draft submissions.
            Default is False.
        search_unclaimed (bool): Search the unclaimed submissions.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Dict[int, List[Submission]]: The submissions sorted by the number of comments.
    """

    if (count_rubric, count_custom) == (False,) * 2:
        if log: logger.info('All comment type flags are false; all submissions will have 0 comments')
        return dict()
    if (search_all, search_finalized, search_drafts, search_unclaimed) == (False,) * 4:
        if log: logger.info('All search flags are false; no submissions found')
        return dict()

    success = log_in_codepost(log=log)
    if not success: return dict()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return dict()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return dict()

    submissions: Dict[int, List[Submission]] = dict()

    if log:
        if search_all or (search_finalized and search_drafts and search_unclaimed):
            adj = 'all'
        else:
            # two flags are true
            if search_finalized and search_drafts:
                adj = 'claimed'
            elif search_finalized and search_unclaimed:
                adj = 'non-draft'
            elif search_drafts and search_unclaimed:
                adj = 'unfinalized'
            # one flag is true
            elif search_finalized:
                adj = 'finalized'
            elif search_drafts:
                adj = 'draft'
            elif search_unclaimed:
                adj = 'unclaimed'
            # no flags are true; shouldn't happen
            else:
                adj = 'never happens'
        logger.info('Counting comments of {} submissions', adj)

    data = list()

    for submission in assignment.list_submissions():

        # if a search flag is false, don't allow those submissions
        if ((not search_finalized and submission.isFinalized) or
                (not search_drafts and (submission.grader is not None and not submission.isFinalized)) or
                (not search_unclaimed and submission.grader is None)):
            continue

        # count comments
        custom_comments = 0
        rubric_comments = 0
        for file in submission.files:
            for comment in file.comments:
                if comment.rubricComment is None:
                    custom_comments += 1
                else:
                    rubric_comments += 1

        # filter comment type
        if count_rubric and count_custom:
            num_comments = custom_comments + rubric_comments
        elif count_rubric:
            num_comments = rubric_comments
        elif count_custom:
            num_comments = custom_comments
        else:
            # shouldn't happen
            num_comments = -1
        if num_comments not in submissions:
            submissions[num_comments] = list()
        submissions[num_comments].append(submission)

        data.append({
            'submission_id': submission.id,
            'grader': submission.grader,
            'finalized': submission.isFinalized,
            'comments': rubric_comments + custom_comments,
            'rubric_comments': rubric_comments,
            'custom_comments': custom_comments,
        })

    filepath = get_path(file=COMMENTS_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='counts', log=log)

    # sort keys in ascending order
    submissions = {k: v for (k, v) in sorted(submissions.items())}
    return submissions

# ===========================================================================
