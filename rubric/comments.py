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
import codepost.errors
from PIL import Image, ImageFont, ImageDraw
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

FONT_SIZE = 16
FONT = None
for fontname in ('FiraSans-Regular', 'SF-Pro-Text-Regular', 'Arial'):
    try:
        FONT = ImageFont.truetype(fontname, size=FONT_SIZE)
        break
    except OSError:
        # could not find font; try next
        pass
else:
    logger.warning('Could not find normal fonts')

MONO_FONT = None
for fontname in ('FiraCode-VariableFont_wght', 'SF-Mono-Regular', 'Courier'):
    try:
        MONO_FONT = ImageFont.truetype(fontname, size=FONT_SIZE)
        break
    except OSError:
        # could not find font; try next
        pass
else:
    logger.warning('Could not find monospace fonts')

# constants
CTX_SETTINGS = {
    'context_settings': {'ignore_unknown_options': True}
}
LOGIN_URL = 'https://codepost.io/login'
JWT_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjo2OTE2LCJ1c2VybmFtZSI6ImpkbG91QHByaW5jZXRvbi5lZHUiLCJleHAiOjE2MTcxMzE2ODIsImVtYWlsIjoiamRsb3VAcHJpbmNldG9uLmVkdSIsIm9yaWdfaWF0IjoxNjE2NTI2ODgyfQ.-kb2wSbYD-rHvrvGO7vt0igtX-7ORYlnLXCYp05u0ek'
BLACK = (0, 0, 0)


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
@click.option('-t', '--timeout', type=click.IntRange(30, None), default=60,
              help='Timeout limit in seconds. Must be at least 30. Default is 60 sec.')
@click.option('-nt', '--no-timeout', is_flag=True, default=False, flag_value=True,
              help='Whether to run without timeout. Default is False.')
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
            try:
                c_id = int(c_id)
            except ValueError:
                c_id = None

        seen_num = False
        s_id = ''
        for c in reversed(submission_link):
            if not c.isdigit():
                if seen_num: break
                continue
            seen_num = True
            s_id = c + s_id
        try:
            s_id = int(s_id)
        except ValueError:
            return None, c_id

        return s_id, c_id

    # not using args, but needs it in signature for positional arguments
    _ = args

    # get parameters
    link = kwargs['link']

    timeout = kwargs.get('timeout', 60)
    no_timeout = kwargs.get('no_timeout', False)

    if no_timeout:
        timeout = 0
    else:
        timeout *= 1000

    logger.info('Extracting submission id and comment id from link')

    # get submission id and comment id
    submission_id, comment_id = parse_link(link)

    if submission_id is None:
        logger.error('No submission id found')
        return
    if comment_id is None:
        logger.error('No comment id found')
        return
    logger.debug('Submission {}, Comment {}', submission_id, comment_id)

    try:
        submission = codepost.submission.retrieve(submission_id)
    except codepost.errors.NotFoundAPIError:
        logger.error('Invalid submission id {}', submission_id)
        return
    except codepost.errors.AuthorizationAPIError:
        logger.error('No access to submission id {}', submission_id)
        return
    try:
        comment = codepost.comment.retrieve(comment_id)
    except codepost.errors.NotFoundAPIError:
        logger.error('Invalid comment id {}', comment_id)
        return
    except codepost.errors.AuthorizationAPIError:
        logger.error('No access to comment id {}', comment_id)
        return

    rubric_id = comment.rubricComment

    file = codepost.file.retrieve(comment.file)
    file_index = sorted(f.name.lower() for f in submission.files).index(file.name.lower())

    assignment = codepost.assignment.retrieve(submission.assignment)
    course = codepost.course.retrieve(assignment.course)

    # create output folders
    if not os.path.exists(OUTPUT_FOLDER):
        os.mkdir(OUTPUT_FOLDER)
    course_folder = os.path.join(OUTPUT_FOLDER, course_str(course))
    if not os.path.exists(course_folder):
        os.mkdir(course_folder)
    assignment_folder = os.path.join(course_folder, assignment.name)
    if not os.path.exists(assignment_folder):
        os.mkdir(assignment_folder)

    strs = [assignment.name, str(submission_id), str(comment_id), file.name]

    if rubric_id is None:
        screenshot_file = FILES['screenshot'].format(submission_id, comment_id)
    else:
        comment_name = codepost.rubric_comment.retrieve(rubric_id).name
        screenshot_file = FILES['rubric comment'].format(submission_id, comment_id, comment_name)

        rubric_comment = codepost.rubric_comment.retrieve(rubric_id)
        category = codepost.rubric_category.retrieve(rubric_comment.category)
        strs += [category.name, comment_name]

    filepath = os.path.join(assignment_folder, screenshot_file)

    width = 1450
    height = 900

    async def create_screenshot():
        """Creates a screenshot of the given comment.
        https://gist.github.com/jlumbroso/c0ec0c4f1a0a502e3835c183cbe89c65
        """

        logger.info('Creating screenshot of comment')

        submission_link = f'https://codepost.io/code/{submission_id}'

        logger.debug('Launching browser')
        browser = await launch()
        page = await browser.newPage()
        await page.setViewport({'width': width, 'height': height})

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
            await page.goto(submission_link, timeout=timeout, waitUntil=waiting)
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

        # align comment
        logger.debug('Aligning comment')
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

        # set column widths
        logger.debug('Setting column widths')
        # code width - default 728
        code_width = 600
        # comment width - default 360
        comment_width = 500
        await page.evaluate(
            '''(codeWidth, commentWidth) => {
                document.getElementById("code-container").style.width = codeWidth + "px";
                document.getElementById("code-panel--comments").style.width = commentWidth + "px";
            }''',
            code_width, comment_width
        )

        # set slider position
        # slider_max = int(await page.evaluate(
        #     '''document.getElementsByClassName("rc-slider-handle-2")[0].getAttribute("aria-valuemax");''',
        #     force_expr=True
        # ))
        # slider_per = code_width / slider_max * 100
        # await page.evaluate(
        #     '''(sliderPer) => {
        #         document.getElementsByClassName("rc-slider-track-1")[0].style.width = sliderPer + "%";
        #         document.getElementsByClassName("rc-slider-handle-2")[0].style.left = sliderPer + "%";
        #     }''',
        #     slider_per
        # )

        logger.debug('Taking screenshot')
        await page.screenshot(path=filepath)

        logger.debug('Closing browser')
        await browser.close()

    asyncio.get_event_loop().run_until_complete(create_screenshot())

    logger.info('Adding metadata to image')
    # assignment name
    # submission id
    # comment id
    # file name
    # category name (if rubric comment)
    # comment name (if rubric comment)

    img = Image.open(filepath)
    img_draw = ImageDraw.Draw(img)

    RIGHT_PADDING = 25
    BOTTOM_PADDING = 15
    COL_SPACE = 10
    LINE_SPACE = 5

    fonts = [FONT, MONO_FONT, MONO_FONT, MONO_FONT, MONO_FONT, MONO_FONT]

    max_width = 0
    max_height = 0
    for s, font in reversed(list(zip(strs, fonts))):
        w, h = font.getsize(s)
        if w > max_width:
            max_width = w
        if h > max_height:
            max_height = h
    x2 = width - RIGHT_PADDING - max_width

    max_width = 0
    labels = ['Assignment:', 'Submission:', 'Comment ID:', 'File:', 'Category:', 'Comment:']
    for _, label in zip(strs, labels):
        w, h = FONT.getsize(label)
        if w > max_width:
            max_width = w
        if h > max_height:
            max_height = h
    x1 = x2 - COL_SPACE - max_width

    for i, (s, label, font) in enumerate(reversed(list(zip(strs, labels, fonts)))):
        y = height - BOTTOM_PADDING - (max_height + LINE_SPACE) * (i + 1)
        img_draw.text((x1, y), label, fill=BLACK, font=FONT)
        img_draw.text((x2, y), s, fill=BLACK, font=font)

    img.save(filepath)


# ===========================================================================

if __name__ == '__main__':
    cli()
