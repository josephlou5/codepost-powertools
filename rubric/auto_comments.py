"""
auto_comments.py
Automatically add rubric comments to submissions.

Rubric comments:
- all MISSING file comments
- no-comments
- no-space-after-slash

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs
"""

# ===========================================================================

import click
from loguru import logger
import codepost

from shared import *

# ===========================================================================

RUBRIC_COMMENTS = [
    'no-comments',  # 71462
    'no-space-after-slash',  # 72151
]

ONLY_ONCE = [
    'no-comments',
]

COMMENTS = dict()

MISSING = dict()


# ===========================================================================

def get_assignment(course, a_name) -> codepost.models.assignments.Assignments:
    """Get an assignment from a course.

    Args:
         course (codepost.models.courses.Courses): The course.
         a_name (str): The name of the assignment.

    Returns:
        codepost.models.assignments.Assignments: The assignment.
            Returns None if no assignment exists with that name.
    """
    assignment = None
    for a in course.assignments:
        if a.name == a_name:
            assignment = a
            break
    if assignment is None:
        logger.critical('Assignment "{}" not found', a_name)
    return assignment


# ===========================================================================

def get_rubric_comment_ids(assignment):
    """Get the ids for the rubric comments in COMMENTS.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
    """
    global COMMENTS

    logger.info('Getting ids for rubric comments')

    # comments = [comment for c in assignment.rubricCategories for comment in c.rubricComments]
    comments = sum((c.rubricComments for c in assignment.rubricCategories), [])

    for c in comments:
        if c.name in RUBRIC_COMMENTS:
            COMMENTS[c.name] = c.id

    diff = set(RUBRIC_COMMENTS) - set(COMMENTS.keys())
    if len(diff) > 0:
        logger.warning('Could not find {} rubric comments:', len(diff))
        for name in diff:
            logger.warning('  {}', name)

    logger.info('Got ids for rubric comments')


def get_missing_comment_ids(assignment):
    """Get the ids for the rubric comments in the "MISSING" category, if it exists.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
    """
    global MISSING

    logger.info('Getting ids for "MISSING" rubric comments')

    missing_category = next((c for c in assignment.rubricCategories if c.name == 'MISSING'), None)

    # there is no MISSING rubric category
    if missing_category is None:
        logger.warning('Could not find "MISSING" rubric category')
        return

    comments = missing_category.rubricComments
    for comment in comments:
        filename = comment.text.split('`')[1]
        MISSING[filename] = comment.id

    logger.info('Got ids for "MISSING" rubric comments')


# ===========================================================================

def parse_file(file) -> (list, int):
    """Parses a file for instances of rubric comments.

    Args:
        file (codepost.models.files.Files): The file.

    Returns:
        (list, int): The comments, in a dict format with the keys:
                (text, startChar, endChar, startLine, endLine, file, rubricComment)
            and the number of comments in the file.
    """

    f_id = file.id

    comments = list()

    # possible states:
    # - normal
    # - in string
    # - first slash
    # - slash comment
    # - starting multi comment
    # - in multi comment
    # - first asterisk
    state = 'normal'

    num_comments = 0

    for line_num, line in enumerate(file.code.split('\n')):
        if state != 'in multi comment':
            state = 'normal'
        for char_num, c in enumerate(line):
            if state == 'normal':
                if c == '/':
                    state = 'first slash'
                elif c == '"':
                    state = 'in string'
            elif state == 'in string':
                if c == '"':
                    state = 'normal'
            elif state == 'first slash':
                if c == '/':
                    state = 'slash comment'
                elif c == '*':
                    state = 'start multi comment'
                elif c == '"':
                    state = 'in string'
                else:
                    state = 'normal'
            elif state == 'slash comment':
                num_comments += 1
                if 'no-space-after-slash' in COMMENTS and c != ' ':
                    # in a comment, but there's no space
                    comments.append({
                        'text': '',
                        'startChar': char_num - 2,
                        'endChar': char_num,
                        'startLine': line_num,
                        'endLine': line_num,
                        'file': f_id,
                        'rubricComment': COMMENTS['no-space-after-slash'],
                    })
                # rest of the line is part of the comment
                state = 'normal'
                break
            elif state == 'start multi comment':
                num_comments += 1
                if 'no-space-after-slash' in COMMENTS and c != ' ':
                    # in a comment, but there's no space
                    comments.append({
                        'text': '',
                        'startChar': char_num - 2,
                        'endChar': char_num,
                        'startLine': line_num,
                        'endLine': line_num,
                        'file': f_id,
                        'rubricComment': COMMENTS['no-space-after-slash'],
                    })

                if c == '*':
                    state = 'first asterisk'
                else:
                    state = 'in multi comment'
            elif state == 'in multi comment':
                if c == '*':
                    state = 'first asterisk'
            elif state == 'first asterisk':
                if c == '/':
                    state = 'normal'
                else:
                    state = 'in multi comment'

    return comments, num_comments


# ===========================================================================

def create_comments(assignment) -> list:
    """Create automatically applied rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        list: The comments, in a dict format with the keys:
            (text, startChar, endChar, startLine, endLine, file, rubricComment)
    """

    logger.info('Creating automatic rubric comments')

    all_comments = list()

    submissions = assignment.list_submissions()
    logger.debug('Iterating through {} total submissions', len(submissions))
    for i, submission in enumerate(submissions):

        if submission.isFinalized: continue

        all_files = submission.files

        # only look through files that don't have any comments
        files = list()
        # find existing comments
        ids = set(MISSING.values()).union(COMMENTS[name] for name in ONLY_ONCE if name in COMMENTS)
        existing_comments = set()
        for file in all_files:
            if len(file.comments) == 0:
                files.append(file)
            else:
                for comment in file.comments:
                    if comment.rubricComment in ids:
                        existing_comments.add(comment.rubricComment)
        del ids

        if len(files) == 0: continue

        first_file = min(files, key=lambda f: f.name)

        # checking for missing files
        missing_files = set(MISSING.keys()) - set(f.name for f in all_files)
        for filename in missing_files:
            if MISSING[filename] not in existing_comments:
                all_comments.append({
                    'text': '',
                    'startChar': 0,
                    'endChar': 0,
                    'startLine': 0,
                    'endLine': 0,
                    'file': first_file.id,
                    'rubricComment': MISSING[filename],
                })
        del missing_files

        # parsing files
        total_num_comments = 0
        for file in files:
            if file.extension != 'java': continue

            comments, num_comments = parse_file(file)

            # only update all_comments with comments that haven't occurred yet
            all_comments += [c for c in comments if c['rubricComment'] not in existing_comments]
            total_num_comments += num_comments

        # no comments in any file
        if total_num_comments == 0:
            if COMMENTS['no-comments'] not in existing_comments:
                all_comments.append({
                    'text': '',
                    'startChar': 0,
                    'endChar': 0,
                    'startLine': 0,
                    'endLine': 0,
                    'file': first_file.id,
                    'rubricComment': COMMENTS['no-comments'],
                })

        if i > 0 and i % 100 == 0:
            logger.debug('Done with submission {}', i + 1)

    logger.info('Created automatic rubric comments')

    return all_comments


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, testing):
    """Automatically add rubric comments to submissions.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment. \f
        testing (bool): Whether to run as a test.
            Default is False.
    """

    logger.info('Start')

    logger.info('Logging into codePost')
    success = log_in_codepost()
    if not success:
        return

    logger.info('Accessing codePost course')
    if testing:
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

    get_rubric_comment_ids(assignment)

    get_missing_comment_ids(assignment)

    apply_comments = create_comments(assignment)

    logger.info('Applying {} rubric comments', len(apply_comments))
    for comment in apply_comments:
        codepost.comment.create(**comment)

    logger.info('Done')


# ===========================================================================

if __name__ == '__main__':
    main()
