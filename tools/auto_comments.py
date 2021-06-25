"""
auto_comments.py
Adds automatic rubric comments to submissions.

Rubric comments:
- all MISSING file comments
- no-comments
- no-comments-in-file
- no-space-after-slash
- line-character-limit
- stringbuilder
"""

# ===========================================================================

import os
from typing import (
    Any,
    Tuple, List, Dict,
)

import codepost
import comma
from loguru import logger

from shared import *
from shared_codepost import *
from shared_output import *

# TODO: parse TESTS.txt to automate checkstyle comments and others

# ===========================================================================

# globals

COMMENT_AUTHOR = 'jdlou+autocommenter@princeton.edu'

COMMENTS_FILE = 'added_auto_comments.csv'

# ===========================================================================

# constants
RUBRIC_COMMENTS = (
    'no-comments',
    'no-comments-in-file',
    'no-space-after-slash',
    'line-character-limit',
)
STRINGBUILDER_COMMENT = 'stringbuilder'
LINE_CHARACTER_LIMIT = 87

# ===========================================================================

# globals

# ids of the rubric comments
# name -> id
NAME_TO_ID: Dict[str, int] = dict()

# names of the rubric comments
# id -> name
ID_TO_NAME: Dict[int, str] = dict()

# ids of the missing file rubric comments
# filename -> id
MISSING: Dict[str, int] = dict()


# ===========================================================================

class AutoComment:
    """AutoComment class: Represents a comment being automatically added.

    Constructors:
        AutoComment(s_id, name, file_id, file_name, text='',
                    line=None, start_line=None, end_line=None,
                    start_char=None, end_char=None)
            Initializes an AutoComment.

        AutoComment.from_codepost(file, comment):
            Initializes an AutoComment from a codePost comment.

    Properties:
        name (str): The rubric comment name.
        file_name (str): The name of the file where the comment should be applied.
        line_num (int): The start line number of the comment.

    Static Methods:
        from_csv(comment_dict)
            Converts a file dict into a comment creation kwargs dict.

    Methods:
        add_line_instance(line_num)
            Adds an instance of this rubric comment in another line.

        add_file_instance(file_name)
            Adds an instance of this rubric comment in another file.

        get_final_rep(lines=True, text=None)
            Returns the kwargs dict and csv representation of this comment.
    """

    def __init__(self,
                 s_id: int,
                 name: str,
                 file_id: int,
                 file_name: str,
                 text: str = '',
                 line: int = None,
                 start_line: int = None,
                 end_line: int = None,
                 start_char: int = None,
                 end_char: int = None,
                 missing: bool = False
                 ):
        """Initializes an AutoComment.

        Args:
            s_id (int): The submission id.
            name (str): The rubric comment name or the missing file name.
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
            missing (bool): Whether this comment is for a missing file.
                Default is False.

        Raises:
            ValueError: If `name` is not one of the auto comments.
        """

        self._s_id = s_id

        self._comment_name = name
        if missing:
            # `name` will be the filename
            self._rubric_comment = MISSING.get(name, None)
            if self._rubric_comment is not None:
                self._comment_name = ID_TO_NAME[self._rubric_comment]
        else:
            self._rubric_comment = NAME_TO_ID.get(name, None)
        if self._rubric_comment is None:
            raise ValueError(f'rubric comment "{name}" is not one of the auto comments')

        self._file_id = file_id
        self._file_name = file_name

        self._text = text
        self._extra_instances = list()
        self._extra_files = list()

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

        self._stringbuilder = name == STRINGBUILDER_COMMENT

    @classmethod
    def from_codepost(cls, file: File, comment: Comment) -> 'AutoComment':
        """Initializes an AutoComment from a codePost comment.
        Not used in this program.

        Args:
            file (File): The file.
            comment (Comment): The comment.
        """

        s_id = file.submission
        name = comment.name
        file_id = file.id
        file_name = file.name
        text = comment.text
        start_line = comment.startLine
        end_line = comment.endLine
        start_char = comment.startChar
        end_char = comment.endChar

        return cls(s_id, name, file_id, file_name, text=text,
                   start_line=start_line, end_line=end_line,
                   start_char=start_char, end_char=end_char)

    # ==================================================

    @property
    def name(self) -> str:
        return self._comment_name

    @property
    def file_name(self) -> str:
        return self._file_name

    @property
    def line_num(self) -> int:
        return self._start_line

    # ==================================================

    @staticmethod
    def from_csv(comment_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Converts a file dict into a comment creation kwargs dict.

        Args:
            comment_dict (Dict[str, Any]): The comment in its csv format.

        Raises:
            KeyError: If `comment_dict` doesn't contain the proper keys.
            ValueError: If appropriate values of `comment_dict` cannot be converted to `int`.

        Returns:
            Dict[str, Any]: The keyword arguments for creating a comment.
        """
        return {
            'text': comment_dict['text'],
            'startChar': int(comment_dict['start_char']),
            'endChar': int(comment_dict['end_char']),
            'startLine': int(comment_dict['start_line']),
            'endLine': int(comment_dict['end_line']),
            'file': int(comment_dict['file_id']),
            'rubricComment': int(comment_dict['comment_id']),
            'author': comment_dict['author'],
        }

    # ==================================================

    def add_line_instance(self, line_num: int):
        """Adds an instance of this rubric comment in another line.

        Args:
            line_num (int): The line number (0-indexed) of the repeat rubric comment.
        """
        self._extra_instances.append(line_num + 1)

    def add_file_instance(self, file_name: str):
        """Adds an instance of this rubric comment in another file.

        Args:
            file_name (str): The name of the file of the repeat rubric comment.
        """
        # add backticks to filename
        self._extra_files.append('`' + file_name + '`')

    # ==================================================

    def _create_text(self, lines: bool = True) -> str:
        """Create the text of the comment.

        Args:
            lines (bool): Whether to use the extra line instances.
                If False, uses the extra file instances.
                Default is True.

        Returns:
            str: The text.
        """

        extra = 'line' if lines else 'file'
        extras = self._extra_instances if lines else self._extra_files

        text = self._text
        num_extra = len(extras)
        if num_extra > 0:
            if text != '':
                text += '\n\n'
            if num_extra == 1:
                text += f'Also see {extra} {extras[0]}.'
            elif num_extra == 2:
                text += f'Also see {extra}s {extras[0]} and {extras[1]}.'
            else:
                text += f'Also see {extra}s '
                # text += ''.join(f'{line}, ' for line in extras[:-1])
                for line in extras[:-1]:
                    text += str(line) + ', '
                text += f'and {extras[-1]}.'

        return text

    def get_final_rep(self,
                      lines: bool = True,
                      author: str = COMMENT_AUTHOR,
                      text: str = None
                      ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Gets the final representations of this AutoComment.

        Args:
            lines (bool): Whether to use the extra line instances.
                If False, uses the extra file instances.
                Default is True.
            author (str): The comment author.
                Default is `COMMENT_AUTHOR`.
            text (str): The text for this comment. Overrides the generated text.
                Default is None.

        Returns:
            Tuple[Dict[str, Any], Dict[str, Any]]: The kwargs dict and the csv representation.
        """

        as_csv = {
            'submission_id': self._s_id,
            'file_name': self._file_name,
            'file_id': self._file_id,
            'author': author,
            'comment': self._comment_name,
            'comment_id': self._rubric_comment,
            'start_line': self._start_line,
            'end_line': self._end_line,
            'start_char': self._start_char,
            'end_char': self._end_char,
            'text': text or self._create_text(lines),
        }
        as_dict = self.from_csv(as_csv)

        return as_dict, as_csv


# ===========================================================================

class SubmissionComments:
    """SubmissionComments class: Represents the comments for a submission.

    Constructors:
        SubmissionComments(submission, comments=None)
            Initializes a SubmissionComments object.

    Properties:
        num_comments (int): The number of comments to apply to this submission.

    Methods:
        force_comment(*args, **kwargs)
            Forces the addition of a comment to this submission.

        add_comment(*args, **kwargs)
            Adds a comment to this submission.

        add_no_comments(*args, **kwargs)
            Adds a "no comments" comment to this submission.

        add_stringbuilder_comment(*args, **kwargs)
            Adds a stringbuilder comment to this submission.

        add_stringbuilder_used(file_name):
            Adds a file where `StringBuilder` was used.

        get_final_comments()
            Returns the comments to apply and for saving in a file.
    """

    def __init__(self, submission: Submission, comments: List[Comment] = None):
        """Initializes a SubmissionComments object.

        Args:
            submission (Submission): The submission.
            comments (List[Comment]): The comments in this submission.
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
        self._no_comments = dict()

        self._stringbuilder_comment = None
        # the files where `StringBuilder` should've been used
        self._stringbuilder_files = list()
        # the files where `StringBuilder` was used
        self._stringbuilder_used = list()

    # ==================================================

    @property
    def num_comments(self) -> int:
        return (len(self._comments)
                + (1 if len(self._no_comments) > 0 else 0)
                + (1 if self._stringbuilder_comment is not None else 0))

    # ==================================================

    def force_comment(self, *args, **kwargs):
        """Forces the addition of a comment to this submission.

        Args:
            The args and kwargs to create an AutoComment.
        """

        try:
            comment = AutoComment(self._s_id, *args, **kwargs)
        except ValueError:
            return

        key = 'force'
        if key in self._comments:
            i = 1
            while f'{key}{i}' in self._comments:
                i += 1
            key += str(i)

        self._comments[key] = comment

    def add_comment(self, *args, **kwargs):
        """Adds a comment to this submission.

        Args:
            The args and kwargs to create an AutoComment.
        """

        try:
            comment = AutoComment(self._s_id, *args, **kwargs)
        except ValueError:
            return

        name = comment.name

        # don't add repeat comments
        if name in self._existing_comments:
            return

        old_comment = self._comments.get(name, None)

        # new comment
        if old_comment is None:
            self._comments[name] = comment
            return

        # update old comment with new instances if in same file and not same line
        if old_comment.file_name == comment.file_name and old_comment.line_num != comment.line_num:
            old_comment.add_line_instance(comment.line_num)

    def add_no_comments(self, *args, **kwargs):
        """Adds a "no comments" comment to this submission.

        Args:
            The args and kwargs to create an AutoComment.
        """

        try:
            comment = AutoComment(self._s_id, *args, **kwargs)
        except ValueError:
            return

        name = comment.name

        # don't add repeat comments
        if name in self._existing_comments:
            return

        old_comment = self._no_comments.get(name, None)

        # new comment
        if old_comment is None:
            self._no_comments[name] = comment
            return

        old_comment.add_file_instance(comment.file_name)

    def add_stringbuilder_comment(self, *args, **kwargs):
        """Adds a stringbuilder comment to this submission.

        Args:
            The args and kwargs to create an AutoComment.
        """

        try:
            comment = AutoComment(self._s_id, *args, **kwargs)
        except ValueError:
            return

        # don't add repeat comments
        if STRINGBUILDER_COMMENT in self._existing_comments:
            return

        if self._stringbuilder_comment is None:
            self._stringbuilder_comment = comment
            return

        self._stringbuilder_files.append(comment.file_name)

    def add_stringbuilder_used(self, file_name: str):
        """Adds a file where `StringBuilder` was used.

        Args:
            file_name (str): The file name.
        """
        self._stringbuilder_used.append(file_name)

    # ==================================================

    def _get_no_comments(self) -> AutoComment:
        """Returns the "no comments" comment."""

        comment = self._no_comments.get('no-comments', None)
        if comment is not None:
            return comment
        return self._no_comments.get('no-comments-in-file', None)

    def get_final_comments(self,
                           author: str = COMMENT_AUTHOR,
                           stringbuilder: bool = False
                           ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Returns the comments to apply and for saving in a file.

        Args:
            author (str): The comment author.
                Default is `COMMENT_AUTHOR`.
            stringbuilder (bool): Whether to apply the stringbuilder comment.
                Default is False.

        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: The comments to apply in kwargs format
                and the comments for saving in a file.
        """

        applying = list()
        for_file = list()

        for comment in self._comments.values():
            as_dict, as_csv = comment.get_final_rep(author=author)
            applying.append(as_dict)
            for_file.append(as_csv)

        no_comment = self._get_no_comments()
        if no_comment is not None:
            as_dict, as_csv = no_comment.get_final_rep(author=author)
            applying.append(as_dict)
            for_file.append(as_csv)

        if stringbuilder and self._stringbuilder_comment is not None:
            text = list()
            if len(self._stringbuilder_files) == 0:
                pass
            elif len(self._stringbuilder_files) == 1:
                text.append(f'Also see the `toString()` method in `{self._stringbuilder_files[0]}`.')
            elif len(self._stringbuilder_files) == 2:
                text.append('Also see the `toString()` methods in '
                            f'`{self._stringbuilder_files[0]}` and `{self._stringbuilder_files[1]}`.')
            else:
                text.append('Also see the `toString()` methods in ' +
                            ', '.join(f'`{file}`' for file in self._stringbuilder_files[:-1]) +
                            f', and `{self._stringbuilder_files[-1]}`.')
            if len(self._stringbuilder_used) == 0:
                pass
            elif len(self._stringbuilder_used) == 1:
                text.append(f'You used `StringBuilder` in `{self._stringbuilder_used[0]}`.')
            elif len(self._stringbuilder_used) == 2:
                text.append('You used `StringBuilder` in '
                            f'`{self._stringbuilder_used[0]}` and `{self._stringbuilder_used[1]}`.')
            else:
                text.append('You used `StringBuilder` in ' +
                            ', '.join(f'`{file}`' for file in self._stringbuilder_used[:-1]) +
                            f', and `{self._stringbuilder_used[-1]}`.')
            as_dict, as_csv = self._stringbuilder_comment.get_final_rep(author=author, text=' '.join(text))
            applying.append(as_dict)
            for_file.append(as_csv)

        return applying, for_file


# ===========================================================================

def get_rubric_comment_ids(assignment: Assignment, stringbuilder: bool = False, log: bool = False):
    """Gets the ids for the rubric comments in COMMENTS.

    Args:
        assignment (Assignment): The assignment.
        stringbuilder (bool): Whether to include the stringbuilder comment.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.
    """
    global NAME_TO_ID
    global ID_TO_NAME

    if log: logger.info('Getting ids for rubric comments')

    searching = list(RUBRIC_COMMENTS)
    if stringbuilder:
        searching.append(STRINGBUILDER_COMMENT)

    for category in assignment.rubricCategories:
        for comment in category.rubricComments:
            c_name = comment.name
            try:
                searching.remove(c_name)
            except ValueError:
                # not in searching
                continue
            c_id = comment.id
            NAME_TO_ID[c_name] = c_id
            ID_TO_NAME[c_id] = c_name
            if log: logger.debug('Found rubric comment for "{}"', c_name)

    if log and len(searching) > 0:
        logger.warning('Could not find {} rubric comments:', len(searching))
        for name in searching:
            logger.warning('  {}', name)

    if log: logger.info('Got ids for rubric comments')


def get_missing_comment_ids(assignment: Assignment, log: bool = False):
    """Gets the ids for the rubric comments in the "MISSING" category, if it exists.

    Args:
        assignment (Assignment): The assignment.
        log (bool): Whether to show log messages.
            Default is False.
    """
    global MISSING
    global ID_TO_NAME

    if log: logger.info('Getting ids for "MISSING" rubric comments')

    missing_category = next((c for c in assignment.rubricCategories if c.name == 'MISSING'), None)

    # there is no MISSING rubric category
    if missing_category is None:
        if log: logger.warning('Could not find "MISSING" rubric category')
        return

    for comment in missing_category.rubricComments:
        # assumes the comment text follows the format "missing `filename.java`"
        filename = comment.text.split('`')[1]
        MISSING[filename] = comment.id
        ID_TO_NAME[comment.id] = comment.name
        if log: logger.debug('Found missing rubric comment for "{}"', filename)

    if log: logger.info('Got ids for "MISSING" rubric comments')


# ===========================================================================

def parse_file(submission_comments: SubmissionComments, file: File) -> int:
    """Parses a file for instances of rubric comments.

    Args:
        submission_comments (SubmissionComments): The SubmissionComments object for this submission.
        file (File): The file.

    Returns:
        int: The number of Java comments in the file.
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

    in_toString = False
    stringbuilder_found = False
    # the number of brackets in the `toString()` method to be able to tell when it ends
    toString_brackets = 0
    # the position of toString(): (line, start char, end char)
    toString_pos: Dict[str, int] = dict()

    # number of Java comments in this file
    num_comments = 0

    for line_num, line in enumerate(file.code.split('\n')):

        if len(line) > LINE_CHARACTER_LIMIT:
            submission_comments.add_comment(
                'line-character-limit', f_id, f_name,
                line=line_num, start_char=0, end_char=2
            )

        if not in_toString and 'public String toString()' in line:
            in_toString = True
            start_char = line.find('toString()')
            toString_pos = {
                'line': line_num,
                'start_char': start_char,
                'end_char': start_char + len('toString()')
            }
        elif in_toString and not stringbuilder_found:
            if 'StringBuilder' in line:
                stringbuilder_found = True

        if state in ('starting multi comment', 'in multi comment', 'first asterisk'):
            state = 'in multi comment'
        else:
            state = 'normal'

        for char_num, c in enumerate(line):

            if in_toString:
                if c == '{':
                    toString_brackets += 1
                elif c == '}':
                    toString_brackets -= 1
                    if toString_brackets == 0:
                        in_toString = False

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

                if c.isalpha():
                    # in a comment, but there's no space
                    submission_comments.add_comment(
                        'no-space-after-slash', f_id, f_name,
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

                if c.isalpha():
                    # in a multi line comment, but there's no space
                    # /** passes, and doesn't check after that
                    submission_comments.add_comment(
                        'no-space-after-slash', f_id, f_name,
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

    if num_comments == 0:
        submission_comments.add_no_comments('no-comments-in-file', f_id, f_name)

    if stringbuilder_found:
        submission_comments.add_stringbuilder_used(f_name)
    else:
        submission_comments.add_stringbuilder_comment(
            STRINGBUILDER_COMMENT, f_id, f_name, **toString_pos
        )

    return num_comments


# ===========================================================================

def create_submission_comments(submission: Submission) -> SubmissionComments:
    """Creates automatically applied rubric comments for a submission.

    Args:
        submission (Submission): The submission.

    Returns:
        SubmissionComments: The SubmissionComments object for this submission.
    """

    files: Dict[str, File] = dict()
    comments: List[Comment] = list()
    for file in submission.files:
        files[file.name] = file
        comments += file.comments

    submission_comments = SubmissionComments(submission, comments)

    first_file = files[min(files.keys(), key=lambda n: n.lower())]

    # check for missing files
    missing_files = set(MISSING.keys()) - set(files.keys())
    for filename in missing_files:
        submission_comments.add_comment(filename, first_file.id, first_file.name, missing=True)

    # parsing files
    total_num_comments = 0
    for name, file in files.items():
        if not name.endswith('.java'): continue
        total_num_comments += parse_file(submission_comments, file)

    # no comments in any file
    if total_num_comments == 0:
        submission_comments.add_no_comments('no-comments', first_file.id, first_file.name)

    # parse readme for long lines
    readme = files.get('readme.txt', None)
    if readme is not None:
        for line_num, line in enumerate(readme.code.split('\n')):
            if len(line) > LINE_CHARACTER_LIMIT:
                submission_comments.force_comment(
                    'line-character-limit', readme.id, readme.name,
                    text='Be sure to follow the line character limit, even in the readme!',
                    line=line_num, start_char=0, end_char=2
                )
                break

    return submission_comments


# ===========================================================================

def create_comments(assignment: Assignment,
                    log: bool = False,
                    progress_interval: int = 100
                    ) -> List[SubmissionComments]:
    """Creates automatically applied rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.
        log (bool): Whether to show log messages.
            Default is False.
        progress_interval (int): The interval at which to show submission counts.
            If less than 0, nothing is shown.
            Default is 100.

    Returns:
        List[SubmissionComments]: The SubmissionComment objects for each submission.
    """

    if log: logger.info('Creating automatic rubric comments')

    all_comments = list()

    submissions = assignment.list_submissions()
    if log: logger.debug('Iterating through {} total submissions', len(submissions))
    for i, submission in enumerate(submissions):

        if submission.isFinalized: continue

        submission_comments = create_submission_comments(submission)

        if submission_comments.num_comments > 0:
            all_comments.append(submission_comments)

        if log and progress_interval > 0 and (i + 1) % progress_interval == 0:
            logger.debug('Done with submission {}', i + 1)

    if log: logger.info('Created automatic rubric comments')

    return all_comments


# ===========================================================================

def read_comments_file(filename: str, log: bool = False) -> List[Dict[str, Any]]:
    """Read comments from a file and return the kwargs dict to create them.

    Args:
        filename (str): The name of the file.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Dict[str, Any]]: The comments to apply in kwargs format.
    """

    if log: logger.info('Reading comments from file')

    if not os.path.exists(filename):
        if log: logger.warning('File "{}" not found', filename)
        return list()
    data = comma.load(filename, force_header=True)
    if len(data) == 0:
        if log: logger.info('No comments found in file "{}"', filename)
        return list()

    applying = list()
    for row in data:
        applying.append(AutoComment.from_csv(row))

    return applying


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         author: str = COMMENT_AUTHOR,
         stringbuilder: bool = False,
         from_file: bool = False,
         apply: bool = False,
         log: bool = False
         ):
    """Adds automatic rubric comments to submissions.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The assignment name.
        author (str): The comment author.
            Default is `COMMENT_AUTHOR`.
        stringbuilder (bool): Whether to apply the stringbuilder comment.
            Default is False.
        from_file (bool): Whether to read the comments from a file.
            Default is False.
        apply (bool): Whether to apply the comments.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.

    Raises:
        ValueError: If `author` is an invalid grader in the given course.
    """

    if log and from_file and not apply:
        logger.warning('Reading from file but not applying')

    success = log_in_codepost(log=log)
    if not success: return

    success, course = get_course(course_name, course_period, log=log)
    if not success: return

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return

    success = validate_grader(course, author)
    if not success: return

    filepath = get_path(file=COMMENTS_FILE, course=course, assignment=assignment)

    applying = list()

    # reading comments from file
    if from_file:
        applying = read_comments_file(filepath, log=log)

    # reading comments from codepost
    if len(applying) == 0:

        get_rubric_comment_ids(assignment, stringbuilder=stringbuilder, log=log)
        get_missing_comment_ids(assignment, log=log)

        all_submission_comments = create_comments(assignment, log=log)

        if len(all_submission_comments) > 0:
            applying = list()
            for_file = list()
            for submission_comments in all_submission_comments:
                apply_comments, file_comments = \
                    submission_comments.get_final_comments(
                        author=author,
                        stringbuilder=stringbuilder
                    )
                applying += apply_comments
                for_file += file_comments

            save_csv(for_file, filepath, description='rubric comments', log=log)

    if apply:
        if len(applying) == 0:
            if log: logger.info('No comments to apply')
        else:
            if log: logger.info('Applying {} rubric comments', len(applying))
            for comment in applying:
                codepost.comment.create(**comment)

# ===========================================================================
