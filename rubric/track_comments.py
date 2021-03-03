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
import time

from shared import *

# ===========================================================================

# report file template
"""
REPORT.txt
Last updated 2021/02/23

SUMMARY
Hello: submitted, graded, viewed
Loops: submitted, graded, not viewed
NBody: submitted, not graded, not viewed

COMMENTS
Hello
    comment1
    comment2
Loops
    comment1
    comment3
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


def remove_duplicates(lst) -> list:
    """Remove duplicates from a list of strings while preserving order.

    Args:
        lst (list): The list with possible duplicates.

    Returns:
        list: The elements in the same order with duplicates removed.
    """

    return list(dict.fromkeys(lst).keys())


# ===========================================================================


def get_rubric_comments(assignment) -> dict:
    """Gets all the rubric comments for an assignment.

    Args:
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The comments in the format:
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

def get_student_assignment_comments(a_name, assignment) -> dict:
    """Gets student rubric comment usage on an assignment.

    Args:
        a_name (str): The assignment name.
        assignment (codepost.models.assignments.Assignments): The assignment.

    Returns:
        dict: The data in the format:
            { student: (assignment_summary, [comments]) }
    """

    logger.debug('Getting rubric comment usage for "{}" assignment', assignment.name)

    data = dict()

    submissions = assignment.list_submissions()
    if len(submissions) == 0:
        return data

    comments = get_rubric_comments(assignment)

    for submission in submissions:

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

                comment = comments[c.rubricComment]

                comment_str = ''
                if comment[0] == 0:
                    # no tier; add blank
                    comment_str += ' ' * 3
                else:
                    comment_str += f'T{comment[0]} '
                comment_str += comment[1]

                submission_comments.append(comment_str)

        for student in submission.students:
            # each student should only appear once in each assignment,
            # so this shouldn't be overriding any students
            data[student] = (assignment_summary, submission_comments)

    return data


def get_student_comments(course, stop_assignment_name) -> dict:
    """Gets student rubric comment usage on all assignments.

    Args:
        course (codepost.models.courses.Courses): The course.
        stop_assignment_name (str): The name of the assignment to stop at (does not parse this assignment).

    Returns:
        dict: The data in the format:
            { student: ( [summaries], { comment: [assignments] }, { assignment_name: [comments] } ) }
    """

    logger.info('Getting student rubric comment usage')

    data = dict()

    # get all students in this course
    all_students = set()
    for student in codepost.roster.retrieve(course.id).students:
        data[student] = (list(), dict(), dict())
        all_students.add(student)

    for i, assignment in enumerate(sorted(course.assignments, key=lambda a: a.sortKey)):

        a_name = assignment.name

        if a_name == stop_assignment_name:
            break

        a_name = f'{i} {a_name}'

        # get data for this assignment
        this_assignment = get_student_assignment_comments(a_name, assignment)

        # save data
        students_in_assignment = set(this_assignment.keys())
        students_not_here = all_students - students_in_assignment

        for student, (assignment_summary, comments) in this_assignment.items():

            data[student][0].append(assignment_summary)

            # by comment
            for comment in comments:
                if comment not in data[student][1]:
                    data[student][1][comment] = list()
                data[student][1][comment].append(a_name)

            # by assignment
            # each student should only appear once in each assignment,
            # so a student shouldn't have this assignment yet
            data[student][2][a_name] = comments

        for student in students_not_here:
            data[student][0].append(summary(a_name))
            # for by assignment
            data[student][2][a_name] = list()

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
    pass


def get_grader_comments(by='assignment') -> dict:
    """Gets grader rubric comment usage on all assignments.

    Args:
        by (str): The format to return the data.
            assignment: { grader: { assignment_name: [comments] } }
            comment: { grader: { comment: [assignments] } }

    Raises:
        ValueError: If by does not receive a proper argument.

    Returns:
        dict: The data in the specified format.
    """
    pass


# ===========================================================================

def create_reports(data) -> tuple[dict[str, int], dict[str, str]]:
    """Creates the report files for each student.

    Args:
        data (dict): The data in the format:
            { student: ( [summaries], { comment: [assignments] }, { assignment_name: [comments] } ) }

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

    for i, (student, (summaries, by_comment, by_assignment)) in enumerate(data.items()):
        ids[student] = (i + 1)

        report_str = line + f'\n{REPORT_FILENAME}\nLast updated: {TODAY}\nReport ID: {i + 1}\n'

        # summary
        report_str += line + '\nSUMMARY\n' + '\n'.join(summaries) + '\n'

        # by comment
        report_str += line + '\nBY COMMENT\n'
        for comment, assignments in by_comment.items():
            report_str += comment + '\n'
            for a_name in remove_duplicates(assignments):
                report_str += (' ' * 4) + a_name + '\n'

        # by assignment
        report_str += line + '\nBY ASSIGNMENT\n'
        for a_name, comments in by_assignment.items():
            report_str += a_name + '\n'
            for comment in comments:
                report_str += (' ' * 4) + comment + '\n'

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

    logger.info(f'Getting "{assignment_name}" assignment')
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

    logger.info('Total time: {:.2f} sec', end - start)


# ===========================================================================

if __name__ == '__main__':
    main()
