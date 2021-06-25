"""
ids.py
Creates mapping between student emails and submission IDs.
"""

# ===========================================================================

from typing import (
    Dict,
    Optional,
)

from loguru import logger

from shared_codepost import *
from shared_output import *

# ===========================================================================

# globals

MAPPING_FILE = 'ids.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         log: bool = False
         ) -> Dict[str, Optional[int]]:
    """Creates mapping between student emails and submission IDs.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Dict[str, Optional[int]]: The student emails mapped to the submission ids.
    """

    success = log_in_codepost(log=log)
    if not success: return dict()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return dict()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return dict()

    if log: logger.info('Getting submissions')

    mapping: Dict[str, Optional[int]] = dict()
    data = list()

    for submission in assignment.list_submissions():
        s_id = submission.id
        for student in submission.students:
            mapping[student] = s_id
            data.append({
                'submission_id': s_id,
                'email': student,
            })

    filepath = get_path(file=MAPPING_FILE, course=course, assignment=assignment)
    save_csv(data, filepath, description='ids', log=log)

    return mapping

# ===========================================================================
