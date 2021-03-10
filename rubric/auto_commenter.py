"""
auto_commenter.py
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
import time
import comma

from shared import *

# ===========================================================================

COMMENT_AUTHOR = 'jdlou+autocommenter@princeton.edu'

COMMENTS_FILE = 'added_auto_comments_{}_{}.csv'

# ===========================================================================

RUBRIC_COMMENTS = [
    'no-comments',  # 71462
    'no-space-after-slash',  # 72151
]

# ids of the rubric comments
# name -> id
COMMENTS = dict()

# names of the rubric comments
# id -> name
ID_TO_NAME = dict()

# ids of the missing file rubric comments
# filename -> id
MISSING = dict()


# ===========================================================================

class Comment:
    """Comment object: Represents a Comment.

    Constructors:
        Comment(s_id, comment_id, file_id, file_name, text='',
                line=None, start_line=None, end_line=None,
                start_char=None, end_char=None)
            Initializes a Comment object.

        Comment.from_codepost(file, comment):
            Initializes a Comment object from a codePost comment.

    Properties:
        name (str): The rubric comment name.
        file_name (str): The name of the file where the comment should be applied.
        line_num (int): The start line number of the comment.

    Static Methods:
        from_csv(comment_dict)
            Converts a file dict into a comment creation kwargs dict.

    Methods:
        add_instance(line_num)
            Adds an instance of this rubric comment.

        as_dict()
            Returns the kwargs dict for creating this comment.

        for_file()
            Returns a csv representation of this comment for a file.
    """

    def __init__(self, s_id, comment_id, file_id, file_name, text='',
                 line=None, start_line=None, end_line=None,
                 start_char=None, end_char=None):
        """Initializes a Comment object.

        Args:
            s_id (int): The submission id.
            comment_id (int): The rubric comment id.
            file_id (int): The id of the file where the comment should be applied.
            file_name (str): The name of the file where the comment should be applied.
            text (str): The custom text of the comment.
                Default is the empty string.
            line (int): The line number of the comment.
                Default is 0.
            start_line (int): The start line number of the comment. Overrides `line`.
                Default is 0.
            end_line (int): The end line number of the comment. Overrides `line`.
                Default is 0.
            start_char (int): The start char index of the comment.
                Default is 0.
            end_char (int): The end char index of the comment.
                Default is 0.

        Raises:
            ValueError: If `comment_id` is not used in this program.
        """

        self._s_id = s_id

        self._rubric_comment = comment_id
        self._file_id = file_id

        # for saving in file
        if comment_id not in ID_TO_NAME:
            raise ValueError(f'rubric comment {comment_id} not used in this program')
        self._comment_name = ID_TO_NAME[comment_id]
        self._file_name = file_name

        self._text = text
        self._extra_instances = list()

        self._start_line = 0
        if start_line is not None:
            self._start_line = start_line
        elif line is not None:
            self._start_line = line

        self._end_line = self._start_line
        if end_line is not None and end_line > self._start_line:
            self._end_line = end_line

        self._start_char = 0
        if start_char is not None:
            self._start_char = start_char

        self._end_char = 0
        if end_char is not None:
            self._end_char = end_char
        if self._start_line == self._end_line and self._end_char < self._start_char:
            self._end_char = self._start_char

    @classmethod
    def from_codepost(cls, file, comment):
        """Initializes a Comment object from a codePost comment.

        Args:
            file (codepost.models.files.Files): The file.
            comment (codepost.models.comments.Comments): The comment.
        """

        s_id = file.submission
        comment_id = comment.rubricComment
        file_id = file.id
        file_name = file.name
        text = comment.text
        start_line = comment.startLine
        end_line = comment.endLine
        start_char = comment.startChar
        end_char = comment.endChar

        return cls(s_id, comment_id, file_id, file_name, text=text,
                   start_line=start_line, end_line=end_line,
                   start_char=start_char, end_char=end_char)

    # ==================================================

    @property
    def name(self):
        return self._comment_name

    @property
    def file_name(self):
        return self._file_name

    @property
    def line_num(self):
        return self._start_line

    # ==================================================

    @staticmethod
    def from_csv(comment_dict) -> dict:
        """Converts a file dict into a comment creation kwargs dict.

        Args:
            comment_dict (dict[str, str]): The comment in its csv format.

        Raises:
            KeyError: If `comment_dict` doesn't contain the proper keys.
            ValueError: If appropriate values of `comment_dict` cannot be converted to `int`.

        Returns:
            dict: The comment in kwargs format for creating.
        """
        return {
            'text': comment_dict['text'],
            'startChar': int(comment_dict['start_char']),
            'endChar': int(comment_dict['end_char']),
            'startLine': int(comment_dict['start_line']),
            'endLine': int(comment_dict['end_line']),
            'file': int(comment_dict['file_id']),
            'rubricComment': int(comment_dict['comment_id']),
            'author': COMMENT_AUTHOR,
        }

    # ==================================================

    def _create_text(self) -> str:
        """Create the text of the comment."""

        text = self._text
        num_extra = len(self._extra_instances)
        if num_extra > 0:
            if text != '':
                text += '\n\n'
            if num_extra == 1:
                text += f'Also see line {self._extra_instances[0]}.'
            elif num_extra == 2:
                text += f'Also see lines {self._extra_instances[0]} and {self._extra_instances[1]}.'
            else:
                text += 'Also see lines '
                # text += ''.join(f'{line}, ' for line in self._extra_instances[:-1])
                for line in self._extra_instances[:-1]:
                    text += str(line) + ', '
                text += f'and {self._extra_instances[-1]}.'
        return text

    # ==================================================

    def add_instance(self, line_num):
        """Adds an instance of this rubric comment.

        Args:
            line_num (int): The line number of the repeat rubric comment (0-indexed).
        """
        self._extra_instances.append(line_num + 1)

    def as_dict(self) -> dict:
        """Returns the kwargs dict for creating this comment."""
        return self.from_csv(self.for_file())

    def for_file(self) -> dict:
        """Returns a csv representation of this comment for a file."""
        return {
            'submission_id': self._s_id,
            'file_name': self._file_name,
            'file_id': self._file_id,
            'comment': self._comment_name,
            'comment_id': self._rubric_comment,
            'start_line': self._start_line,
            'end_line': self._end_line,
            'start_char': self._start_char,
            'end_char': self._end_char,
            'text': self._create_text(),
        }


# ===========================================================================

class SubmissionComments:
    """SubmissionComments object: Represents the comments for a submission.

    Constructors:
        SubmissionComments(submission)
            Initializes a SubmissionComments object.

    Properties:
        num_comments (int): The number of comments to apply to this submission.
        for_file (list[str]): The comments in str format for saving in the file.

    Methods:
        add_comment(*args, **kwargs)
            Adds a comment to this submission.

        applying()
            Returns the comments to apply to this submission.
    """

    def __init__(self, submission, comments=None):
        """Initializes a SubmissionComments object.

        Args:
            submission (codepost.models.submissions.Submissions): The submission.
            comments (list): The comments in this submission.
                Default is None. If not given, will get from `submission`.
        """

        self._submission = submission
        self._s_id = submission.id

        if comments is None:
            comments = [c for file in submission.files for c in file.comments]

        # get all existing comments
        self._existing_comments = set()
        for comment in comments:
            rubric_comment = comment.rubricComment
            if rubric_comment is None: continue
            # not using these rubric comments
            if rubric_comment not in ID_TO_NAME: continue
            # add comment name to existing
            self._existing_comments.add(ID_TO_NAME[rubric_comment])

        self._comments = dict()
        self._for_file = list()

    # ==================================================

    @property
    def num_comments(self):
        return len(self._comments)

    @property
    def for_file(self):
        return self._for_file

    # ==================================================

    def add_comment(self, *args, **kwargs):
        """Adds a comment to this submission.

        Args:
            The args and kwargs to create a Comment.
        """

        comment = Comment(self._s_id, *args, **kwargs)
        name = comment.name

        # don't add repeat comments
        if name in self._existing_comments:
            return

        if name in self._comments:
            # update old comment with new instances if in same file and not same line
            old_comment = self._comments[name]
            if old_comment.file_name == comment.file_name and old_comment.line_num != comment.line_num:
                old_comment.add_instance(comment.line_num)
        else:
            # new comment
            self._comments[name] = comment
            self._for_file.append(comment.for_file())

    def applying(self) -> list[dict]:
        """Returns the comments to apply to this submission.

        Returns:
            list[dict]: The comments to apply in kwargs format.
        """

        applying = list()
        for comment in self._comments.values():
            applying.append(comment.as_dict())
        return applying


# ===========================================================================

def get_rubric_comment_ids(assignment):
    """Gets the ids for the rubric comments in COMMENTS.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
    """
    global COMMENTS
    global ID_TO_NAME

    logger.info('Getting ids for rubric comments')

    for category in assignment.rubricCategories:
        for comment in category.rubricComments:
            if comment.name not in RUBRIC_COMMENTS: continue
            c_name = comment.name
            COMMENTS[c_name] = comment.id
            ID_TO_NAME[comment.id] = c_name
            logger.debug('Found rubric comment for "{}"', c_name)

    diff = set(RUBRIC_COMMENTS) - set(COMMENTS.keys())
    if len(diff) > 0:
        logger.warning('Could not find {} rubric comments:', len(diff))
        for name in diff:
            logger.warning('  {}', name)

    logger.info('Got ids for rubric comments')


def get_missing_comment_ids(assignment):
    """Gets the ids for the rubric comments in the "MISSING" category, if it exists.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
    """
    global MISSING
    global ID_TO_NAME

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
        ID_TO_NAME[comment.id] = 'missing-' + filename.split('.')[0].lower()
        logger.debug('Found missing rubric comment for "{}"', filename)

    logger.info('Got ids for "MISSING" rubric comments')


# ===========================================================================

def parse_file(submission_comments, file) -> int:
    """Parses a file for instances of rubric comments.

    Args:
        submission_comments (SubmissionComments): The SubmissionComments object for this submission.
        file (codepost.models.files.Files): The file.

    Returns:
        int: The number of comments in the file.
    """

    f_id = file.id
    f_name = file.name

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

        if state in ('starting multi comment', 'in multi comment', 'first asterisk'):
            state = 'in multi comment'
        else:
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

                if c.isalpha() and 'no-space-after-slash' in COMMENTS:
                    # in a comment, but there's no space
                    submission_comments.add_comment(
                        COMMENTS['no-space-after-slash'], f_id, f_name,
                        line=line_num, start_char=char_num - 2, end_char=char_num
                    )

                # rest of the line is part of the comment
                state = 'normal'
                break

            elif state == 'start multi comment':
                num_comments += 1

                if c == '*':
                    state = 'first asterisk'
                    continue

                if c.isalpha() and 'no-space-after-slash' in COMMENTS:
                    # in a multi line comment, but there's no space
                    # /** passes, and doesn't check after that
                    submission_comments.add_comment(
                        COMMENTS['no-space-after-slash'], f_id, f_name,
                        line=line_num, start_char=char_num - 2, end_char=char_num
                    )

                state = 'in multi comment'

            elif state == 'in multi comment':
                if c == '*':
                    state = 'first asterisk'

            elif state == 'first asterisk':
                if c == '/':
                    state = 'normal'
                elif c != '*':
                    state = 'in multi comment'

    return num_comments


# ===========================================================================

def create_submission_comments(submission) -> SubmissionComments:
    """Creates automatically applied rubric comments for a submission.

    Args:
        submission (codepost.models.submissions.Submissions): The submission.

    Returns:
        SubmissionComments: The SubmissionComments object for this submission.
    """

    files = dict()
    comments = list()
    for file in submission.files:
        files[file.name] = file
        comments += file.comments

    submission_comments = SubmissionComments(submission, comments)

    first_file = files[min(files.keys(), key=lambda n: n.lower())]

    # check for missing files
    missing_files = set(MISSING.keys()) - set(files.keys())
    for filename in missing_files:
        submission_comments.add_comment(MISSING[filename], first_file.id, first_file.name)

    # parsing files
    total_num_comments = 0
    for name, file in files.items():
        if not name.endswith('.java'): continue
        total_num_comments += parse_file(submission_comments, file)

    # no comments in any file
    if total_num_comments == 0:
        submission_comments.add_comment(COMMENTS['no-comments'], first_file.id, first_file.name)

    return submission_comments


# ===========================================================================

def create_comments(assignment) -> list[SubmissionComments]:
    """Creates automatically applied rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        list[SubmissionComments]: The SubmissionComment objects for each submission.
    """

    logger.info('Creating automatic rubric comments')

    all_comments = list()

    submissions = assignment.list_submissions()
    logger.debug('Iterating through {} total submissions', len(submissions))
    for i, submission in enumerate(submissions):

        if submission.isFinalized: continue

        submission_comments = create_submission_comments(submission)

        if submission_comments.num_comments > 0:
            all_comments.append(submission_comments)

        if i % 100 == 99:
            logger.debug('Done with submission {}', i + 1)

    logger.info('Created automatic rubric comments')

    return all_comments


# ===========================================================================

def read_comments_file(filename) -> list[dict]:
    """Read comments from a file and return the kwargs dict to create them.

    Args:
        filename (str): The name of the file.

    Returns:
        list[dict]: The comments to apply in kwargs format.
    """

    logger.info('Reading comments from file')

    data = comma.load(filename, force_header=True)
    if data is None:
        logger.info('File "{}" not found', filename)
        return list()
    if len(data) == 0:
        logger.info('No comments found in file "{}"', filename)
        return list()

    applying = list()
    for row in data:
        applying.append(Comment.from_csv(row))

    return applying


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-f', '--from-file', is_flag=True, default=False, flag_value=True,
              help='Whether to read the comments from a file. Default is False.')
@click.option('-a', '--apply', is_flag=True, default=False, flag_value=True,
              help='Whether to apply the comments. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, from_file, apply, testing):
    """Automatically add rubric comments to submissions.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment. \f
        from_file (bool): Whether to read the comments form a file.
            Default is False.
        apply (bool): Whether to apply the comments.
            Default is False.
        testing (bool): Whether to run as a test.
            Default is False.
    """

    if from_file and not apply:
        logger.warning('Reading from file but not applying')

    start = time.time()

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

    filename = COMMENTS_FILE.format(course_str(course, delim='_'), assignment_name)

    applying = list()

    # reading comments from file
    if from_file:
        applying = read_comments_file(filename)

    if len(applying) == 0:

        get_rubric_comment_ids(assignment)

        get_missing_comment_ids(assignment)

        all_submission_comments = create_comments(assignment)

        if len(all_submission_comments) == 0:
            logger.info('No comments to apply')

        else:
            applying = list()
            for_file = list()
            for submission_comments in all_submission_comments:
                applying += submission_comments.applying()
                for_file += submission_comments.for_file

            logger.info('Saving rubric comments to "{}" file', filename)
            comma.dump(for_file, filename)

    if from_file and not apply:
        logger.info('Found {} comments to apply', len(applying))

    elif apply and len(applying) > 0:
        logger.info('Applying {} rubric comments', len(applying))
        for comment in applying:
            codepost.comment.create(**comment)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {}', format_time(end - start))


# ===========================================================================

if __name__ == '__main__':
    main()
