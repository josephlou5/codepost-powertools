"""
tier_report.py
Generates a report of the comment tiers.
"""

# ===========================================================================

from typing import (
    List, Tuple, Dict
)

from loguru import logger

from shared import *
from shared_codepost import *
from shared_output import *

# ===========================================================================

REPORT_FILENAME = 'tier_report.csv'


# ===========================================================================


def get_rubric_comments(assignment: Assignment) -> Dict[int, Tuple[str, int]]:
    """Gets all the rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.

    Returns:
        Dict[int, Tuple[str, int]]: The comments in the format:
                { comment_id: (name, tier) }
            Tier 0 means the comment does not belong to a tier.
    """

    comments = dict()

    for category in assignment.rubricCategories:
        for comment in category.rubricComments:
            # get tier if has it
            match = TIER_PATTERN.match(comment.text)
            if match is None:
                tier = 0
            else:
                tier = int(match.groups()[0])

            # saving comment
            comments[comment.id] = (comment.name, tier)

    return comments


# ===========================================================================

def create_report(assignment: Assignment,
                  log: bool = False,
                  progress_interval: int = 100
                  ) -> Tuple[List[Dict], List[int]]:
    """Creates the tier report for this assignment.

    Args:
        assignment (Assignment): The assignment.
        log (bool): Whether to show log messages.
            Default is False.
        progress_interval (int): The interval at which to show submission counts.
            If less than 0, nothing is shown.
            Default is 100.

    Returns:
        Tuple[List[Dict], List[int]]: The report in the dict format:
                [ (submission_id, students, grader, grade, comments, T1, T2, T3, no_tier, rubric, custom) ]
            and the unfinalized submissions.
    """

    if log: logger.debug('Getting rubric comment tiers for "{}" assignment', assignment.name)

    submissions = assignment.list_submissions()
    if len(submissions) == 0:
        return list(), list()

    comments = get_rubric_comments(assignment)

    data = list()
    unfinalized = list()

    for i, submission in enumerate(submissions):

        if not submission.isFinalized:
            unfinalized.append(submission.id)
            continue

        num_comments = 0
        num_tiers = [0, 0, 0, 0]
        num_rubric = 0
        num_custom = 0

        for file in submission.files:
            for comment in file.comments:
                num_comments += 1
                if comment.rubricComment is None:
                    num_custom += 1
                    continue
                num_rubric += 1
                _, tier = comments[comment.rubricComment]
                num_tiers[tier] += 1

        data.append({
            'submission_id': submission.id,
            'students': ';'.join(submission.students),
            'grader': submission.grader,
            'grade': submission.grade,
            'comments': num_comments,
            'T1': num_tiers[1],
            'T2': num_tiers[2],
            'T3': num_tiers[3],
            'no_tier': num_tiers[0],
            'rubric': num_rubric,
            'custom': num_custom,
        })

        if log and progress_interval > 0 and (i + 1) % progress_interval == 0:
            logger.debug('Done with submission {}', i + 1)

    return data, unfinalized


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         log: bool = False
         ):
    """Generates a report of tier comments usage.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        log (bool): Whether to show log messages.
            Default is False.
    """

    success = log_in_codepost(log=log)
    if not success: return

    success, course = get_course(course_name, course_period, log=log)
    if not success: return

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return

    report, unfinalized = create_report(assignment, log=log)

    if log and len(unfinalized) > 0:
        logger.debug('{} unfinalized submissions', len(unfinalized))

    filepath = get_path(file=REPORT_FILENAME, course=course, assignment=assignment)
    save_csv(report, filepath, description='report', log=log)

# ===========================================================================
