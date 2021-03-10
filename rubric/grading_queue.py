"""
grading_queue.py
Grading queue related operations.

Commands:
claim - saves all claimed submissions to a file
    - claim all (or some) unclaimed submissions
        - if claiming a portion of unclaimed submissions, has option for randomness
    - claim all (or some) submissions from another grader
        - if claiming a portion of unclaimed submissions, has option for randomness
    - todo: ignores some grader(s) or submissions
unclaim - saves all unclaimed submissions to a file
    - unclaim all submissions claimed by a grader
    - unclaim a percentage or fixed number of submissions claimed by a grader
        - if unclaiming a portion of submissions, has option for randomness
    - todo: ignores some submissions
stats
    - lists current stats of the grading queue
    - todo: real-time stats window
finalized
    - todo: reads finalized submissions from a file
    - saves all finalized submissions to a file
    - opens all finalized submissions
audit
    - reads submissions that need to be audited from a file
    - searches for submissions that need to be audited
        - desired audit count can be specified
    - searches for finalized submissions that need to be audited
        - desired audit count can be specified
    - saves submissions that need to be audited to a file
    - opens submissions that need to be audited

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs
"""

# ===========================================================================

import os
import click
from functools import update_wrapper
from loguru import logger
import codepost
import time
from random import shuffle
import comma
import datetime

from shared import *

# ===========================================================================

THREE_HOURS = datetime.timedelta(hours=3)

# ===========================================================================

DUMMY_GRADER = 'jdlou+dummygrader@princeton.edu'

AUDIT_COMMENT = 'quality-assurance'

CLAIMED_FILE = 'output/submission_claimed.txt'
UNCLAIMED_FILE = 'output/submission_unclaimed.txt'
OPENED_FILE = 'output/submissions_opened.csv'
AUDIT_COUNTS_FILE = 'output/submissions_auditing.csv'
AUDIT_REPORT_FILE = 'output/audit_report.txt'


# ===========================================================================

def east_coast_time():
    return (datetime.datetime.now() + THREE_HOURS).strftime('%Y-%m-%d %H:%M:%S')


# ===========================================================================

def dump_to_file(filename, grader, assignment_name, submissions):
    """Dumps the given information to a file.

    Args:
        filename (str): The filename.
        grader (str): The grader.
        assignment_name (str): The assignment name.
        submissions (list[int]): The submission ids.
    """

    logger.info('Dumping submissions to "{}"', filename)
    with open(filename, 'w') as f:
        f.write(grader + '\n')
        f.write(assignment_name + '\n')
        f.write('\n'.join(map(str, submissions)))
        f.write('\n')


# ===========================================================================

@click.group()
def cli():
    """Grading queue related operations."""
    pass


def driver(f):
    """Decorator for main driver code."""

    @click.pass_context
    def main(ctx, *args, **kwargs):

        # not using args, but needs it in signature for positional arguments
        _ = args

        # get parameters
        course_period = kwargs['course_period']
        assignment_name = kwargs['assignment_name']

        start = time.time()

        logger.info('Start')

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

        logger.info('Done')

        end = time.time()

        logger.info('Total time: {}', format_time(end - start))

    return update_wrapper(main, f)


def with_grader(f):
    """Decorator for main driver code with a grader."""

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

        # update grader in case netid was given
        kwargs['grader'] = grader

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


# ===========================================================================

@cli.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-g', '--grader', type=str, default=DUMMY_GRADER,
              help='The grader to claim to. Accepts netid or email. Default is DUMMY_GRADER.')
@click.option('-f', '--from', 'from_grader', type=str,
              help='The grader to claim from. Accepts netid or email. Default is None (unclaimed submissions).')
@click.option('-n', '--num', type=click.IntRange(1, None),
              help='The number of submissions to claim. Overrides `percentage` if both given. Default is ALL.')
@click.option('-p', '--percentage', type=click.IntRange(1, 100), default=100,
              help='The percentage of submissions to claim, as an `int` (e.g. 60% is 60). Default is 100%.')
@click.option('-r', '--random', is_flag=True, default=False, flag_value=True,
              help='Whether to claim random submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@with_grader
def claim(*args, **kwargs):
    """Claims submissions to a grader."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    grader = kwargs.get('grader', DUMMY_GRADER)
    from_grader = kwargs.get('from_grader', None)
    num = kwargs.get('num', None)
    percentage = kwargs.get('percentage', 100)
    random = kwargs.get('random', False)

    # get submissions
    if from_grader is None:
        # get unclaimed submissions
        submissions = [s for s in assignment.list_submissions() if s.grader is None]
    else:
        # validate other grader first
        course = kwargs['COURSE']
        from_grader = make_email(from_grader)
        logger.info('Validating grader "{}"', from_grader)
        validated = validate_grader(course, from_grader)
        if not validated:
            return
        # get submissions from specified grader
        submissions = assignment.list_submissions(grader=from_grader)

    num_submissions = len(submissions)

    if num is not None:
        # if num is given, use it
        num_claim = num
        if num_claim > num_submissions:
            num_claim = num_submissions
            msg = ('Claiming all {} unclaimed submissions', num_submissions)
        else:
            random_str = 'random ' if random else ''
            msg = ('Claiming %s{} of {} unclaimed submissions' % random_str, num_claim, num_submissions)
    else:
        # if num is not given, fall back on percentage
        num_claim = int(len(submissions) * percentage / 100)
        if percentage == 100:
            msg = ('Claiming all {} unclaimed submissions', num_submissions)
        else:
            random_str = 'random ' if random else ''
            msg = ('Claiming %s{}%% of {} unclaimed submissions' % random_str, percentage, num_submissions)

    logger.info(*msg)

    # randomness
    if random:
        shuffle(submissions)

    claiming = submissions[:num_claim]
    claimed_ids = list()
    for s in claiming:
        codepost.submission.update(s.id, grader=grader)
        claimed_ids.append(s.id)

    logger.debug('Claimed {} submissions to "{}"', num_claim, grader)

    # dump to file
    dump_to_file(CLAIMED_FILE, grader, assignment_name, claimed_ids)


@cli.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-g', '--grader', type=str, default=DUMMY_GRADER,
              help='The grader to unclaim from. Accepts netid or email. Default is DUMMY_GRADER.')
@click.option('-n', '--num', type=click.IntRange(1, None),
              help='The number of submissions to unclaim. Overrides `percentage` if both given. Default is ALL.')
@click.option('-p', '--percentage', type=click.IntRange(1, 100), default=100,
              help='The percentage of submissions to unclaim, as an `int` (e.g. 60% is 60). Default is 100%.')
@click.option('-r', '--random', is_flag=True, default=False, flag_value=True,
              help='Whether to unclaim random submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@with_grader
def unclaim(*args, **kwargs):
    """Unclaims submissions from a grader."""

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    assignment = kwargs['ASSIGNMENT']
    assignment_name = kwargs['assignment_name']

    grader = kwargs.get('grader', DUMMY_GRADER)
    num = kwargs.get('num', None)
    percentage = kwargs.get('percentage', 100)
    random = kwargs.get('random', False)

    # get submissions claimed by grader
    submissions = assignment.list_submissions(grader=grader)
    num_submissions = len(submissions)

    if num is not None:
        # if num is given, use it
        num_unclaim = num
        if num_unclaim > num_submissions:
            num_unclaim = num_submissions
            msg = ('Unclaiming all {} submissions claimed by the grader', num_submissions)
        else:
            random_str = 'random ' if random else ''
            msg = ('Unclaiming %s{} of {} submissions claimed by the grader' % random_str, num_unclaim, num_submissions)
    else:
        # if num is not given, fall back on percentage
        num_unclaim = int(len(submissions) * percentage / 100)
        if percentage == 100:
            msg = ('Unclaiming all {} submissions claimed by the grader', num_submissions)
        else:
            random_str = 'random ' if random else ''
            msg = (
                'Unclaiming %s{}%% of {} submissions claimed by the grader' % random_str,
                percentage, num_submissions
            )

    logger.info(*msg)

    # randomness
    if random:
        shuffle(submissions)

    unclaiming = submissions[:num_unclaim]
    unclaimed_ids = list()
    for s in unclaiming:
        codepost.submission.update(s.id, grader='')
        unclaimed_ids.append(s.id)

    logger.debug('Unclaimed {} submissions from "{}"', num_unclaim, grader)

    # dump to file
    dump_to_file(UNCLAIMED_FILE, grader, assignment_name, unclaimed_ids)


# ===========================================================================

@cli.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def stats(*args, **kwargs):
    """
    Lists current stats of the grading queue.

    Expected time: < 10 seconds.
    """

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    assignment = kwargs['ASSIGNMENT']

    # get submissions
    logger.info('Getting stats')
    submissions = assignment.list_submissions()
    total = len(submissions)
    num_finalized = 0
    num_unfinalized = 0
    num_unclaimed = 0
    num_drafts = 0
    num_dummy_grader = 0
    for s in submissions:
        if s.isFinalized:
            num_finalized += 1
        else:
            num_unfinalized += 1
            if s.grader is None:
                num_unclaimed += 1
            elif s.grader == DUMMY_GRADER:
                num_dummy_grader += 1
            else:
                num_drafts += 1

    num_unfinalized -= num_dummy_grader

    # display stats
    logger.info('{} total submissions', total)
    logger.info('{} finalized [{:.2%}]', num_finalized, num_finalized / total)
    logger.info('{} unfinalized [{:.2%}]', num_unfinalized, num_unfinalized / total)
    logger.info('  {} drafts', num_drafts)
    logger.info('  {} unclaimed', num_unclaimed)
    if num_dummy_grader > 0:
        logger.info('{} claimed by dummy grader [{:.2%}]', num_dummy_grader, num_dummy_grader / total)


# ===========================================================================

@cli.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-s', '--save', 'saving', is_flag=True, default=False, flag_value=True,
              help='Whether to save the submissions to a file. Default is False.')
@click.option('-o', '--open', 'opening', is_flag=True, default=False, flag_value=True,
              help='Whether to open the finalized submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def finalized(*args, **kwargs):
    """
    Finds finalized submissions.

    Expected time: < 10 seconds.
    """

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    assignment = kwargs['ASSIGNMENT']

    saving = kwargs.get('saving', False)
    opening = kwargs.get('opening', False)

    submissions = list()
    num_submissions = 0

    # read from file?

    if len(submissions) == 0:
        logger.info('Getting finalized submissions')
        submissions = [s for s in assignment.list_submissions() if s.isFinalized]
        num_submissions = len(submissions)

        if num_submissions == 0:
            logger.info('No finalized submissions')
        else:
            logger.info('Found {} finalized submissions', num_submissions)

            if saving:
                logger.info('Saving submissions to "{}"', OPENED_FILE)
                data = list()
                for s in submissions:
                    row = {
                        'submission_id': s.id,
                        'old_grader': s.grader,
                    }
                    data.append(row)
                comma.dump(data, OPENED_FILE)

    if opening and num_submissions > 0:
        logger.info('Opening {} finalized submissions', num_submissions)
        for s in submissions:
            codepost.submission.update(s.id, grader='', isFinalized=False)


# ===========================================================================

@cli.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-r', '--report', is_flag=True, default=False, flag_value=True,
              help='Whether to generate a report of the auditing. Default is False.')
@click.option('-ff', '--from-file', is_flag=True, default=False, flag_value=True,
              help='Whether to read the submissions from a file. Default is False.')
@click.option('-f', '--only-finalized', is_flag=True, default=False, flag_value=True,
              help='Whether to only search finalized submissions. Default is False.')
@click.option('-n', '--num-times', type=click.IntRange(1, None), default=2,
              help='How many times each submission should be audited. Must be positive. Default is 2.')
@click.option('-l', '--list-submissions', 'listing', is_flag=True, default=False, flag_value=True,
              help='Whether to list the submissions. Default is False.')
@click.option('-s', '--save', 'saving', is_flag=True, default=False, flag_value=True,
              help='Whether to save the submissions to a file. Default is False.')
@click.option('-o', '--open', 'opening', is_flag=True, default=False, flag_value=True,
              help='Whether to open the submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
@driver
def audit(*args, **kwargs):
    """
    Deals with auditing submissions.

    \b
    Expected time:
        Report: <= 5 minutes.
        From codePost: <= 5 minutes.
        From file: < 5 seconds.
        Opening submissions: <= 2 minutes.
    """

    # not using args, but need in signature for positional arguments
    _ = args

    # get parameters
    assignment = kwargs['ASSIGNMENT']

    report = kwargs.get('report', False)
    from_file = kwargs.get('from_file', False)
    only_finalized = kwargs.get('only_finalized', False)
    num_times = kwargs.get('num_times', 2)
    listing = kwargs.get('listing', False)
    saving = kwargs.get('saving', False)
    opening = kwargs.get('opening', False)

    def get_audit_comment() -> int:
        """Gets the id of the quality assurance rubric comment."""

        logger.info('Finding "{}" rubric comment', AUDIT_COMMENT)
        audit_comment = None
        for category in assignment.rubricCategories:
            if category.name != 'GRADING': continue
            for rubric_comment in category.rubricComments:
                if rubric_comment.name == AUDIT_COMMENT:
                    audit_comment = rubric_comment
                    break
            break
        if audit_comment is None:
            logger.error('Could not find "{}" rubric comment', AUDIT_COMMENT)
            return -1
        return audit_comment.id

    if report:

        audit_comment_id = get_audit_comment()
        if audit_comment_id == -1:
            return

        course = kwargs['COURSE']

        graders = {g: 0 for g in codepost.roster.retrieve(course.id).graders if not g.startswith('jdlou+')}

        logger.info('Counting audited submissions')
        submissions_audited = set()
        for s in assignment.list_submissions():
            if not s.isFinalized: continue
            s_id = s.id
            for f in s.files:
                for c in f.comments:
                    comment = c.rubricComment
                    if comment is None: continue
                    if comment == audit_comment_id:
                        graders[s.grader] += 1
                        submissions_audited.add(s_id)

        audited = list()
        not_audited = list()
        for grader, count in graders.items():
            if count == 0:
                not_audited.append(grader)
            else:
                audited.append((count, grader))

        audited.sort(reverse=True)
        not_audited.sort()

        logger.info('Creating audit report in "{}"', AUDIT_REPORT_FILE)
        with open(AUDIT_REPORT_FILE, 'w') as f:
            f.write(f'Last updated: {east_coast_time()}\n')
            f.write('Note: audit counts not necessarily disjoint\n')
            f.write(f'\n{len(submissions_audited)} submissions audited\n')
            f.write(f'\n{len(audited)} graders audited:\n')
            for count, grader in audited:
                f.write(f'{count}\t{grader}\n')
            f.write(f'\n{len(not_audited)} graders didn\'t audit:\n')
            for grader in not_audited:
                f.write(grader + '\n')

        return

    submissions = list()
    num_submissions = 0

    # reading from file
    if from_file:
        logger.info('Reading submissions from file')
        if not os.path.exists(AUDIT_COUNTS_FILE):
            logger.warning('File "{}" not found', AUDIT_COUNTS_FILE)
        else:
            data = comma.load(AUDIT_COUNTS_FILE, force_header=True)
            keys = data.header
            audited_key = keys[1]
            for row in data:
                vals = (int(row['submission_id']), int(row[audited_key]), row['graders'])
                submissions.append(vals)
            num_submissions = len(submissions)

    # finding submissions from codepost
    if num_submissions == 0:

        audit_comment_id = get_audit_comment()
        if audit_comment_id == -1:
            return

        # find submissions with less than `num_times` audit comments
        logger.info('Finding {} submissions audited less than {} times',
                    'finalized' if only_finalized else 'all', num_times)

        all_submissions = assignment.list_submissions()
        for s in all_submissions:
            if only_finalized and not s.isFinalized: continue
            audit_count = 0
            graders = list()
            for f in s.files:
                for c in f.comments:
                    if c.rubricComment is None: continue
                    if c.rubricComment == audit_comment_id:
                        audit_count += 1
                        graders.append(c.author)
            if audit_count < num_times:
                submissions.append((s.id, audit_count, ';'.join(graders)))

        num_submissions = len(submissions)

    logger.debug('Found {} submissions needing to be audited', num_submissions)

    # listing submissions
    if listing and num_submissions > 0:
        logger.debug('Submissions found:')
        for (s_id, audit_count, _) in submissions:
            logger.debug('  {:6} {}', s_id, audit_count)

    # saving to file
    if saving and num_submissions > 0:
        logger.info('Saving audited submissions to "{}"', AUDIT_COUNTS_FILE)
        data = list()
        audited_key = f'times_audited_out_of_{num_times}'
        for (s_id, audit_count, graders) in submissions:
            row = {
                'submission_id': s_id,
                audited_key: audit_count,
                'graders': graders,
            }
            data.append(row)
        data.sort(key=lambda r: r[audited_key])
        comma.dump(data, AUDIT_COUNTS_FILE)

    # opening submissions
    if opening and num_submissions > 0:
        logger.info('Opening {} submissions', num_submissions)
        for (s_id, _, _) in submissions:
            codepost.submission.update(id=s_id, grader='', isFinalized=False)


# ===========================================================================

if __name__ == '__main__':
    cli()
