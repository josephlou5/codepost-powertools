"""
comments.py
Comment related operations.

Commands:
auto - Automatically add rubric comments to submissions
find - Find submissions that have a number of comments
reports - Creates report of rubric comment usage
screenshot - Screenshots a linked comment

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs

gspread API
https://gspread.readthedocs.io/en/latest/index.html
"""

# ===========================================================================

import os
import time
import click
import asyncio
import codepost
import codepost.models.assignments  # to get rid of an error message
from loguru import logger
from functools import update_wrapper
# ref: https://github.com/miyakogi/pyppeteer/issues/219#issuecomment-563077061
import pyppdf.patch_pyppeteer  # needed to avoid chromium errors
from pyppeteer import launch
import pyppeteer.errors

from shared import *

# ===========================================================================

# outputs
OUTPUT_FOLDER = 'comments'
FILES = {
    'screenshot': '{}_{}.png',  # submission id, comment id
    'rubric comment': '{}_{}_{}.png',  # submission id, comment id, comment name
}

# globals
TIMEOUT_SEC = 60

# constants
CTX_SETTINGS = {
    'context_settings': {'ignore_unknown_options': True}
}
LOGIN_URL = 'https://codepost.io/login'
JWT_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjo2OTE2LCJ1c2VybmFtZSI6ImpkbG91QHByaW5jZXRvbi5lZHUiLCJleHAiOjE2MTcxMzE2ODIsImVtYWlsIjoiamRsb3VAcHJpbmNldG9uLmVkdSIsIm9yaWdfaWF0IjoxNjE2NTI2ODgyfQ.-kb2wSbYD-rHvrvGO7vt0igtX-7ORYlnLXCYp05u0ek'


# ===========================================================================


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

        kwargs['COURSE'] = course

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


def with_codepost(f):
    """Decorator for main driver with only codePost."""

    @click.pass_context
    @wrap
    def main(ctx, *args, **kwargs):
        # not using args, but needs it in signature for positional arguments
        _ = args

        logger.info('Logging into codePost')
        success = log_in_codepost()
        if not success:
            return

        # do function
        ctx.invoke(f, ctx, **kwargs)

    return update_wrapper(main, f)


# ===========================================================================

@cli.command(
    'auto',
    **CTX_SETTINGS,
    help='Automatically add rubric comments to submissions.'
)
@driver
def auto_cmd(*args, **kwargs):
    """Automatically add rubric comments to submissions."""

    # not using args, but needs it in signature for positional arguments
    _ = args


# ===========================================================================

@cli.command(
    'find',
    **CTX_SETTINGS,
    help='Find submissions that have a number of comments.'
)
@driver
def find_cmd(*args, **kwargs):
    """Find submissions that have a number of comments."""

    # not using args, but needs it in signature for positional arguments
    _ = args


# ===========================================================================

@cli.command(
    'reports',
    **CTX_SETTINGS,
    help='Creates report of rubric comment usage.'
)
@driver
def reports_cmd(*args, **kwargs):
    """Creates report of rubric comment usage."""

    # not using args, but needs it in signature for positional arguments
    _ = args


# ===========================================================================

@cli.command(
    'screenshot',
    **CTX_SETTINGS,
    help='Screenshots a linked comment.'
)
@click.argument('link', type=str, required=True)
@with_codepost
def screenshot_cmd(*args, **kwargs):
    """Screenshots a linked comment."""

    def parse_link(codepost_link) -> tuple:
        """Extracts the submission id and comment id from a link.

        Args:
            codepost_link (str): The link.

        Returns:
            tuple[int, int]: The submission id and comment id.
                If no comment id, returns tuple[int, None].
        """

        if '/?comment=' not in codepost_link:
            # no comment id
            submission_link = codepost_link
            c_id = None
        else:
            submission_link, c_id = codepost_link.split('/?comment=')
            c_id = int(c_id)

        seen_num = False
        s_id = ''
        for c in reversed(submission_link):
            if not c.isdigit():
                if seen_num: break
                continue
            seen_num = True
            s_id = c + s_id
        s_id = int(s_id)

        return s_id, c_id

    # not using args, but needs it in signature for positional arguments
    _ = args

    # get parameters
    link = kwargs['link']

    logger.info('Extracting submission id and comment id from link')

    # get submission id and comment id
    submission_id, comment_id = parse_link(link)

    if comment_id is None:
        logger.error('No comment id found')
        return

    submission = codepost.submission.retrieve(submission_id)
    comment = codepost.comment.retrieve(comment_id)

    rubric_id = comment.rubricComment
    if rubric_id is not None:
        comment_name = codepost.rubric_comment.retrieve(rubric_id).name

    file = codepost.file.retrieve(comment.file)
    file_index = sorted(f.name.lower() for f in submission.files).index(file.name.lower())

    assignment = codepost.assignment.retrieve(submission.assignment)
    course = codepost.course.retrieve(assignment.course)

    async def create_screenshot():
        """Creates a screenshot of the given comment.
        https://gist.github.com/jlumbroso/c0ec0c4f1a0a502e3835c183cbe89c65
        """

        logger.info('Creating screenshot of comment')

        submission_link = f'https://codepost.io/code/{submission_id}'

        logger.debug('Launching browser')
        browser = await launch()
        page = await browser.newPage()
        await page.setViewport({'width': 1450, 'height': 900})

        logger.debug('Storing JWT token')
        # store JWT
        await page.goto(LOGIN_URL)
        await page.evaluate('(token) => { localStorage.setItem("token", token); }', JWT_KEY)

        logger.debug('Opening submission page')
        # load page and wait to make sure everything is rendered
        waiting = [
            'load',  # load event
            'domcontentloaded',  # DOMContentLoaded event
            'networkidle0',  # no more than 0 network connections for at least 500 ms
            'networkidle2',  # no more than 2 network connections for at least 500 ms
        ]
        start = time.time()
        try:
            await page.goto(submission_link, timeout=TIMEOUT_SEC * 1000, waitUntil=waiting)
        except pyppeteer.errors.TimeoutError as e:
            logger.error('Error: {}', e)
            return
        end = time.time()
        logger.debug('Page loaded ({:.2f})', end - start)

        # hide grade
        # logger.debug('Hiding grade')
        # await page.evaluate(
        #     '''() => {
        #         const header = document.getElementsByClassName("layout--standard-console__header")[0];
        #         const grade_div = header.firstElementChild.children[1];
        #         grade_div.style.display = "none";
        #     }'''
        # )

        # collapse left sections
        # logger.debug('Collapsing sections')
        # section_arrows = await page.querySelectorAll('.ant-collapse-arrow')
        # for i, arrow in enumerate(section_arrows):
        #     # skip files section
        #     if i == 2: continue
        #     # collapse section by clicking on its arrow
        #     await arrow.click()

        # select correct file
        if file_index != 0:
            logger.debug('Selecting correct file')
            # using click() scrolls the files page just in case it needs to be scrolled
            # but since the left section is being hidden, that doesn't matter
            # page_files = await page.querySelectorAll('#file-menu li')
            # await page_files[file_index].click()
            await page.keyboard.down('Meta')
            await page.keyboard.press(str(file_index + 1))
            await page.keyboard.up('Meta')

        # justify comment
        logger.debug('Justifying comment')
        highlight = await page.querySelector(f'#line-{comment.startLine}-{comment.id}')
        await page.keyboard.down('Meta')
        await highlight.click()
        await page.keyboard.up('Meta')

        # hide other comments
        if len(file.comments) > 1:
            logger.debug('Hiding other comments')
            comments = [f'comment-{c.id}' for c in file.comments if c.id != comment_id]
            await page.evaluate(
                '''(comments) => {
                    comments.forEach((comment) => {
                        document.getElementById(comment).style.display = "none";
                    });
                }''',
                comments
            )

        # hide header bar, slider bar, section panel, command bar, and intercom
        logger.debug('Hiding unwanted elements')
        await page.evaluate(
            '''() => {
                document.getElementsByClassName("layout--standard-console__header").forEach((x) => {
                    x.style.display = "none";
                });
                document.getElementsByClassName("layout-resizer").forEach((x) => {
                    x.style.visibility = "hidden";
                });
                document.getElementById("Code-Header").style.display = "none";
                document.getElementById("commandbar-wrapper").style.display = "none";
                document.getElementById("intercom-frame").style.display = "none";
                document.getElementsByClassName("intercom-lightweight-app").forEach((x) => {
                    x.style.display = "none";
                });
            }'''
        )

        # code width - default 728
        logger.debug('Setting code width')
        width = 600
        # slider_max = int(await page.evaluate(
        #     '''document.getElementsByClassName("rc-slider-handle-2")[0].getAttribute("aria-valuemax");''',
        #     force_expr=True
        # ))
        # slider_per = width / slider_max * 100
        # await page.evaluate(
        #     '''(width, slider_per) => {
        #         document.getElementById("code-container").style.width = width + "px";
        #         // document.getElementsByClassName("rc-slider-track-1")[0].style.width = slider_per + "%";
        #         // document.getElementsByClassName("rc-slider-handle-2")[0].style.left = slider_per + "%";
        #     }''',
        #     width, slider_per
        # )
        await page.evaluate(
            '''(width) => {
                document.getElementById("code-container").style.width = width + "px";
            }''',
            width
        )

        # comment width - default 360
        logger.debug('Setting comment width')
        width = 500
        await page.evaluate(
            '''(width) => {
                document.getElementById("code-panel--comments").style.width = width + "px";
            }''',
            width
        )

        logger.debug('Taking screenshot')

        if not os.path.exists(OUTPUT_FOLDER):
            os.mkdir(OUTPUT_FOLDER)
        course_folder = os.path.join(OUTPUT_FOLDER, course_str(course))
        if not os.path.exists(course_folder):
            os.mkdir(course_folder)
        assignment_folder = os.path.join(course_folder, assignment.name)
        if not os.path.exists(assignment_folder):
            os.mkdir(assignment_folder)

        if rubric_id is None:
            screenshot_file = FILES['screenshot'].format(submission_id, comment_id)
        else:
            screenshot_file = FILES['rubric comment'].format(submission_id, comment_id, comment_name)

        filepath = os.path.join(assignment_folder, screenshot_file)
        await page.screenshot(path=filepath)

        logger.debug('Closing browser')
        await browser.close()

    asyncio.get_event_loop().run_until_complete(create_screenshot())


# ===========================================================================

if __name__ == '__main__':
    cli()
