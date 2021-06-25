"""
failed.py
Finds submissions that failed tests.
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

TESTS_FiLE = 'tests.csv'
FAILED_FILE = 'failed.csv'


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         cutoff: int = None,
         log: bool = False
         ) -> Dict[int, List[Submission]]:
    """Finds submissions that failed tests.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        cutoff (int): The number of tests that denote "passed".
            Default is all passed.
        log (bool): Whether to show log messages.
            Default is False.

    Raises:
        ValueError: If `cutoff` is not positive.

    Returns:
        Dict[int, List[Submission]]: The submissions sorted by the number of tests passed.
    """

    # check args
    if cutoff is not None and cutoff <= 0:
        raise ValueError('`cutoff` must be positive')

    success = log_in_codepost(log=log)
    if not success: return dict()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return dict()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return dict()

    # get test categories and test cases
    # maps test category key -> number of cases
    test_max = dict()
    # maps test case id -> test category key
    test_cases = dict()
    for category in assignment.testCategories:
        c_name = category.name
        cases = category.testCases
        num_cases = len(cases)

        test_category_key = f'{c_name}_{num_cases}'
        for case in cases:
            test_max[test_category_key] = num_cases
            test_cases[case.id] = test_category_key
    total_tests = sum(test_max.values())
    total_key = f'total_out_of_{total_tests}'

    # default is all tests passed
    if cutoff is None:
        cutoff = total_tests

    if cutoff > total_tests:
        if log: logger.info('All submissions will pass less than {} out of {} tests', cutoff, total_tests)
        return assignment.list_submissions()

    if log:
        if cutoff == total_tests:
            logger.info('Finding submissions that failed any of {} tests', total_tests)
        else:
            logger.info('Finding submissions that pass less than {} out of {} tests', cutoff, total_tests)

    failed = dict()
    data = list()
    data_failed = list()

    for submission in assignment.list_submissions():

        # count tests
        s_tests = submission.tests
        passed = {test_category_key: 0 for test_category_key in test_max.keys()}
        for test in s_tests:
            test_category = test_cases[test.testCase]
            if test.passed:
                passed[test_category] += 1
        num_passed = sum(passed.values())

        row = {
            'submission_id': submission.id,
            'students': ';'.join(submission.students),
            total_key: num_passed,
        }
        for test_category_key, num_cases_passed in passed.items():
            row[test_category_key] = num_cases_passed

        if len(s_tests) == 0 or num_passed < cutoff:
            # no tests at all (compile error or other error) or didn't meet cutoff
            if num_passed not in failed:
                failed[num_passed] = list()
            failed[num_passed].append(submission)

            data_failed.append(row)

        data.append(row)

    if log: logger.debug('Found {} failed submissions', len(data_failed))

    sort_keys = (total_key,) + tuple(test_max.keys())

    data.sort(key=lambda r: tuple(r[key] for key in sort_keys))
    filepath = get_path(file=TESTS_FiLE, course=course, assignment=assignment)
    save_csv(data, filepath, description='test results', log=log)

    data_failed.sort(key=lambda r: tuple(r[key] for key in sort_keys))
    filepath = get_path(file=FAILED_FILE, course=course, assignment=assignment)
    save_csv(data_failed, filepath, description='failed submissions', log=log)

    # sort keys in ascending order
    failed = {k: v for (k, v) in sorted(failed.items())}
    return failed

# ===========================================================================
