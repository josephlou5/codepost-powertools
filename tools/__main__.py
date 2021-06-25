"""
__main__.py
The command-line interface for the codePost powertools.
"""

# ===========================================================================

import time
from functools import update_wrapper

import click
from loguru import logger

from shared_codepost import DUMMY_GRADER

# rubric group
import rubric_to_sheet
import sheet_to_rubric
# comments group
import auto_comments
import reports
import num_comments
import tier_report
# grading group
import ids
import claim
import unclaim
import finalize
import open_submissions
import find
import failed
import stats

# ===========================================================================

CTX_SETTINGS = {
    'context_settings': {'ignore_unknown_options': True}
}


# ===========================================================================

def format_time(seconds: float) -> str:
    """Formats seconds into minutes or higher units of time.

    Args:
        seconds (float): The number of seconds.

    Returns:
        str: The formatted time.
    """

    remaining, secs = map(int, divmod(seconds, 60))
    hrs, mins = map(int, divmod(remaining, 60))

    if remaining == 0:
        return f'{seconds:.2f} sec'

    time_str = ''
    if hrs > 0:
        time_str += f'{hrs} hr '
    if mins > 0:
        time_str += f'{mins} min '
    if secs > 0:
        time_str += f'{secs} sec '
    time_str += f'({seconds:.2f})'

    return time_str


# ===========================================================================

# decorators

def wrap(f):
    """Decorator for start and end."""

    @click.pass_context
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        start = time.time()
        logger.info('Start')

        # do function
        ctx.invoke(f, **kwargs)

        logger.info('Done')
        end = time.time()
        logger.info('Total time: {}', format_time(end - start))

    return update_wrapper(main, f)


# ===========================================================================

# rubric group

@click.command(
    name='export',
    **CTX_SETTINGS,
    help='Exports a codePost rubric to a Google Sheet.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('start_assignment', type=str, required=False)
@click.argument('end_assignment', type=str, required=False)
@click.option('-w', '--wipe', is_flag=True, default=False, flag_value=True,
              help='Whether to wipe the existing worksheets. Default is False.')
@click.option('-r', '--replace', is_flag=True, default=False, flag_value=True,
              help='Whether to replace the existing worksheets. Default is False.')
@click.option('-ci', '--count-instances', is_flag=True, default=False, flag_value=True,
              help='Whether to count the instances of the rubric comments. Default is False.')
@wrap
def export_cmd(**kwargs):
    rubric_to_sheet.main(**kwargs, log=True)


@click.command(
    name='import',
    **CTX_SETTINGS,
    help='Imports a codePost rubric from a Google Sheet.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('sheet_name', type=str, required=True)
@click.argument('start_sheet', type=click.IntRange(0), required=False)
@click.argument('end_sheet', type=click.IntRange(0), required=False)
@click.option('-f', '--force-update', is_flag=True, default=False, flag_value=True,
              help='Whether to force updating the rubric. Default is False.')
@click.option('-d', '--delete-missing', is_flag=True, default=False, flag_value=True,
              help='Whether to delete the rubric comments not in the sheet. Default is False.')
@click.option('-w', '--wipe', is_flag=True, default=False, flag_value=True,
              help='Whether to wipe the existing rubric. Default is False.')
@wrap
def import_cmd(**kwargs):
    # TODO: test
    sheet_to_rubric.main(**kwargs, log=True)


# ===========================================================================

# comments group

@click.command(
    name='auto_comments',
    **CTX_SETTINGS,
    help='Adds automatic rubric comments to submissions.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('author', type=str, required=False)
@click.option('-s', '--stringbuilder', is_flag=True, default=False, flag_value=True,
              help='Whether to apply the stringbuilder comment. Default is False.')
@click.option('-f', '--from-file', is_flag=True, default=False, flag_value=True,
              help='Whether to read the comments from a file. Default is False.')
@click.option('-a', '--apply', is_flag=True, default=False, flag_value=True,
              help='Whether to apply the comments. Default is False.')
@wrap
def auto_comments_cmd(**kwargs):
    # TODO: test
    auto_comments.main(**kwargs, log=True)


@click.command(
    name='reports',
    **CTX_SETTINGS,
    help='Creates rubric comment usage reports.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-f', '--from-files', is_flag=True, default=False, flag_value=True,
              help='Whether to read the reports from files. Default is False.')
@click.option('-a', '--apply', is_flag=True, default=False, flag_value=True,
              help='Whether to apply the reports to the submissions. Default is False.')
@wrap
def reports_cmd(**kwargs):
    # TODO: test
    reports.main(**kwargs, log=True)


@click.command(
    name='num_comments',
    **CTX_SETTINGS,
    help='Counts the number of applied comments.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-rc', '--rubric-comments', is_flag=True, default=True, flag_value=False,
              help='Whether to count rubric comments. Default is True.')
@click.option('-cc', '--custom-comments', is_flag=True, default=True, flag_value=False,
              help='Whether to count custom comments. Default is True.')
@click.option('-sa', '--search-all', is_flag=True, default=False, flag_value=True,
              help='Search all submissions. Default is False.')
@click.option('-sf', '--search-finalized', is_flag=True, default=False, flag_value=True,
              help='Search the finalized submissions. Default is False.')
@click.option('-sd', '--search-drafts', is_flag=True, default=False, flag_value=True,
              help='Search the draft submissions. Default is False.')
@click.option('-su', '--search-unclaimed', is_flag=True, default=False, flag_value=True,
              help='Search the unclaimed submissions. Default is False.')
@wrap
def num_comments_cmd(**kwargs):
    # TODO: test
    num_comments.main(**kwargs, log=True)


@click.command(
    name='tier_report',
    **CTX_SETTINGS,
    help='Generates a report of tier comments usage.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@wrap
def tier_report_cmd(**kwargs):
    # TODO: test
    tier_report.main(**kwargs, log=True)


# ===========================================================================

# grading group

@click.command(
    name='ids',
    **CTX_SETTINGS,
    help='Creates a mapping between student emails and submission IDs.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@wrap
def ids_cmd(**kwargs):
    # TODO: test
    ids.main(**kwargs, log=True)


@click.command(
    name='claim',
    **CTX_SETTINGS,
    help='Claims submissions.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=False)
@click.option('-g', '--grader', type=str, default=DUMMY_GRADER,
              help='The grader to claim to. Default is `DUMMY_GRADER`.')
@click.option('-n', '--num', type=click.IntRange(1, None),
              help='The number of submissions to claim. Default is ALL.')
@click.option('-p', '--percentage', type=click.IntRange(1, 100), default=100,
              help='The percentage of submissions to claim. Default is 100%.')
@wrap
def claim_cmd(**kwargs):
    # TODO: test
    claim.main(**kwargs, log=True)


@click.command(
    name='unclaim',
    **CTX_SETTINGS,
    help='Unclaims submissions.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=False)
@click.option('-g', '--grader', type=str, default=DUMMY_GRADER,
              help='The grader to unclaim from. Default is `DUMMY_GRADER`.')
@click.option('-n', '--num', type=click.IntRange(1, None),
              help='The number of submissions to unclaim. Default is ALL.')
@click.option('-p', '--percentage', type=click.IntRange(1, 100), default=100,
              help='The percentage of submissions to unclaim. Default is 100%.')
@click.option('-u', '--unfinalize', is_flag=True, default=False, flag_value=True,
              help='Whether to unclaim and unfinalize finalized submissions. Default is False.')
@wrap
def unclaim_cmd(**kwargs):
    # TODO: test
    unclaim.main(**kwargs, log=True)


@click.command(
    name='finalize',
    **CTX_SETTINGS,
    help='Finalizes submissions.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=True)
@wrap
def finalize_cmd(**kwargs):
    # TODO: test
    finalize.main(**kwargs, log=True)


@click.command(
    name='open',
    **CTX_SETTINGS,
    help='Opens submissions (unfinalizes and unclaims).'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.argument('file', type=str, required=True)
@click.option('-d', '--drafts', is_flag=True, default=False, flag_value=True,
              help='Whether to open draft submissions. Default is False.')
@wrap
def open_cmd(**kwargs):
    # TODO: test
    open_submissions.main(**kwargs, log=True)


@click.command(
    name='find',
    **CTX_SETTINGS,
    help='Finds submissions by given search flags.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-g', '--grader', type=str,
              help='The grader to filter.')
@click.option('-s', '--student', type=str,
              help='The student to filter. Ignores all other options.')
@click.option('-a', '--search-all', is_flag=True, default=False, flag_value=True,
              help='Search all submissions. Default is False.')
@click.option('-f', '--finalized', is_flag=True, default=False, flag_value=True,
              help='Search the finalized submissions. Default is True.')
@click.option('-d', '--drafts', is_flag=True, default=False, flag_value=True,
              help='Search the draft submissions. Default is False.')
@click.option('-u', '--unclaimed', is_flag=True, default=False, flag_value=True,
              help='Search the unclaimed submissions. Default is False.')
@wrap
def find_cmd(**kwargs):
    # TODO: test
    find.main(**kwargs, log=True)


@click.command(
    name='failed',
    **CTX_SETTINGS,
    help='Finds submissions that failed tests.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-c', '--cutoff', type=click.IntRange(1, None),
              help='The number of tests that denote "passed". Default is all passed.')
@wrap
def failed_cmd(**kwargs):
    # TODO: test
    failed.main(**kwargs, log=True)


@click.command(
    name='stats',
    **CTX_SETTINGS,
    help='Lists current stats of the grading queue.'
)
@click.argument('course_name', type=str, required=True)
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-w', '--window', type=click.IntRange(10, None),
              help=('The window update interval in seconds. Must be at least 10.'
                    'If not given, will not display window.'))
@wrap
def stats_cmd(**kwargs):
    # TODO: test
    stats.main(**kwargs, log=True)


# ===========================================================================

# miscellaneous

# ===========================================================================

# groups

# https://github.com/pallets/click/issues/513#issuecomment-504158316
class NaturalOrderGroup(click.Group):

    def __init__(self, *args, **kwargs):
        commands = kwargs.get('commands', None)
        if commands is not None:
            if type(commands) is list:
                kwargs['commands'] = {cmd.name: cmd for cmd in commands}
        super().__init__(*args, **kwargs)

    def list_commands(self, ctx):
        return list(self.commands.keys())


rubric = NaturalOrderGroup(commands=[
    export_cmd,
    import_cmd,
])
comments = NaturalOrderGroup(commands=[
    auto_comments_cmd,
    reports_cmd,
    num_comments_cmd,
    tier_report_cmd,
])
grading = NaturalOrderGroup(commands=[
    ids_cmd,
    claim_cmd,
    unclaim_cmd,
    finalize_cmd,
    open_cmd,
    find_cmd,
    failed_cmd,
    stats_cmd,
])
# miscellaneous = NaturalOrderGroup(commands=[])


# ===========================================================================

# putting everything together

class NaturalOrderCollection(click.CommandCollection):
    def list_commands(self, ctx):
        return sum([multiCommand.list_commands(ctx) for multiCommand in self.sources], [])


cli = NaturalOrderCollection(sources=[
    rubric,
    comments,
    grading,
])

# ===========================================================================

if __name__ == '__main__':
    cli()
