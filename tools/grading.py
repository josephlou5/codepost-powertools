"""
grading.py
Grading related operations.

Commands:
claim - Claims submissions to a grader
unclaim - Unclaims submissions
ids - Creates mapping between student netids and submission ids
find - Finds submissions
failed - Finds submissions that fail tests
finalize - Finalizes submissions
stats - Lists current stats of the grading queue

GitHub repo:
https://github.com/josephlou5/codepost-powertools

TODO: command pipe
"""

# ===========================================================================

# imports pygame if needed

import datetime
import os
import time
from functools import update_wrapper
from random import shuffle
from typing import (
    Any,
    Sequence, List, Tuple, Mapping,
    Union,
    Callable,
)

import click
import codepost
import codepost.models.submissions
import comma
from loguru import logger

from shared import *

# ===========================================================================

# outputs
FILES = {
    'claim': 'claimed_{}_{}.csv',
    'tests': 'tests_{}_{}.csv',
    'failed': 'failed_{}_{}.csv',
    'found': 'found_{}_{}.csv',
    'finalize': 'finalized_{}_{}.csv',
    'ids': 'mapping_{}_{}.csv',
    'unclaim': 'unclaimed_{}_{}.csv',
}

# globals
DUMMY_GRADER = 'jdlou+dummygrader@princeton.edu'

# constants
CTX_SETTINGS = {
    'context_settings': {'ignore_unknown_options': True}
}
BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)
GREEN: Color = (0, 175, 0)
RED: Color = (255, 0, 0)
YELLOW: Color = (255, 255, 0)


# ===========================================================================

def read_submissions_from_file(filepath: str, ext: str, objs: bool = False) -> Union[List[int], List[Submission]]:
    """Reads submissions from a file.

    Args:
        filepath (str): The file.
        ext (str): The file extension.
        objs (bool): Whether to get the Submission objects.
            Default is False.
            Takes about 0.165 sec to retrieve one submission.

    Returns:
        list[int]: The list of submission ids.
        list[Submission]: The list of submissions.
    """

    logger.info('Reading submissions from file')

    submissions = list()

    if ext == '.txt':
        with open(filepath, 'r') as f:
            submissions = [int(line.strip()) for line in f.read().split('\n') if line.strip().isdigit()]
    elif ext == '.csv':
        data = comma.load(filepath, force_header=True)
        S_ID_KEY = 'submission_id'
        if S_ID_KEY not in data.header:
            logger.warning('File "{}" does not have a "{}" column', filepath, S_ID_KEY)
        else:
            for s_id in data[S_ID_KEY]:
                try:
                    submissions.append(int(s_id.strip()))
                except ValueError:
                    pass

    if len(submissions) == 0:
        logger.warning('No submissions found in file')
    else:
        logger.debug('Found {} submissions', len(submissions))

        if objs:
            submissions = [codepost.submission.retrieve(s_id) for s_id in submissions]

    return submissions


def dump_to_file(msg: str, data: Sequence[Mapping[str, Any]], filename: str, course: Course = None,
                 assignment_name: str = None):
    """Dumps data to a file.

    Args:
        msg (str): The logger message.
        data (Sequence[Mapping[str, Any]]): The data in csv format.
        filename (str): The filename.
        course (Course): The course.
            Default is None. If not given, not included in filename.
        assignment_name (str): The assignment name.
            Default is None. If not given, not included in filename.
    """

    if len(data) == 0:
        logger.info('No data to save to file')
        return

    logger.info(msg)

    fmts = list()
    if course is not None:
        fmts.append(course_str(course, delim='_'))
    if assignment_name is not None:
        fmts.append(assignment_name.replace(' ', ''))

    if len(fmts) == 0:
        actual_filename = filename
    else:
        actual_filename = filename.format(*fmts)

    output_file = os.path.join(OUTPUT_FOLDER, actual_filename)

    if not os.path.exists(OUTPUT_FOLDER):
        os.mkdir(OUTPUT_FOLDER)

    comma.dump(data, output_file)


def filter_submissions(action: str, submissions: List[Submission],
                       num: int = None, percentage: int = 100, random: bool = False) -> List[Submission]:
    """Filters submissions.

    Args:
        action (str): Whether claiming or unclaiming.
        submissions (List[Submission]): The submissions.
        num (int): The number of submissions to keep.
            Default is all.
        percentage (int): The percentage of submissions to keep.
            Default is 100%.
        random (bool): Whether to keep random submissions.
            Default is False.

    Returns:
        List[Submission]: The filtered submissions.
    """

    action = action.title()

    num_submissions = len(submissions)

    # filter submissions
    if num is not None:
        # if num is given, use it
        num_keep = num
        if num_keep >= num_submissions:
            num_keep = num_submissions
            msg = ('{} all {} submissions', action, num_submissions)
        else:
            random_str = 'random ' if random else ''
            msg = ('{} %s{} of {} submissions' % random_str, action, num_keep, num_submissions)
    else:
        # if num is not given, fall back on percentage
        num_keep = int(num_submissions * percentage / 100)
        if percentage == 100:
            msg = ('{} all {} submissions', action, num_submissions)
        else:
            random_str = 'random ' if random else ''
            msg = ('{} %s{}%% of {} submissions' % random_str, action, percentage, num_submissions)
    logger.info(*msg)

    copy = submissions[:]

    # randomness
    if random:
        shuffle(copy)

    return copy[:num_keep]


# ===========================================================================

# https://github.com/pallets/click/issues/513#issuecomment-504158316
class NaturalOrderGroup(click.Group):
    def list_commands(self, ctx):
        return self.commands.keys()


@click.group(cls=NaturalOrderGroup)
def cli():
    """Grading related operations."""
    pass


def wrap(f):
    """Decorator for start and end."""

    @click.pass_context
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        start = time.time()
        logger.info('Start')

        # do function
        ctx.invoke(f, ctx, **kwargs)

        logger.info('Done')
        end = time.time()
        logger.info('Total time: {}', format_time(end - start))

    return update_wrapper(main, f)


def driver(f):
    """Decorator for main driver."""

    @click.pass_context
    @wrap
    def main(ctx, *args, **kwargs):

        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        course_period = kwargs['course_period']
        assignment_name = kwargs['assignment_name']

        logger.info('Logging into codePost')
        success = log_in_codepost()
        if not success:
            return

        logger.info('Accessing codePost course')
        if kwargs.get('testing', False):
            logger.info('Running as test: Opening Joseph\'s Course')
            course = get_course("Joseph's Course", 'S2021')
        else:
            logger.info('Accessing COS126 course for period "{}"', course_period)
            course = get_126_course(course_period)
        if course is None:
            return

        logger.info('Getting "{}" assignment', assignment_name)
        assignment = get_assignment(course, assignment_name)
        if assignment is None:
            return

        kwargs['COURSE'] = course
        kwargs['ASSIGNMENT'] = assignment

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


def with_grader(f):
    """Decorator for main driver with a grader."""

    @click.pass_context
    @driver
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        course = kwargs['COURSE']
        grader = kwargs.get('grader', DUMMY_GRADER)

        grader = make_email(grader)
        logger.info('Validating grader "{}"', grader)
        validated = validate_grader(course, grader)
        if not validated:
            return

        # update grader
        kwargs['grader'] = grader

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


def with_file(f):
    """Decorator for main driver with a file."""

    @click.pass_context
    @driver
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        file = kwargs['file']

        if file is not None:
            filepath, file_ext = validate_file(file)

            # update kwargs
            kwargs['filepath'] = filepath
            kwargs['file ext'] = file_ext

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


def with_grader_and_file(f):
    """Decorator for main driver with a grader and a file."""

    @click.pass_context
    @driver
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        course = kwargs['COURSE']
        file = kwargs['file']
        grader = kwargs.get('grader', DUMMY_GRADER)

        grader = make_email(grader)
        logger.info('Validating grader "{}"', grader)
        validated = validate_grader(course, grader)
        if not validated:
            return

        # update grader
        kwargs['grader'] = grader

        if file is not None:
            filepath, file_ext = validate_file(file)

            # update kwargs
            kwargs['filepath'] = filepath
            kwargs['file ext'] = file_ext

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


# ===========================================================================

@cli.command(
    'claim',
    **CTX_SETTINGS,
    help='Claims submissions to a grader.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=False)
@click.option('-g', '--grader', type=str, default=DUMMY_GRADER,
              help='The grader to claim to. Accepts netid or email. Default is DUMMY_GRADER.')
@click.option('-n', '--num', type=click.IntRange(1, None),
              help='The number of submissions to claim. Overrides `percentage` if both given. Default is ALL.')
@click.option('-p', '--percentage', type=click.IntRange(1, 100), default=100,
              help='The percentage of submissions to claim, as an `int` (e.g. 60% is 60). Default is 100%.')
@click.option('-r', '--random', is_flag=True, default=False, flag_value=True,
              help='Whether to claim random submissions. Default is False.')
@click.option('-sa', '--search-all', is_flag=True, default=False, flag_value=True,
              help='Search all submissions. Default is False.')
@click.option('-uf', '--unfinalized', is_flag=True, default=False, flag_value=True,
              help='Search unfinalized submissions. Default is False.')
@click.option('-uc', '--unclaimed', is_flag=True, default=False, flag_value=True,
              help='Search unclaimed submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@with_grader_and_file
def claim_cmd(*args, **kwargs):
    """Claims submissions to a grader."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    file = kwargs['file']
    filepath = kwargs.get('filepath', None)
    file_ext = kwargs.get('file ext', None)
    grader = kwargs.get('grader', DUMMY_GRADER)
    num = kwargs.get('num', None)
    percentage = kwargs.get('percentage', 100)
    random = kwargs.get('random', False)
    search_all = kwargs.get('search_all', False)
    unclaimed = kwargs.get('unclaimed', True)
    unfinalized = kwargs.get('unfinalized', False)

    logger.info('Getting submissions to claim')

    submissions = list()

    # reading from file
    if file is not None:
        submissions: List[Submission] = read_submissions_from_file(filepath, file_ext, objs=True)

    # search through assignment submissions
    if len(submissions) == 0:
        logger.info('Getting submissions from assignment')
        all_submissions = assignment.list_submissions()
        if search_all:
            submissions = all_submissions
        elif unfinalized:
            submissions = [s for s in all_submissions if not s.isFinalized]
        elif unclaimed:
            submissions = [s for s in all_submissions if s.grader is None]
        else:
            logger.error('All search flags are False')
            return

    if len(submissions) == 0:
        logger.info('No submissions to claim')
        return

    claiming = filter_submissions('Claiming', submissions, num, percentage, random)

    # claim submissions
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

    logger.debug('Claimed {} submissions to "{}"', len(claiming), grader)

    # dump to file
    dump_to_file('Saving claimed submissions to file',
                 data, FILES['claim'], course, assignment_name)


# ===========================================================================

@cli.command(
    'unclaim',
    **CTX_SETTINGS,
    help='Unclaims submissions.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=False)
@click.option('-u', '--unfinalize', is_flag=True, default=False, flag_value=True,
              help='Whether to unfinalize and unclaim finalized submissions. Default is False.')
@click.option('-n', '--num', type=click.IntRange(1, None),
              help='The number of submissions to unclaim. Overrides `percentage` if both given. Default is ALL.')
@click.option('-p', '--percentage', type=click.IntRange(1, 100), default=100,
              help='The percentage of submissions to unclaim, as an `int` (e.g. 60% is 60). Default is 100%.')
@click.option('-r', '--random', is_flag=True, default=False, flag_value=True,
              help='Whether to unclaim random submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@with_file
def unclaim_cmd(*args, **kwargs):
    """
    Unclaims submissions.
    Displays warning for finalized submissions.
    """

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    file = kwargs['file']
    filepath = kwargs.get('filepath', None)
    file_ext = kwargs.get('file ext', None)
    unfinalize = kwargs.get('unfinalize', False)
    num = kwargs.get('num', None)
    percentage = kwargs.get('percentage', 100)
    random = kwargs.get('random', False)

    logger.info('Getting submissions to unclaim')

    if file is not None:
        # reading from file
        submissions: List[Submission] = read_submissions_from_file(filepath, file_ext, objs=True)
    else:
        # getting from dummy grader
        logger.debug('Getting submissions from dummy grader "{}"', DUMMY_GRADER)
        submissions = assignment.list_submissions(grader=DUMMY_GRADER)

    num_submissions = len(submissions)

    if num_submissions == 0:
        logger.info('No submissions to unclaim')
        return

    unclaiming = filter_submissions('Unclaiming', submissions, num, percentage, random)

    # unclaim submissions
    data = list()
    for submission in unclaiming:
        s_id = submission.id

        if submission.isFinalized:
            if unfinalize:
                logger.warning('Submission {} is finalized; unfinalizing', s_id)
            else:
                logger.warning('Submission {} is finalized; cannot unclaim', s_id)
                continue

        data.append({
            'submission_id': s_id,
            'students': ';'.join(submission.students),
            'old_grader': submission.grader,
            'was_finalized': submission.isFinalized,
        })

        codepost.submission.update(s_id, grader='', isFinalized=False)

    logger.debug('Unclaimed {} submissions', len(unclaiming))

    # dump to file
    dump_to_file('Saving unclaimed submissions to file',
                 data, FILES['unclaim'], course, assignment_name)


# ===========================================================================

@cli.command(
    'ids',
    **CTX_SETTINGS,
    help='Creates mapping between student netids and submission ids.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def ids_cmd(*args, **kwargs):
    """Creates mapping between student netids and submission ids."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    logger.info('Getting submissions')

    data = list()

    submissions = assignment.list_submissions()
    for submission in submissions:
        s_id = submission.id
        for student in submission.students:
            data.append({
                'submission_id': s_id,
                'netid': student.split('@')[0],
                'email': student,
            })

    logger.debug('Found {} submissions', len(submissions))

    # dump to file
    dump_to_file('Saving mapping to file',
                 data, FILES['ids'], course, assignment_name)


# ===========================================================================

@cli.command(
    'find',
    **CTX_SETTINGS,
    help='Finds submissions. Returns intersection of search flags.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-g', '--grader', type=str,
              help='The grader to filter. Accepts netid or email.')
@click.option('-s', '--student', type=str,
              help='The student to filter. Accepts netid or email.')
@click.option('-f', '--finalized', is_flag=True, default=False, flag_value=True,
              help='Find finalized submissions. Default is False.')
@click.option('-uf', '--unfinalized', is_flag=True, default=False, flag_value=True,
              help='Find unfinalized submissions. Default is False.')
@click.option('-c', '--claimed', is_flag=True, default=False, flag_value=True,
              help='Find claimed submissions. Default is False.')
@click.option('-uc', '--unclaimed', is_flag=True, default=False, flag_value=True,
              help='Find unclaimed submissions. Default is False.')
@click.option('-d', '--drafts', is_flag=True, default=False, flag_value=True,
              help='Find drafts. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def find_cmd(*args, **kwargs):
    """Finds submissions. Returns intersection of search flags."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    grader = kwargs.get('grader', None)
    student = kwargs.get('student', None)
    finalized = kwargs.get('finalized', False)
    unfinalized = kwargs.get('unfinalized', False)
    claimed = kwargs.get('claimed', False)
    unclaimed = kwargs.get('unclaimed', False)
    drafts = kwargs.get('drafts', False)

    # get student's submission
    if student is not None:
        student = make_email(student)
        validated = student in codepost.roster.retrieve(course.id).students
        if not validated:
            logger.error('Invalid student in {}: "{}"', course_str(course), student)
            return

        submissions = assignment.list_submissions(student=student)
        if len(submissions) == 0:
            logger.info('Student "{}" does not have a submission for "{}"', student, assignment_name)
            return

        submission = submissions[0]
        logger.info('Submission {}', submission.id)
        logger.info('Student: {}', ','.join(submission.students))
        logger.info('Grader: {}', submission.grader)
        logger.info('Finalized: {}', submission.isFinalized)
        return

    # validate grader
    if grader is not None:
        grader = make_email(grader)
        validated = validate_grader(course, grader)
        if not validated:
            return

    if grader is None and True not in (finalized, unfinalized, claimed, unclaimed, drafts):
        logger.error('All search flags are False')
        return

    # check for empty intersections
    if finalized and unfinalized:
        logger.info('There are no submissions that are both finalized and unfinalized')
        return
    if finalized and unclaimed:
        logger.info('There are no submissions that are both finalized and unclaimed')
        return
    if finalized and drafts:
        logger.info('There are no submissions that are both finalized and drafts')
        return
    if (claimed or grader is not None) and unclaimed:
        logger.info('There are no submissions that are both claimed and unclaimed')
        return
    if unclaimed and drafts:
        logger.info('There are no submissions that are both unclaimed and drafts')
        return

    searching = list()
    if finalized: searching.append('finalized')
    if unfinalized: searching.append('unfinalized')
    if claimed: searching.append('claimed')
    if unclaimed: searching.append('unclaimed')
    if drafts: searching.append('drafts')
    logger.info('Finding submissions that are {}', ', '.join(searching))

    # drafts are unfinalized and claimed
    if drafts:
        unfinalized = True
        claimed = True

    data = list()

    for submission in assignment.list_submissions():

        if finalized and not submission.isFinalized:
            continue
        if unfinalized and submission.isFinalized:
            continue
        if claimed and submission.grader is None:
            continue
        if unclaimed and submission.grader is not None:
            continue
        if grader is not None and submission.grader != grader:
            continue

        data.append({
            'submission_id': submission.id,
            'students': ';'.join(submission.students),
            'grader': submission.grader,
            'finalized': submission.isFinalized,
        })

    logger.debug('Found {} submissions', len(data))

    # dump to file
    dump_to_file('Saving found submissions to file',
                 data, FILES['found'], course, assignment_name)


# ===========================================================================

@cli.command(
    'failed',
    **CTX_SETTINGS,
    help='Finds submissions that failed tests.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-c', '--cutoff', type=click.IntRange(1, None),
              help='The number of tests that denote "passed". Default is all passed.')
@click.option('-sa', '--search-all', is_flag=True, default=False, flag_value=True,
              help='Whether to search all submissions, not just those with no grader. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def failed_cmd(*args, **kwargs):
    """Finds submissions that failed tests."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    cutoff = kwargs.get('cutoff', None)
    search_all = kwargs.get('search_all', False)

    total_tests = sum(len(category.testCases) for category in assignment.testCategories)

    if cutoff is None:
        cutoff = total_tests

    if cutoff > total_tests:
        logger.info('All submissions will pass less than {} out of {} tests', cutoff, total_tests)
        return
    if cutoff == total_tests:
        logger.info('Finding submissions that failed any of {} tests', total_tests)
    else:
        logger.info('Finding submissions that pass less than {} out of {} tests', cutoff, total_tests)

    failed_submissions = dict()
    num_failed = 0
    data = list()
    data_failed = list()
    TESTS_KEY = f'passed_out_of_{total_tests}'

    for i, submission in enumerate(assignment.list_submissions()):
        if submission.isFinalized: continue

        # only submissions that have no grader
        if not search_all and submission.grader is not None: continue

        s_id = submission.id
        students = ';'.join(submission.students)

        # count tests
        all_tests = submission.tests
        total_tests = len(all_tests)
        failed_count = len([test for test in all_tests if not test.passed])
        passed_count = total_tests - failed_count

        row = {
            'submission_id': s_id,
            'students': students,
            TESTS_KEY: passed_count,
        }
        data.append(row)

        if total_tests == 0 or passed_count < cutoff:
            # no tests at all (compile error or related) or didn't meet cutoff
            failed_submissions[s_id] = (students, passed_count)
            num_failed += 1

            data_failed.append(row)

        if i % 100 == 99:
            logger.debug('Done with submission {}', i + 1)

    logger.debug('Found {} failed submissions', num_failed)

    # dump to file
    data.sort(key=lambda r: r[TESTS_KEY])
    data_failed.sort(key=lambda r: r[TESTS_KEY])

    dump_to_file('Saving test results to file',
                 data, FILES['tests'], course, assignment)
    dump_to_file('Saving failed submissions to file',
                 data_failed, FILES['failed'], course, assignment_name)


# ===========================================================================

@cli.command(
    'finalize',
    **CTX_SETTINGS,
    help='Finalizes submissions.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=True)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@with_file
def finalize_cmd(*args, **kwargs):
    """Finalizes submissions."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment_name = kwargs['assignment_name']

    filepath = kwargs['filepath']
    file_ext = kwargs['file ext']

    # get submissions
    submissions: List[Submission] = read_submissions_from_file(filepath, file_ext, objs=True)

    if len(submissions) == 0:
        return

    # finalize submissions
    logger.info('Finalizing {} submissions', len(submissions))

    data = list()

    for submission in submissions:
        s_id = submission.id

        if submission.grader is None:
            logger.warning('Submission {}: no grader; cannot finalize', s_id)
            continue
        if submission.isFinalized:
            logger.warning('Submission {}: already finalized', s_id)
            continue

        data.append({
            'submission_id': s_id,
            'students': ';'.join(submission.students),
            'grader': submission.grader,
        })

        codepost.submission.update(s_id, isFinalized=True)

    logger.debug('Finalized {} submissions', len(data))

    # dump to file
    dump_to_file('Saving finalized submissions to file',
                 data, FILES['finalize'], course, assignment_name)


# ===========================================================================

@cli.command(
    'stats',
    **CTX_SETTINGS,
    help='Lists current stats of the grading queue.'
)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-w', '--window', type=click.IntRange(10, None),
              help=('The window update interval in seconds. Must be at least 10. '
                    'If not given, will not display window.'))
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def stats_cmd(*args, **kwargs):
    """
    Lists current stats of the grading queue.

    Expected time: < 10 seconds.
    """

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    course = kwargs['COURSE']
    assignment = kwargs['ASSIGNMENT']

    window = kwargs.get('window', None)

    def get_counts() -> Tuple[int, int, int, int, int, int, int]:
        """Gets the stats counts for an assignment."""
        submissions = assignment.list_submissions()
        num_finalized = 0
        num_unfinalized = 0
        num_unclaimed = 0
        num_drafts = 0
        num_dummy_grader = 0
        for s in submissions:
            if s.isFinalized:
                num_finalized += 1
                continue
            num_unfinalized += 1
            if s.grader is None:
                num_unclaimed += 1
            elif s.grader == DUMMY_GRADER:
                num_dummy_grader += 1
            else:
                num_drafts += 1
        num_unfinalized -= num_dummy_grader
        num_claimed = num_finalized + num_drafts
        return (
            len(submissions),
            num_finalized, num_unfinalized,
            num_claimed, num_unclaimed,
            num_drafts, num_dummy_grader
        )

    if window is None:
        logger.info('Getting stats')
        total, n_finalized, unfinalized, claimed, unclaimed, drafts, dummy_grader = get_counts()
        # display stats
        logger.info('{} total submissions', total)
        logger.info('{:<3d} [{:>6.2%}] finalized ', n_finalized, n_finalized / total)
        logger.info('{:<3d} [{:>6.2%}] unfinalized', unfinalized, unfinalized / total)
        logger.info('{:<3d} [{:>6.2%}] claimed', claimed, claimed / total)
        logger.info('{:<3d} [{:>6.2%}] unclaimed', unclaimed, unclaimed / total)
        logger.info('{:<3d} [{:>6.2%}] drafts', drafts, drafts / total)
        if dummy_grader > 0:
            logger.info('{:<3d} [{:>6.2%}] claimed by dummy grader', dummy_grader, dummy_grader / total)
        return

    logger.info('Displaying window')
    title = f'Stats for {course_str(course)} {assignment.name}'
    stats_window(title, get_counts, window)


def stats_window(title: str, get_counts: Callable[[], Tuple[int, int, int, int, int, int, int]], interval: int):
    """Display the stats window.

    Args:
        title (str): The title of the window.
        get_counts (Callable[[], Tuple[int, int, int, int, int, int, int]]):
            A method that returns the stats counts for an assignment.
        interval (int): The second interval for updating the window.
    """

    # only importing pygame if needed
    # don't print pygame welcome and support
    pygame_key = 'PYGAME_HIDE_SUPPORT_PROMPT'
    old_val = os.environ.get(pygame_key, None)
    os.environ[pygame_key] = 'hide'
    import pygame
    if old_val is None:
        os.environ.pop(pygame_key)
    else:
        os.environ[pygame_key] = old_val
    del pygame_key, old_val

    def create_text(font_obj: pygame.font.Font,
                    x: float, y: float, text: str,
                    color: Color = BLACK, align: str = 'LEFT',
                    min_x: float = None, max_x: float = None
                    ) -> Tuple[pygame.SurfaceType, Tuple[float, float]]:
        """Creates args for displaying text with `surface.blit()`.

        Args:
            font_obj (pygame.font.Font): The font object.
            x (float): The x-position.
            y (float): The y-position.
            text (str): The text to display.
            color (Color): The color of the text.
                Default is BLACK.
            align (str): The alignment of the text with respect to (x,y).
                Default is LEFT.
                Choices: LEFT, CENTER, RIGHT.
            min_x (float): The minimum x-value.
                Default is None.
            max_x (float): The maximum x-value.
                Default is None.

        Returns:
            Tuple[pygame.SurfaceType, Tuple[float, float]]: The args.
        """

        text = str(text)
        width, height = font_obj.size(text)

        px = x
        py = y - height / 2

        if align == 'CENTER':
            px = x - width / 2
        elif align == 'RIGHT':
            px = x - width

        if min_x is not None and px < min_x:
            px = min_x
        elif max_x is not None and px > max_x - width:
            px = max_x - width

        return font_obj.render(text, True, color), (px, py)

    # constants
    font = 'sfprotext'
    monofont = 'sfnsmono'

    # use pygame to display window
    pygame.init()

    # set up window
    screen_width = 500
    screen_height = 250
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption(title)

    clock = pygame.time.Clock()

    # create text
    text25 = pygame.font.SysFont(font, 25)
    text15 = pygame.font.SysFont(font, 15)
    mono15 = pygame.font.SysFont(monofont, 15)

    title_text = create_text(text25, screen_width / 2, 20, title, align='CENTER')
    status_y = 45
    # loading_text = create_text(text15, screen_width / 2, status_y, 'Getting stats...', align='CENTER')
    nums_y = 70
    nums_dy = 25
    rect_x = 10
    nums_x0 = 30
    nums_x1 = 150
    nums_x2 = 220
    text_labels = ('Total', 'Finalized', 'Unfinalized', 'Claimed', 'Unclaimed', 'Drafts', 'Held')
    labels = [create_text(text15, nums_x0, nums_y + i * nums_dy, text) for i, text in enumerate(text_labels)]
    # rects
    side = 10
    rects = list()
    rects.append((GREEN, pygame.Rect(rect_x, nums_y + 1 * nums_dy - side / 2, side, side)))  # finalized
    rects.append((YELLOW, pygame.Rect(rect_x, nums_y + 2 * nums_dy - side / 2, side, side / 2)))  # unfinalized
    rects.append((RED, pygame.Rect(rect_x, nums_y + 2 * nums_dy, side, side / 2)))
    rects.append((GREEN, pygame.Rect(rect_x, nums_y + 3 * nums_dy - side / 2, side / 2, side)))  # claimed
    rects.append((YELLOW, pygame.Rect(rect_x + side / 2, nums_y + 3 * nums_dy - side / 2, side / 2, side)))
    rects.append((RED, pygame.Rect(rect_x, nums_y + 4 * nums_dy - side / 2, side, side)))  # unclaimed
    rects.append((YELLOW, pygame.Rect(rect_x, nums_y + 5 * nums_dy - side / 2, side, side)))  # drafts
    rects.append((BLACK, pygame.Rect(rect_x, nums_y + 6 * nums_dy - side / 2, side, side)))  # dummy grader / held
    borders = [(BLACK, pygame.Rect(rect_x - 1, nums_y + (i + 1) * nums_dy - side / 2 - 1, side + 2, side + 2), 1)
               for i in range(len(text_labels) - 1)]

    # stats box
    stats_width = 250
    stats_height = 150
    stats_pos = (235, 70)
    stats_box = pygame.Surface((stats_width, stats_height))
    stats_box.fill(WHITE)

    # initial screen
    screen.fill(WHITE)
    screen.blit(*title_text)
    screen.blit(*create_text(text25, screen_width / 2, screen_height / 2, 'Loading...', align='CENTER'))
    pygame.display.flip()

    countdown = 0

    running = True
    while running:

        dt = clock.tick() / 1000

        # check events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        if not running: break

        # wait for next interval
        if countdown > 0:
            countdown -= dt
            continue

        # get counts
        total, *counts = get_counts()
        n_finalized, unfinalized, claimed, unclaimed, drafts, dummy_grader = counts
        countdown = interval

        screen.fill(WHITE)
        screen.blit(*title_text)
        screen.blit(*create_text(text15, screen_width / 2, status_y,
                                 'Last updated: {}'.format(datetime.datetime.now().strftime('%H:%M:%S')),
                                 align='CENTER'))
        for label in labels:
            screen.blit(*label)
        for rect in rects:
            pygame.draw.rect(screen, *rect)
        for rect in borders:
            pygame.draw.rect(screen, *rect)

        # update total
        screen.blit(*create_text(mono15, nums_x1, nums_y, total, align='RIGHT'))

        if total == 0:
            # update screen
            pygame.display.flip()
            continue

        # update numbers and percentages
        for i, num in enumerate(counts):
            screen.blit(*create_text(mono15, nums_x1, nums_y + (i + 1) * nums_dy, num, align='RIGHT'))
            screen.blit(*create_text(mono15, nums_x2, nums_y + (i + 1) * nums_dy, f'{num / total:.2%}', align='RIGHT'))

        # finalized stuff
        finalized_width = n_finalized / total * stats_width
        finalized_box = pygame.Rect(0, 0, finalized_width, stats_height)
        pygame.draw.rect(stats_box, GREEN, finalized_box)

        # unfinalized stuff
        unfinalized_width = unfinalized / total * stats_width

        if unfinalized > 0:
            # drafts stuff
            drafts_height = drafts / unfinalized * stats_height
            drafts_box = pygame.Rect(finalized_width, 0, unfinalized_width, drafts_height)
            pygame.draw.rect(stats_box, YELLOW, drafts_box)

            # unclaimed stuff
            unclaimed_height = unclaimed / unfinalized * stats_height
            unclaimed_box = pygame.Rect(finalized_width, drafts_height, unfinalized_width, unclaimed_height)
            pygame.draw.rect(stats_box, RED, unclaimed_box)

        # write text underneath
        bottom_label_x = stats_pos[0]
        bottom_label_y = stats_pos[1] + stats_height + 10
        if n_finalized > 0:
            screen.blit(*create_text(text15, bottom_label_x + finalized_width / 2, bottom_label_y,
                                     'Finalized', GREEN, align='CENTER', min_x=bottom_label_x))
        if unfinalized > 0:
            screen.blit(*create_text(text15, bottom_label_x + finalized_width + unfinalized_width / 2, bottom_label_y,
                                     'Unfinalized', RED, align='CENTER',
                                     min_x=bottom_label_x + finalized_width / 2 + text15.size('Finalized')[0] / 2 + 5,
                                     max_x=stats_pos[0] + stats_width))

        # dummy grader stuff
        if dummy_grader > 0:
            dummy_grader_width = dummy_grader / total * stats_width
            dummy_grader_box = pygame.Rect(finalized_width + unfinalized_width, 0, dummy_grader_width, stats_height)
            pygame.draw.rect(stats_box, BLACK, dummy_grader_box)
            screen.blit(*create_text(text15, bottom_label_x + stats_width - dummy_grader_width / 2, bottom_label_y,
                                     'Held', align='CENTER'))

        # update screen
        screen.blit(stats_box, stats_pos)
        pygame.display.flip()

    pygame.quit()


# ===========================================================================

if __name__ == '__main__':
    cli()
