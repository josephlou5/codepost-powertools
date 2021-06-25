"""
stats.py
Lists current stats of the grading queue.
Only meant for use from the command line.
"""

# ===========================================================================

import datetime
import os
from typing import (
    Tuple,
)

from loguru import logger

from shared import *
from shared_codepost import *

# ===========================================================================

# constants

BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)
GREEN: Color = (0, 175, 0)
RED: Color = (255, 0, 0)
YELLOW: Color = (255, 255, 0)


# ===========================================================================

def get_counts(assignment: Assignment
               ) -> Tuple[int, int, int, int, int, int, int]:
    """Gets the stats counts for an assignment.

    Args:
        assignment (Assignment): The assignment.

    Returns:
        Tuple[int, int, int, int, int, int, int]:
            The counts of:
            - total submissions
            - finalized submissions
            - unfinalized submissions
            - claimed submissions
            - unclaimed submissions
            - draft submissions
            - submissions held by dummy grader
    """

    submissions = assignment.list_submissions()
    num_finalized = 0
    num_unfinalized = 0
    num_unclaimed = 0
    num_drafts = 0
    num_dummy_grader = 0
    for submission in submissions:
        if submission.isFinalized:
            num_finalized += 1
            continue
        num_unfinalized += 1
        if submission.grader is None:
            num_unclaimed += 1
        elif submission.grader == DUMMY_GRADER:
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


# ===========================================================================

def import_pygame():
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
    return pygame


def stats_window(title: str,
                 assignment: Assignment,
                 interval: int
                 ):
    """Display the stats window.

    Args:
        title (str): The title of the window.
        assignment (Assignment): The assignment to display stats for.
        interval (int): The second interval for updating the window.
    """

    pygame = import_pygame()

    def create_text(font_obj: pygame.font.Font,
                    x: float,
                    y: float,
                    text: str,
                    color: Color = BLACK,
                    align: str = 'LEFT',
                    min_x: float = None,
                    max_x: float = None
                    ) -> Tuple[pygame.SurfaceType, Tuple[float, float]]:
        """Creates args for displaying text with `surface.blit()`.

        Args:
            font_obj (pygame.font.Font): The font object.
            x (float): The x-position.
            y (float): The y-position.
            text (str): The text to display.
            color (Color): The color of the text.
                Default is BLACK.
            align (str): The alignment of the text with respect to (x, y).
                Choices: LEFT, CENTER, RIGHT.
                Default is LEFT.
            min_x (float): The minimum x-value.
                Default is None.
            max_x (float): The maximum x-value.
                Default is None.

        Returns:
            Tuple[pygame.SurfaceType, Tuple[float, float]]: The args.
        """

        text = str(text)
        w, h = font_obj.size(text)

        px = x
        py = y - h / 2

        if align == 'CENTER':
            px = x - w / 2
        elif align == 'RIGHT':
            px = x - w

        if min_x is not None and px < min_x:
            px = min_x
        elif max_x is not None and px > max_x - w:
            px = max_x - w

        return font_obj.render(text, True, color), (px, py)

    # fonts
    font = 'sfprotext'
    monofont = 'sfnsmono'

    # use pygame to display window
    pygame.init()

    # set up window
    width, height = 500, 250
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(title)

    # create text
    text25 = pygame.font.SysFont(font, 25)
    text15 = pygame.font.SysFont(font, 15)
    mono15 = pygame.font.SysFont(monofont, 15)

    # title and status
    title_text = create_text(text25, width / 2, 20, title, align='CENTER')
    status_y = 45

    # number summary section
    nums_y = 70
    nums_dy = 25
    rect_x = 10
    nums_x0 = 30
    nums_x1 = 150
    nums_x2 = 220
    text_labels = ('Total', 'Finalized', 'Unfinalized', 'Claimed', 'Unclaimed', 'Drafts', 'Held')
    labels = [create_text(text15, nums_x0, nums_y + i * nums_dy, text)
              for i, text in enumerate(text_labels)]
    side = 10
    rects = [
        # finalized
        (GREEN, pygame.Rect(rect_x, nums_y + 1 * nums_dy - side / 2, side, side)),
        # unfinalized
        (YELLOW, pygame.Rect(rect_x, nums_y + 2 * nums_dy - side / 2, side, side / 2)),
        (RED, pygame.Rect(rect_x, nums_y + 2 * nums_dy, side, side / 2)),
        # claimed
        (GREEN, pygame.Rect(rect_x, nums_y + 3 * nums_dy - side / 2, side / 2, side)),
        (YELLOW, pygame.Rect(rect_x + side / 2, nums_y + 3 * nums_dy - side / 2, side / 2, side)),
        # unclaimed
        (RED, pygame.Rect(rect_x, nums_y + 4 * nums_dy - side / 2, side, side)),
        # drafts
        (YELLOW, pygame.Rect(rect_x, nums_y + 5 * nums_dy - side / 2, side, side)),
        # held by dummy grader
        (BLACK, pygame.Rect(rect_x, nums_y + 6 * nums_dy - side / 2, side, side)),
    ]
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
    screen.blit(*create_text(text25, width / 2, height / 2, 'Loading...', align='CENTER'))
    pygame.display.flip()

    clock = pygame.time.Clock()
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
        total, *counts = get_counts(assignment)
        n_finalized, unfinalized, claimed, unclaimed, drafts, dummy_grader = counts
        countdown = interval

        screen.fill(WHITE)
        screen.blit(*title_text)
        screen.blit(*create_text(text15, width / 2, status_y,
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

        # label pie chart sections
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

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         window: int = None,
         log: bool = False
         ):
    """Lists current stats of the grading queue.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        window (int): The window update interval in seconds.
            Must be at least 10.
            If not given, will not display window.
        log (bool): Whether to show log messages.
            Default is False.
    """

    # check args
    if window is not None and window < 10:
        raise ValueError('`window` must be at least 10')

    # no output in this situation
    if not log and window is None: return

    success = log_in_codepost(log=log)
    if not success: return dict()

    success, course = get_course(course_name, course_period, log=log)
    if not success: return dict()

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return dict()

    # display stats
    if window is None:
        logger.info('Getting stats')
        total, n_finalized, unfinalized, claimed, unclaimed, drafts, dummy_grader = get_counts(assignment)
        logger.info('{} total submissions', total)
        if total == 0: return
        stat_format = '{:<3d} [{:>6.2%}] {}'
        for num, label in ((n_finalized, 'finalized'),
                           (unfinalized, 'unfinalized'),
                           (claimed, 'claimed'),
                           (unclaimed, 'unclaimed'),
                           (drafts, 'drafts')):
            logger.info(stat_format, num, num / total, label)
        if dummy_grader > 0:
            logger.info(stat_format, dummy_grader, dummy_grader / total, 'claimed by dummy grader')
        return

    # display window
    if log: logger.info('Displaying window')
    title = f'Stats for {course_str(course)} {assignment.name}'
    stats_window(title, assignment, window)

# ===========================================================================
