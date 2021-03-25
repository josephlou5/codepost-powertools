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
import comma
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
# maps rubric comment id -> (comment name, category name)
CATEGORIES = dict()

TIMEOUT_SEC = 60

FONT_SIZE = 14
ONE_LINE_FONT_SIZE = 10
TITLE_FONTS = ['Roboto-Bold', 'FiraSans-Bold', 'SF-Pro-Text-Bold', 'Arial Bold']
SANS_FONTS = ['Roboto-Regular', 'FiraSans-Regular', 'SF-Pro-Text-Regular', 'Arial']
MONO_FONTS = ['FiraCode-VariableFont_wght', 'SF-Mono-Regular', 'Courier']

# constants
CTX_SETTINGS = {
    'context_settings': {'ignore_unknown_options': True}
}
LOGIN_URL = 'https://codepost.io/login'
JWT_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjo2OTE2LCJ1c2VybmFtZSI6ImpkbG91QHByaW5jZXRvbi5lZHUiLCJleHAiOjE2MTcxMzE2ODIsImVtYWlsIjoiamRsb3VAcHJpbmNldG9uLmVkdSIsIm9yaWdfaWF0IjoxNjE2NTI2ODgyfQ.-kb2wSbYD-rHvrvGO7vt0igtX-7ORYlnLXCYp05u0ek'
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CODEPOST_GREEN = (87, 177, 130)
LIGHT_GRAY = (192, 192, 192)


# ===========================================================================

def validate_file(file) -> tuple:
    """Validates a file.

    Args:
        file (str): The file to validate.

    Returns:
        tuple[str, str]: The filepath and file extension.
    """

    if file is None:
        return None, None

    # check file existence
    filepath = file
    if not os.path.exists(filepath):
        filepath = os.path.join(OUTPUT_FOLDER, filepath)
        if not os.path.exists(filepath):
            logger.error('File "{}" not found', file)
            return None, None

    # check file extension
    _, ext = os.path.splitext(filepath)
    if ext not in ('.txt', '.csv'):
        logger.warning('Unsupported file type "{}"', ext)
        return None, None

    return filepath, ext


def read_links_from_file(filepath, ext) -> list[str]:
    """Reads links from a file.

    Args:
        filepath (str): The file.
        ext (str): The file extension.

    Returns:
        list[str]: The list of links.
    """

    logger.info('Reading links from file')

    links = list()

    if ext == '.txt':
        with open(filepath, 'r') as f:
            links = [line.strip() for line in f.read().split('\n')]
    elif ext == '.csv':
        data = comma.load(filepath, force_header=True)
        LINK_KEY = 'link'
        if LINK_KEY in data.header:
            links = list(data[LINK_KEY])
        else:
            # look for submission id and comment id and combine into links
            S_ID_KEY = 'submission_id'
            C_ID_KEY = 'comment_id'
            if S_ID_KEY not in data.header or C_ID_KEY not in data.header:
                logger.warning('File "{}" does not have proper columns', filepath)
            else:
                for s_id, c_id in zip(data[S_ID_KEY], data[C_ID_KEY]):
                    if s_id.strip().isdigit() and c_id.strip().isdigit():
                        link = f'https://codepost.io/code/{s_id.strip()}/?comment={c_id.strip()}'
                        links.append(link)

    if len(links) == 0:
        logger.warning('No links found in file')
    else:
        logger.debug('Found {} links', len(links))

    return links


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

def get_font(fontnames, size=10, default=ImageFont.load_default()) -> ImageFont:
    """Gets a font.

    Args:
        fontnames (list[str]): The font names to try, in order.
        size (int): The font size.
            Default is 10.
        default (Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]): The default font if none are found.
            Default is ImageFont.load_default().

    Returns:
        Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]: The font.
    """

    final_font = default
    for fontname in fontnames:
        try:
            final_font = ImageFont.truetype(fontname, size=size)
            break
        except OSError:
            logger.warning('Font "{}" not found', fontname)
            pass
    return final_font


def get_file_name(submission_id, comment_id, rubric_id) -> tuple:
    """Gets the screenshot file name of the given comment.

    Args:
        submission_id (int): The submission id.
        comment_id (int): The comment id.
        rubric_id (int): The rubric comment id, if the comment is a rubric comment.

    Returns:
        tuple[str, Optional[str], Optional[str]]: The screenshot file name,
            the category name, and the comment name.
            The last two are only passed if the comment is a rubric comment.
    """
    global CATEGORIES

    if rubric_id is None:
        return FILES['screenshot'].format(submission_id, comment_id), None, None

    comment_name, category_name = CATEGORIES.get(rubric_id, (None, None))
    if comment_name is None:
        rubric_comment = codepost.rubric_comment.retrieve(rubric_id)
        comment_name = rubric_comment.name
        category = codepost.rubric_category.retrieve(rubric_comment.category)
        category_name = category.name

        CATEGORIES[rubric_id] = (comment_name, category_name)

    screenshot_file = FILES['rubric comment'].format(submission_id, comment_id, comment_name)

    return screenshot_file, category_name, comment_name


class CodePostPage:
    """
    CodePostPage class: Represents a Pyppeteer page linked to a submission.

    Constructors:
        CodePostPage.create(browser, submission_id, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT)
            Initializes a CodePostPage.

    Constants:
        DEFAULT_WIDTH (int): The default width.
        DEFAULT_HEIGHT (int): The default height.

    Properties:
        width (int): The width.
        height (int): The height.
        size (tuple[int, int]): The width and height.

    Methods (all coroutines):
        set_width(width)
            Sets the width.

        set_height(height)
            Sets the height.

        set_size(width, height)
            Sets the width and height.

        open_submission(timeout=60000)
            Opens the submission.

        evaluate(*args, **kwargs)
            Proxy for `pyppeteer.page.Page.evaluate()`.

        hide_grade()
            Hides the grade element.

        collapse_sections(ignore=None)
            Collapses the sections on the left.

        align_comment(comment)
            Aligns a comment.

        hide_elements(ids=None, classes=None)
            Hides elements on the page.

        cover_elements(ids=None, classes=None)
            Covers elements on the page.

        reset_column_width(code=False, comment=False)
            Resets the column width of the code and comment panels.

        set_column_width(code=None, comment=None, slider=False)
            Sets the column width of the code and comment panels.

        screenshot(path, x=None, y=None, width=None, height=None)
            Takes and saves a screenshot.
    """

    # ==================================================

    # constants
    DEFAULT_WIDTH = 1450
    DEFAULT_HEIGHT = 900

    # ==================================================

    # constructors

    def __init__(self, browser, page, submission_id, width, height):
        """Initializes a Page. Not meant for public calls."""
        self._browser = browser
        self._page = page
        self._s_id = submission_id
        self._width = width
        self._height = height

        self._selected_file = 0

    @classmethod
    async def create(cls, browser, submission_id, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
        """Initializes a CodePostPage.

        Args:
            browser (pyppeteer.browser.Browser): The browser.
            submission_id (int): The submission id.
            width (int): The width of the page.
                Default is `DEFAULT_WIDTH`.
            height (int): The height of the page.
                Default is `DEFAULT_HEIGHT`.
        """
        page = cls(browser, await browser.newPage(), submission_id, width, height)
        await page._update_size()
        return page

    # ==================================================

    # private methods

    async def _update_size(self):
        await self._page.setViewport({'width': self._width, 'height': self._height})

    # ==================================================

    # properties

    @property
    def width(self):
        return self._width

    async def set_width(self, width):
        """Sets the width."""
        self._width = width
        await self._update_size()

    @property
    def height(self):
        return self._height

    async def set_height(self, height):
        """Sets the height."""
        self._height = height
        await self._update_size()

    @property
    def size(self):
        return self._width, self._height

    async def set_size(self, width, height):
        """Sets the width and height."""
        self._width, self._height = width, height
        await self._update_size()

    # ==================================================

    # public methods

    async def open_submission(self, timeout=60000) -> float:
        """Opens the submission.

        Args:
            timeout (int): The timeout limit for the page to load, in milliseconds.
                Default is 60000 ms.

        Returns:
            float: The amount of time it took to load, in seconds.
                If timed out, returns -1.
        """

        link = f'https://codepost.io/code/{self._s_id}'

        # load page and wait to make sure everything is rendered
        waiting = [
            'load',  # load event
            'domcontentloaded',  # DOMContentLoaded event
            'networkidle0',  # no more than 0 network connections for at least 500 ms
            'networkidle2',  # no more than 2 network connections for at least 500 ms
        ]

        start = time.time()
        try:
            await self._page.goto(link, timeout=timeout, waitUntil=waiting)
        except pyppeteer.errors.TimeoutError as e:
            logger.error('Error: {}', e)
            return -1
        end = time.time()

        return end - start

    async def evaluate(self, *args, **kwargs):
        """Proxy for `pyppeteer.page.Page.evaluate()`."""
        return await self._page.evaluate(*args, **kwargs)

    async def hide_grade(self):
        """Hides the grade element."""
        await self._page.evaluate(
            '''() => {
                const header = document.getElementsByClassName("layout--standard-console__header")[0];
                const gradeDiv = header.firstElementChild.children[1];
                gradeDiv.style.display = "none";
            }'''
        )

    async def collapse_sections(self, ignore=None):
        """Collapses the sections on the left.

        Args:
            ignore (Union[int, tuple]): Which sections to ignore.
                Default is None.
                0 - Submission Info
                1 - Tests
                2 - Files
                3 - Rubric
        """

        if ignore is None:
            ignore = list()

        section_arrows = await self._page.querySelectorAll('.ant-collapse-arrow')
        for i, arrow in enumerate(section_arrows):
            # skip files section
            if i in ignore: continue
            # collapse section by clicking on its arrow
            await arrow.click()

    async def select_file(self, file_index):
        """Selects a file.

        Args:
            file_index (int): The index of the file to select.
        """

        if file_index == self._selected_file:
            return

        async def _click_file():
            # using click() scrolls the files page just in case it needs to be scrolled
            files = await self._page.querySelectorAll('#file-menu li')
            await files[file_index].click()

        async def _keyboard_shortcut():
            await self._page.keyboard.down('Meta')
            await self._page.keyboard.press(str(file_index + 1))
            await self._page.keyboard.up('Meta')

        # easiest method
        await _keyboard_shortcut()
        self._selected_file = file_index

    async def align_comment(self, comment):
        """Aligns a comment.

        Args:
            comment (codepost.models.comments.Commens): The comment.
        """

        highlight = await self._page.querySelector(f'#line-{comment.startLine}-{comment.id}')
        await self._page.keyboard.down('Meta')
        await highlight.click()
        await self._page.keyboard.up('Meta')

    async def hide_elements(self, ids=None, classes=None):
        """Hides elements on the page.

        Args:
            ids (list[str]): The element ids to hide.
                Default is None.
            classes (list[str]): The element classes to hide.
                Default is None.
        """

        if ids is None and classes is None:
            return

        HIDE_IDS = '''
        ids.forEach((i) => {
            document.getElementById(i).style.display = "none";
        });
        '''

        HIDE_CLASSES = '''
        classes.forEach((c) => {
            document.getElementsByClassName(c).forEach((x) => {
                x.style.display = "none";
            });
        });'''

        if ids is None:
            await self._page.evaluate(
                '(classes) => {' + HIDE_CLASSES + '}',
                classes
            )
            return

        if classes is None:
            await self._page.evaluate(
                '(ids) => {' + HIDE_IDS + '}',
                ids
            )
            return

        await self._page.evaluate(
            '(ids, classes) => {' + HIDE_IDS + HIDE_CLASSES + '}',
            ids, classes
        )

    async def cover_elements(self, ids=None, classes=None):
        """Covers elements on the page.

        Args:
            ids (list[str]): The element ids to cover.
                Default is None.
            classes (list[str]): The element classes to cover.
                Default is None.
        """

        if ids is None and classes is None:
            return

        COVER_IDS = '''
        ids.forEach((i) => {
            document.getElementById(i).style.visibility = "hidden";
        });
        '''

        COVER_CLASSES = '''
        classes.forEach((c) => {
            document.getElementsByClassName(c).forEach((x) => {
                x.style.visibility = "hidden";
            });
        });'''

        if ids is None:
            await self._page.evaluate(
                '(classes) => {' + COVER_CLASSES + '}',
                classes
            )
            return

        if classes is None:
            await self._page.evaluate(
                '(ids) => {' + COVER_IDS + '}',
                ids
            )
            return

        await self._page.evaluate(
            '(ids, classes) => {' + COVER_IDS + COVER_CLASSES + '}',
            ids, classes
        )

    async def reset_column_width(self, code=False, comment=False):
        """Resets the column width of the code and comment panels.

        Args:
            code (bool): Whether to reset the code panel.
                Default is False.
            comment (bool): Whether to reset the comment panel.
                Default is False.
        """

        # default 728 px
        if code:
            await self._page.evaluate(
                'document.getElementById("code-container").style.width = "728px";',
                force_expr=True
            )
        # default 360 px
        if comment:
            await self._page.evaluate(
                'document.getElementById("code-panel--comments").style.width = "360px";',
                force_expr=True
            )

    async def set_column_width(self, code=None, comment=None, slider=False):
        """Sets the column width of the code and comment panels.

        Args:
            code (int): The width of the code panel.
                Default is None.
            comment (int): The width of the comment panel.
                Default is None.
            slider (bool): Whether to update the position of the slider.
                Default is False.
        """

        if code is not None:
            await self._page.evaluate(
                f'document.getElementById("code-container").style.width = "{code}px";',
                force_expr=True
            )

            if slider:
                slider_max = await self._page.evaluate(
                    '''parseFloat(
                        document.getElementsByClassName("rc-slider-handle-2")[0].getAttribute("aria-valuemax")
                    );''',
                    force_expr=True
                )
                slider_per = code / slider_max * 100
                await self._page.evaluate(
                    '''(sliderPer) => {
                        document.getElementsByClassName("rc-slider-track-1")[0].style.width = sliderPer + "%";
                        document.getElementsByClassName("rc-slider-handle-2")[0].style.left = sliderPer + "%";
                    }''',
                    slider_per
                )

        if comment is not None:
            await self._page.evaluate(
                f'document.getElementById("code-panel--comments").style.width = "{comment}px";',
                force_expr=True
            )

    async def screenshot(self, path, x=None, y=None, width=None, height=None):
        """Takes and saves a screenshot.

        Args:
            path (str): The path to save the screenshot.
            x (int): The x-value of the top-left of the screenshot.
                Default is 0.
            y (int): The y-value of the top-left of the screenshot.
                Default is 0.
            width (int): The width of the screenshot.
                Default is `self.width`.
            height (int): The height of the screenshot.
                Default is `self.height`.
        """

        if x is None: x = 0
        if y is None: y = 0
        if width is None: width = self._width
        if height is None: height = self._height

        clip = {
            'x': x,
            'y': y,
            'width': width,
            'height': height,
        }

        await self._page.screenshot(path=path, clip=clip)


async def take_screenshot(submission_id, comment_id,
                          filepath, page, strs, adjust=True, fit_to_comment=False, one_line=False):
    """Takes the screenshot and adds the metadata tattoo.

    Args:
        submission_id (int): The submission id.
        comment_id (int): The comment id.
        filepath (str): The path of the screenshot.
        page (pyppeteer.page.Page): The page.
        strs (list[str]): The information.
        adjust (bool): Whether to adjust the tattoo to not overlap the comment.
            Default is True.
        fit_to_comment (bool): Whether to fit to comment.
            Default is False.
        one_line (bool): Whether to make the tattoo one line.
            Default is False.
    """

    if fit_to_comment: one_line = True

    # getting cropping area for screenshot
    logger.debug('{}:{}: Getting cropping area', submission_id, comment_id)

    margins = await page.evaluate(
        '''() => {
            const element = document.getElementsByClassName("code-panel--code")[0];
            const style = element.currentStyle || window.getComputedStyle(element);
            return {
                left: parseFloat(style.marginLeft),
                right: parseFloat(style.marginRight),
            };
        }'''
    )
    side_padding = margins['left']
    middle_padding = margins['right']

    # actual code width should be same as `code_width`
    # actual comment width should be `comment_width - 10` because there's a 10px padding on the right
    actual_width = await page.evaluate(
        '''(commentID) => {
            return {
                code: document.getElementsByClassName("code-panel--code")[0].offsetWidth,
                comment: document.getElementById("comment-" + commentID).offsetWidth,
            };
        }''',
        comment_id
    )

    pic_width = side_padding + actual_width['code'] + middle_padding + actual_width['comment'] + side_padding
    if pic_width > page.width:
        # resize page to accommodate screenshot
        await page.set_width(pic_width)

    heights = await page.evaluate(
        '''(commentID) => {
            const slider = document.getElementById("code-panel").firstElementChild;
            const sliderStyle = slider.currentStyle || window.getComputedStyle(slider);
            const comment = document.getElementById("comment-" + commentID);
            const commentStyle = comment.currentStyle || window.getComputedStyle(comment);
            return {
                slider: slider.offsetHeight + parseFloat(sliderStyle.marginTop) + parseFloat(sliderStyle.marginBottom),
                code: document.getElementById("code-container").offsetHeight,
                comment: comment.offsetHeight,
                top: parseFloat(commentStyle.top), 
            };
        }''',
        comment_id
    )

    COMMENT_PADDING = 20
    BOX_PADDING = 5
    BOX_WIDTH = 0
    RIGHT_PADDING = 15
    BOTTOM_PADDING = 15
    COL_SPACE = 5
    LINE_SPACE = 5

    TITLES = ['Assignment:', 'Submission:', 'Comment ID:', 'File:', 'Category:', 'Comment:']

    # tattoo rectangle and texts
    if one_line:

        # getting font
        mono_font = get_font(MONO_FONTS, size=ONE_LINE_FONT_SIZE)

        max_x = - RIGHT_PADDING - BOX_WIDTH - BOX_PADDING
        max_y = - BOTTOM_PADDING - BOX_WIDTH - BOX_PADDING

        text = ' '.join(strs)
        text_width, text_height = mono_font.getsize(text)

        x = max_x - text_width
        y = max_y - text_height

        rectangle_coords = (
            x - BOX_PADDING - BOX_WIDTH, y - BOX_PADDING - BOX_WIDTH,
            - RIGHT_PADDING, - BOTTOM_PADDING
        )
        rectangle_kwargs = rectangle_kwargs = {
            'fill': CODEPOST_GREEN,
            'outline': None,
            'width': BOX_WIDTH,
        }

        texts = [(x, y, text, {'fill': WHITE, 'font': mono_font})]

    else:

        # getting fonts
        title_font = get_font(TITLE_FONTS, size=FONT_SIZE)
        sans_font = get_font(SANS_FONTS, size=FONT_SIZE)
        mono_font = get_font(MONO_FONTS, size=FONT_SIZE)

        fonts = [sans_font, mono_font, mono_font, mono_font, mono_font, mono_font]

        max_x = - RIGHT_PADDING - BOX_WIDTH - BOX_PADDING
        max_y = - BOTTOM_PADDING - BOX_WIDTH - BOX_PADDING

        max_width = 0
        max_height = 0
        for s, font in zip(strs, fonts):
            w, h = font.getsize(s)
            if w > max_width:
                max_width = w
            if h > max_height:
                max_height = h
        x2 = max_x - max_width

        max_width = 0
        for _, title in zip(strs, TITLES):
            w, h = title_font.getsize(title)
            if w > max_width:
                max_width = w
            if h > max_height:
                max_height = h
        x1 = x2 - COL_SPACE - max_width

        y = max_y - max_height * len(strs) - LINE_SPACE * (len(strs) - 1)
        rectangle_coords = (x1 - BOX_PADDING - BOX_WIDTH, y - BOX_PADDING - BOX_WIDTH,
                            - RIGHT_PADDING, - BOTTOM_PADDING)
        rectangle_kwargs = {
            'fill': CODEPOST_GREEN,
            'outline': None,
            'width': BOX_WIDTH,
        }

        texts = list()
        for s, title, font in zip(strs, TITLES, fonts):
            texts += [
                (x1, y, title, {'fill': WHITE, 'font': title_font}),
                (x2, y, s, {'fill': WHITE, 'font': font}),
            ]
            y += max_height + LINE_SPACE

    comment_bottom_y = heights['slider'] + heights['top'] + heights['comment']

    if fit_to_comment:
        pic_y1 = heights['slider'] + heights['top'] - COMMENT_PADDING
        pic_y2 = comment_bottom_y + COMMENT_PADDING
    else:
        pic_y1 = 0
        pic_y2 = max(heights['slider'] + heights['code'], comment_bottom_y) + heights['slider']

    if adjust:
        # diff = top of the tattoo - bottom of the comment
        tattoo_top_y = pic_y2 + rectangle_coords[1]
        diff = tattoo_top_y - comment_bottom_y
        # (0,0) is top left, so y increases as it goes down
        # if diff < 0, tattoo is going to overlap the comment
        # if diff < COMMENT_PADDING, the tattoo is going to be too close to the comment
        if diff < COMMENT_PADDING:
            # shift tattoo/y2 down by COMMENT_PADDING - diff
            pic_y2 += COMMENT_PADDING - diff

    pic_height = pic_y2 - pic_y1
    if pic_height > page.height:
        # resize page to accommodate screenshot
        await page.set_height(pic_height)

    logger.debug('{}:{}: Taking screenshot', submission_id, comment_id)
    await page.screenshot(path=filepath, y=pic_y1, width=pic_width, height=pic_height)

    logger.debug('{}:{}: Adding metadata to image', submission_id, comment_id)
    # assignment name
    # submission id
    # comment id
    # file name
    # category name (if rubric comment)
    # comment name (if rubric comment)

    img = Image.open(filepath)
    img_draw = ImageDraw.Draw(img)

    # draw rectangle
    rectangle_coords = (
        rectangle_coords[0] + pic_width, rectangle_coords[1] + pic_height,
        rectangle_coords[2] + pic_width, rectangle_coords[3] + pic_height
    )
    img_draw.rectangle(rectangle_coords, **rectangle_kwargs)

    # draw text
    for x, y, text, kwargs in texts:
        img_draw.text((x + pic_width, y + pic_height), text, **kwargs)

    img.save(filepath)

    logger.debug('{}:{}: Created screenshot at "{}"', submission_id, comment_id, filepath)


async def create_screenshot(browser,
                            submission, comment, assignment_name, file, file_index, output_folder,
                            timeout=60000, adjust=True, fit_to_comment=False, one_line=False):
    """Creates a screenshot for a comment.

    Args:
        browser (pyppeteer.browser.Browser): The browser.
        submission (codepost.models.submissions.Submissions): The submission.
        comment (codepost.models.comments.Comments): The comment.
        assignment_name (str): The assignment name.
        file (codepost.models.files.Files): The file the comment belongs to.
        file_index (int): The index of the file in the Files section.
        output_folder (str): The path of the folder where the screenshot should be saved.
        timeout (int): The timeout limit for the page to load, in milliseconds.
            Default is 60000 ms.
        adjust (bool): Whether to adjust the tattoo to not overlap the comment.
            Default is True.
        fit_to_comment (bool): Whether to fit to comment.
            Default is False.
        one_line (bool): Whether to make the tattoo one line.
            Default is False.
    """

    if fit_to_comment: one_line = True

    submission_id = submission.id
    comment_id = comment.id

    strs = [assignment_name, str(submission_id), str(comment_id), file.name]

    screenshot_file, category_name, comment_name = get_file_name(submission_id, comment_id, comment.rubricComment)
    filepath = os.path.join(output_folder, screenshot_file)

    if category_name is not None:
        strs += [category_name, comment_name]

    # create new page
    page = await CodePostPage.create(browser, submission_id)

    logger.debug('{}:{}: Loading page', submission_id, comment_id)
    elapsed = await page.open_submission(timeout=timeout)
    if elapsed == -1:
        return
    logger.debug('{}:{}: Loaded page ({:.2f})', submission_id, comment_id, elapsed)

    logger.debug('{}:{}: Selecting correct file', submission_id, comment_id)
    await page.select_file(file_index)

    logger.debug('{}:{}: Aligning comment', submission_id, comment_id)
    await page.align_comment(comment)

    # hide other comments
    logger.debug('{}:{}: Hiding other comments', submission_id, comment_id)
    comments = [f'comment-{c.id}' for c in file.comments if c.id != comment_id]
    await page.hide_elements(ids=comments)

    # hide header bar, slider bar, section panel, command bar, and intercom
    logger.debug('{}:{}: Hiding unwanted elements', submission_id, comment_id)
    elements = ['Code-Header', 'commandbar-wrapper', 'intercom-frame']
    hide_classes = ['layout--standard-console__header', 'intercom-lightweight-app']
    cover_classes = ['layout-resizer']
    await page.hide_elements(ids=elements, classes=hide_classes)
    await page.cover_elements(classes=cover_classes)

    # set column widths
    logger.debug('{}:{}: Setting column widths', submission_id, comment_id)
    code_width = 600
    comment_width = 500
    await page.set_column_width(code=code_width, comment=comment_width)

    # take screenshot
    await take_screenshot(submission_id, comment_id, filepath, page, strs, adjust, fit_to_comment, one_line)


async def create_screenshots(comments, timeout=60000, adjust=True, fit_to_comment=False, one_line=False):
    """Creates screenshots of the given comments.
    Adapted from https://gist.github.com/jlumbroso/c0ec0c4f1a0a502e3835c183cbe89c65 for SPA.

    Args:
        comments (list[tuple]): The comments to create screenshots for.
        timeout (int): The timeout limit for the page to load, in milliseconds.
            Default is 60000 ms.
        adjust (bool): Whether to adjust the tattoo to not overlap the comment.
            Default is True.
        fit_to_comment (bool): Whether to fit to comment.
            Default is False.
        one_line (bool): Whether to make the tattoo one line.
            Default is False.
    """

    if fit_to_comment: one_line = True

    logger.info('Launching browser')
    start = time.time()
    browser = await launch()
    end = time.time()
    logger.debug('Launched browser ({:.2f})', end - start)

    # store JWT
    logger.debug('Storing JWT token')
    start = time.time()
    page = await browser.newPage()
    await page.goto(LOGIN_URL)
    await page.evaluate('(token) => { localStorage.setItem("token", token); }', JWT_KEY)
    await page.close()
    end = time.time()
    logger.debug('Stored JWT token ({:.2f})', end - start)

    # create screenshot for all submissions
    screenshots = [
        create_screenshot(
            browser, *comment_info,
            timeout=timeout, adjust=adjust, fit_to_comment=fit_to_comment, one_line=one_line
        )
        for comment_info in comments
    ]
    # allows all screenshots to be generated synchronously as coroutines
    await asyncio.gather(*screenshots)

    logger.debug('Closing browser')
    await browser.close()


@cli.command(
    'screenshot',
    **CTX_SETTINGS,
    help='Screenshots a linked comment.'
)
@click.argument('link', type=str, required=False)
@click.option('-f', '--file', type=str,
              help='A file to read submission links from.')
@click.option('-t', '--timeout', type=click.IntRange(30, None), default=60,
              help='Timeout limit in seconds. Must be at least 30. Default is 60 sec.')
@click.option('-nt', '--no-timeout', is_flag=True, default=False, flag_value=True,
              help='Whether to run without timeout. Default is False.')
@click.option('-a', '--adjust', is_flag=True, default=True, flag_value=True,
              help='Whether to adjust the tattoo to not overlap the comment. Default is True.')
@click.option('-c', '--fit-to-comment', is_flag=True, default=False, flag_value=True,
              help='Whether to fit to comment. Default is False.')
@click.option('-o', '--one-line', is_flag=True, default=False, flag_value=True,
              help='Whether to make the tattoo one line. Default is False.')
@with_codepost
def screenshot_cmd(*args, **kwargs):
    """Screenshots a linked comment.
    Average time to load a page: ~25 sec.

    \b
    Expected time:
        Single link: 20-60 sec.
    """

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
    link = kwargs.get('link', None)
    file = kwargs.get('file', None)

    timeout = kwargs.get('timeout', 60)
    no_timeout = kwargs.get('no_timeout', False)
    adjust = kwargs.get('adjust', True)
    fit_to_comment = kwargs.get('fit_to_comment', False)
    one_line = kwargs.get('one_line', False)

    if fit_to_comment: one_line = True

    if no_timeout:
        timeout = 0
    else:
        timeout *= 1000

    if link is None and file is None:
        logger.error('No arguments given')
        return

    links = list()

    if link is not None:
        links.append(link)

    if file is not None:
        filepath, file_ext = validate_file(file)
        links += read_links_from_file(filepath, file_ext)

    if len(links) == 0:
        logger.error('No links to process')
        return

    logger.info('Extracting submission id and comment id from links')

    # maps assignment id -> assignment folder
    outputs = dict()
    # maps assignment id -> assignment name
    assignment_names = dict()

    if not os.path.exists(OUTPUT_FOLDER):
        os.mkdir(OUTPUT_FOLDER)

    comments = list()
    for link in links:
        submission_id, comment_id = parse_link(link)

        if submission_id is None and comment_id is None:
            logger.error('"{}": No submission id or comment id', link)
            continue
        elif submission_id is None:
            logger.error('"{}": No submission id found', link)
            continue
        elif comment_id is None:
            logger.error('"{}": No comment id found', link)
            continue

        try:
            submission = codepost.submission.retrieve(submission_id)
        except codepost.errors.AuthorizationAPIError:
            logger.error('"{}":{}: No access', link, submission_id)
            continue
        except codepost.errors.NotFoundAPIError:
            logger.error('"{}":{}: Invalid id', link, submission_id)
            continue

        try:
            comment = codepost.comment.retrieve(comment_id)
        except codepost.errors.AuthorizationAPIError:
            logger.error('"{}":{}:{}: No access', link, submission_id, comment_id)
            continue
        except codepost.errors.NotFoundAPIError:
            logger.error('"{}":{}:{}: Invalid id', link, submission_id, comment_id)
            continue

        file = codepost.file.retrieve(comment.file)
        file_index = sorted(f.name.lower() for f in submission.files).index(file.name.lower())

        # get output folder
        assignment_id = submission.assignment
        assignment_folder = outputs.get(assignment_id, None)
        if assignment_folder is None:
            # create output folder
            assignment = codepost.assignment.retrieve(submission.assignment)
            course = codepost.course.retrieve(assignment.course)

            course_folder = os.path.join(OUTPUT_FOLDER, course_str(course))
            if not os.path.exists(course_folder):
                os.mkdir(course_folder)
            assignment_folder = os.path.join(course_folder, assignment.name)
            if not os.path.exists(assignment_folder):
                os.mkdir(assignment_folder)

            outputs[assignment_id] = assignment_folder
            assignment_names[assignment_id] = assignment.name

        comments.append(
            (submission, comment, assignment_names[assignment_id], file, file_index, assignment_folder)
        )

    logger.debug('Creating screenshots for {} comments', len(comments))

    asyncio.run(create_screenshots(comments, timeout, adjust, fit_to_comment, one_line))


# ===========================================================================

if __name__ == '__main__':
    cli()
