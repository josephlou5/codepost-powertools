"""
track_comments.py
Track rubric comment usage for students and graders and creates reports.

GitHub repo:
https://github.com/josephlou5/codepost-rubric-import-export

codePost API
https://docs.codepost.io/reference
https://docs.codepost.io/docs
"""

# ===========================================================================

import os
import datetime
import click
from loguru import logger
import codepost
import codepost.errors
import time

from shared import *

# ===========================================================================

TESTING = False
if TESTING:
    with open('report_whitelist.txt', 'r') as whitelist_file:
        # remove blank lines
        whitelist = set(whitelist_file.read().split('\n')) - {''}

# ===========================================================================

# report file template
"""
-------------------------
REPORT.txt

Last updated 2021/02/23
Report ID: XXX

-------------------------
SUMMARY

0-Hello: submitted, graded, viewed
1-Loops: submitted, graded, not viewed
2-NBody: submitted, not graded, not viewed

-------------------------
BY ASSIGNMENT

0-Hello
    (+1) T2 comment1
    (-1) T1 comment2

1-Loops
    (  ) T1 comment1 *
    (+1)    comment3

-------------------------
BY COMMENT

comment1
    (+1) 0-Hello
    (  ) 1-Loops
comment2
    0-Hello
comment3
    1-Loops
"""

REPORTS_FOLDER = 'reports'

REPORT_FILENAME = 'REPORT.txt'
REPORT_EXT = '.txt'
REPORT_IDS_FILE = '_report_ids.txt'

TODAY = datetime.date.today()


# ===========================================================================

def summary(assignment_name, submitted=False, graded=False, viewed=False) -> str:
    """Create summary string for an assignment.

    Args:
        assignment_name (str): The assignment name.
        submitted (bool): Whether the submission was submitted.
        graded (bool): Whether the submission was graded.
        viewed (bool): Whether the submission was viewed by the student.

    Returns:
        str: The summary string.
    """
    return (assignment_name + ': '
            + ('submitted' if submitted else 'not submitted') + ', '
            + ('graded' if graded else 'not graded') + ', '
            + ('viewed' if viewed else 'not viewed'))


def format_indent(feedback, tier, name) -> str:
    """Create indent line.

    Args:
        feedback (int): The feedback for the comment.
        tier (int): The tier of the comment.
        name (str): The comment or assignment name.

    Returns:
        str: A str representation of this information.
    """
    return ('(' + (f'{feedback:+2d}' if feedback != 0 else ' ' * 2) + ') ' +
            (f'T{tier}' if tier != 0 else ' ' * 2) + ' ' +
            name)


def remove_duplicates(lst) -> list[str]:
    """Removes duplicates from a list while preserving order.

    Args:
        lst (list[str]): The list of elements.

    Returns:
        list[str]: The list without duplicates.
    """
    return list(dict.fromkeys(lst).keys())


def count_before(assignments, a_name) -> int:
    """Count number of assignments before.

    Args:
        assignments (list[tuple[int, int, str]]): The assignments info.
        a_name (str): The assignment to count before.

    Returns:
        int: The number of assignments before.
    """
    return remove_duplicates([a[2] for a in assignments]).index(a_name)


# ===========================================================================


def get_rubric_comments(assignment) -> dict[int, tuple[int, str]]:
    """Gets all the rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict[int, tuple[int, str]]: The comments in the format:
                { comment_id: (tier, name) }
            Tier 0 means the comment does not belong to a tier.
    """

    comments = dict()

    for category in assignment.rubricCategories:
        for comment in category.rubricComments:
            # getting tier
            tier = 0
            c_text = comment.text
            if c_text[:3] == '\\[T' and c_text[4:6] == '\\]':
                # has tier
                try:
                    tier = int(c_text[3])
                except ValueError:
                    # not a valid number; shouldn't happen
                    pass

            # saving comment
            comments[comment.id] = (tier, comment.name)

    return comments


# ===========================================================================

def get_student_assignment_comments(a_name, assignment) -> dict[str, tuple[str, list[tuple]]]:
    """Gets student rubric comment usage on an assignment.

    Args:
        a_name (str): The assignment name.
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict[str, tuple[str, list[tuple]]]: The data in the format:
            { student: (assignment_summary, [ (feedback, tier, comment_name) ]) }
    """

    logger.debug('Getting rubric comment usage for "{}" assignment', assignment.name)

    submissions = assignment.list_submissions()
    if len(submissions) == 0:
        return dict()

    comments = get_rubric_comments(assignment)

    data = dict()

    for submission in submissions:

        # this loop is very susceptible to codepost API runtime errors, so wrap in try
        while True:

            try:

                # TESTING
                if TESTING:
                    these_students = set(submission.students)
                    inter = whitelist & these_students
                    if len(inter) == 0:
                        continue

                assignment_summary = summary(
                    a_name,
                    submitted=True,
                    graded=submission.isFinalized and assignment.isReleased,
                    viewed=submission.list_view_history()['hasViewed']
                )

                submission_comments = list()
                for f in submission.files:
                    for c in f.comments:
                        if c.rubricComment is None: continue
                        tier, name = comments[c.rubricComment]
                        feedback = c.feedback
                        comment = (feedback, tier, name)
                        submission_comments.append(comment)

                for student in submission.students:
                    # each student should only appear once in each assignment,
                    # so this shouldn't be overriding any students
                    data[student] = (assignment_summary, submission_comments)

            except codepost.errors.APIError:
                logger.warning('Got codePost API Runtime Error')
                continue

            break

    return data


def get_student_comments(course, stop_assignment_name) -> dict[str, tuple[list, dict, dict]]:
    """Gets student rubric comment usage on all assignments.

    Args:
        course (codepost.models.courses.Courses): The course.
        stop_assignment_name (str): The name of the assignment to stop at (does not parse this assignment).

    Returns:
        dict[str, tuple[list, dict, dict]]: The data in the format:
            { student: ( [summaries], { assignment_name: [comments] }, { comment: [assignments] } ) }
    """

    logger.info('Getting student rubric comment usage')

    data = dict()

    # get all students in this course
    all_students = set()
    for student in codepost.roster.retrieve(course.id).students:
        # TESTING
        if TESTING:
            if student not in whitelist: continue
        data[student] = (list(), dict(), dict())
        all_students.add(student)

    for i, assignment in enumerate(sorted(course.assignments, key=lambda a: a.sortKey)):

        a_name = assignment.name

        if a_name == stop_assignment_name:
            break

        a_name = f'{i}-{a_name}'

        # get data for this assignment
        this_assignment = get_student_assignment_comments(a_name, assignment)

        # save data
        students_in_assignment = set(this_assignment.keys())
        students_not_here = all_students - students_in_assignment

        for student, (assignment_summary, comments) in this_assignment.items():

            # TESTING
            if TESTING:
                if student not in whitelist: continue

            data[student][0].append(assignment_summary)

            # by assignment
            # each student should only appear once in each assignment,
            # so a student shouldn't have this assignment yet
            data[student][1][a_name] = comments

            # by comment
            for feedback, tier, comment in comments:
                if comment not in data[student][2]:
                    data[student][2][comment] = list()
                a_info = (feedback, tier, a_name)
                data[student][2][comment].append(a_info)

        for student in students_not_here:
            data[student][0].append(summary(a_name))
            # for by assignment
            data[student][1][a_name] = list()

    return data


# ===========================================================================

# TODO: get grader rubric comment usage as well

def get_grader_assignment_comments(assignment) -> dict:
    """Gets grader rubric comment usage on an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The data in the format:
            { grader: [comments] }
            { grader: { student: [comments] }
    """
    assignment.list_submissions()
    return dict()


def get_grader_comments() -> dict:
    """Gets grader rubric comment usage on all assignments.

    Returns:
        dict: The data in the specified format.
    """
    pass


# ===========================================================================

def create_reports(data) -> tuple[dict[str, int], dict[str, str]]:
    """Creates the report files for each student.

    Args:
        data (dict): The data in the format:
            { student: ( [summaries], { assignment_name: [comments] }, { comment: [assignments] } ) }

    Returns:
        tuple[dict[str, int], dict[str, str]]: The student report ids in the format:
                { student: id }
            and the report strings in the format:
                { student: report_str }
    """

    logger.info('Creating report files for each student')

    ids = dict()
    reports = dict()

    line = '-' * 50

    for i, (student, (summaries, by_assignment, by_comment)) in enumerate(data.items()):
        ids[student] = (i + 1)

        report_str = line + f'\n{REPORT_FILENAME}\n\nLast updated: {TODAY}\nReport ID: {i + 1}\n\n'

        # summary
        report_str += line + '\nSUMMARY\n\n' + '\n'.join(summaries) + '\n\n'

        # by assignment
        report_str += line + '\nBY ASSIGNMENT\n\n'
        for a_name, comments in by_assignment.items():
            report_str += a_name + '\n'
            for comment in comments:
                c_name = comment[2]
                num_stars = count_before(by_comment[c_name], a_name)
                report_str += (' ' * 4) + format_indent(*comment)
                if num_stars > 0:
                    report_str += ' ' + ('*' * num_stars)
                report_str += '\n'
            report_str += '\n'

        # by comment
        report_str += line + '\nBY COMMENT\n\n'
        for comment, assignments in sorted(by_comment.items()):
            report_str += comment + '\n'
            strs = [format_indent(*info) for info in assignments]
            for a_str in remove_duplicates(strs):
                report_str += (' ' * 4) + a_str + '\n'

        reports[student] = report_str

    return ids, reports


# ===========================================================================

def validate_dir(directory) -> str:
    """Validates a directory, and creates it if it does not exist.

    Args:
        directory (str): The directory to validate.

    Returns:
        str: The directory.
    """

    if not os.path.exists(directory):
        os.mkdir(directory)
    return directory


# ===========================================================================

def get_report_files(course, assignment_name) -> dict[str, str]:
    """Gets the reports from files.

    Args:
        course (codepost.models.courses.Courses): The course.
        assignment_name (str): The name of the assignment.

    Returns:
        dict[str, str]: The student report strings in the format:
            { student: report_str }
    """

    logger.info('Getting reports from files')

    reports = dict()

    course_info = f'{course.name} {course.period}'
    assignment_folder = os.path.join(REPORTS_FOLDER, course_info, assignment_name)

    # checking if reports exist
    if not os.path.exists(assignment_folder):
        logger.warning('Report files do not exist')
        return reports

    # reading reports
    for file in os.listdir(assignment_folder):
        if not file.endswith('@princeton.edu.txt'):
            continue
        # take off .txt extension
        student = file[:-4]
        with open(os.path.join(assignment_folder, file), 'r') as f:
            reports[student] = f.read()

    logger.debug('Got {} report files', len(reports))

    # check missing
    students = set(reports.keys())
    all_students = set(codepost.roster.retrieve(course.id).students)
    missing = all_students - students
    if len(missing) > 0:
        logger.warning('Missing {} report files:', len(missing))
        for student in sorted(missing):
            logger.warning('  {}', student)

    return reports


# ===========================================================================

def save_ids(course, assignment_name, ids):
    """Saves the report ids to a file.

    Args:
        course (codepost.models.courses.Courses): The course.
        assignment_name (str): The assignment name.
        ids (dict[str, int]): The reports in the format:
            { student: id }
    """

    logger.info('Saving report ids to "{}"', REPORT_IDS_FILE)

    course_info = f'{course.name} {course.period}'

    # get paths
    validate_dir(REPORTS_FOLDER)
    course_folder = validate_dir(os.path.join(REPORTS_FOLDER, course_info))
    assignment_folder = validate_dir(os.path.join(course_folder, assignment_name))

    filepath = os.path.join(assignment_folder, REPORT_IDS_FILE)

    with open(filepath, 'w') as f:
        f.write(course_info + '\n')
        f.write(assignment_name + '\n')
        for student, i in ids.items():
            f.write(f'{i},{student}\n')


def save_reports(course, assignment_name, reports):
    """Saves the reports as files.

    Args:
        course (codepost.models.courses.Courses): The course.
        assignment_name (str): The assignment name.
        reports (dict[str, str]): The reports in the format:
            { student: report_str }
    """

    logger.info('Saving reports as files')

    course_info = f'{course.name} {course.period}'

    # get paths
    validate_dir(REPORTS_FOLDER)
    course_folder = validate_dir(os.path.join(REPORTS_FOLDER, course_info))
    assignment_folder = validate_dir(os.path.join(course_folder, assignment_name))

    # saving reports
    for student, report_str in reports.items():
        student_file = os.path.join(assignment_folder, f'{student}.txt')
        with open(student_file, 'w') as f:
            f.write(report_str)


# ===========================================================================

def apply_reports(assignment, reports):
    """Applies the report files to each student's submission.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.
        reports (dict[str, str]): The reports in the format:
            { student: report_str }
    """

    logger.info('Applying reports to assignment "{}"', assignment.name)

    for i, submission in enumerate(assignment.list_submissions()):

        if submission.isFinalized: continue

        report_str = '\n'.join(reports[student] for student in submission.students if student in reports)

        # no reports exist for the students (shouldn't happen)
        if report_str == '':
            logger.warning('Submission {}: Student(s) had no reports', submission.id)
            continue

        # replace file if exists
        for file in submission.files:
            if file.name == REPORT_FILENAME:
                codepost.file.update(
                    id=file.id,
                    code=report_str,
                )
                break
        else:
            # create new file
            codepost.file.create(
                name=REPORT_FILENAME,
                code=report_str,
                extension=REPORT_EXT,
                submission=submission.id,
            )

        # DEBUG
        # logger.debug('Submission {}: Created "{}"', submission.id, REPORT_FILENAME)

        if i % 100 == 99:
            logger.debug('Done with submission {}', i + 1)


# ===========================================================================

@click.command()
@click.argument('course_period', type=str, required=True)
@click.argument('assignment_name', type=str, required=True)
@click.option('-f', '--from-file', is_flag=True, default=False, flag_value=True,
              help='Whether to read the reports from files. Default is False.')
@click.option('-s', '--save-files', is_flag=True, default=False, flag_value=True,
              help='Whether to save the reports as files. Default is False.')
@click.option('-a', '--apply', is_flag=True, default=False, flag_value=True,
              help='Whether to apply the reports to the submissions. Default is False.')
@click.option('-t', '--testing', is_flag=True, default=False, flag_value=True,
              help='Whether to run as a test. Default is False.')
def main(course_period, assignment_name, from_file, save_files, apply, testing):
    """
    Track rubric comment usage for students and graders and creates reports.

    \b
    Args:
        course_period (str): The period of the COS126 course.
        assignment_name (str): The name of the assignment to apply the reports to. \f
        from_file (bool): Whether to read the reports from files.
            Default is False.
        save_files (bool): Whether to save the reports as files.
            Default is False.
        apply (bool): Whether to apply the reports to the submissions.
            Default is False.
        testing (bool): Whether to run as a test.
            Default is False.
    """

    if not (from_file or save_files or apply):
        logger.warning('Getting reports without saving or applying.')

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

    reports = dict()

    if from_file:
        reports = get_report_files(course, assignment_name)

    if len(reports) == 0:
        # either from_file didn't succeed or not from_file

        data = get_student_comments(course, assignment_name)
        ids, reports = create_reports(data)

        # no need to save if read from file; it's the same thing
        save_ids(course, assignment_name, ids)
        if save_files:
            save_reports(course, assignment_name, reports)

    if apply:
        apply_reports(assignment, reports)

    logger.info('Done')

    end = time.time()

    logger.info('Total time: {}', format_time(end - start))


# ===========================================================================

if __name__ == '__main__':
    main()
