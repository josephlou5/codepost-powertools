"""
reports.py
Creates rubric comment usage reports.
"""

# ===========================================================================

import datetime
import os
import time
from typing import (
    Tuple, List, Dict,
)

import codepost
import codepost.errors
from loguru import logger

from shared import *
from shared_codepost import *
from shared_output import *

# ===========================================================================


# report file template
"""
--------------------------------------------------
REPORT.txt

Last updated: 2021-01-01
Report ID: XXX

--------------------------------------------------
SUMMARY

0-Hello: submitted, graded, viewed
1-Loops: submitted, graded, not viewed
2-NBody: submitted, not graded, not viewed

--------------------------------------------------
BY ASSIGNMENT

0-Hello
    (+1) T2 comment1
    (-1) T1 comment2

1-Loops
    (  ) T1 comment1 *
    (+1)    comment3

2-NBody

--------------------------------------------------
BY COMMENT

comment1
    (+1) T2 0-Hello
    (  ) T1 1-Loops
comment2
    (-1) T1 0-Hello
comment3
    (+1)    1-Loops
"""

# constants
REPORTS_FOLDER = 'reports'
REPORT_IDS_FILE = '_report_ids.txt'

REPORT_FILENAME = 'REPORT.txt'
REPORT_EXT = '.txt'

TODAY = datetime.date.today()


# ===========================================================================

def get_report_files(course: Course,
                     assignment: Assignment,
                     log: bool = False
                     ) -> Dict[str, str]:
    """Gets the reports from files.

    Args:
        course (Course): The course.
        assignment (Assignment): The assignment.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Dict[str, str]: The student report strings in the format:
            { student: report_str }
    """

    if log: logger.info('Getting reports from files')

    reports = dict()

    folder = get_path(course=course, assignment=assignment, folder=REPORTS_FOLDER, create=False)

    # checking if reports exist
    if not os.path.exists(folder):
        if log: logger.warning('Report files do not exist')
        return reports

    # getting reports
    for file in os.listdir(folder):
        if not file.endswith('@princeton.edu.txt'):
            continue
        # take off .txt extension
        student = file[:-4]
        with open(os.path.join(folder, file), 'r') as f:
            reports[student] = f.read()

    if log: logger.debug('Got {} report files', len(reports))

    # check missing
    if log:
        students = set(reports.keys())
        all_students = set(codepost.roster.retrieve(course.id).students)
        missing = all_students - students
        if len(missing) > 0:
            logger.warning('Missing {} report files:', len(missing))
            for student in sorted(missing):
                logger.warning('  {}', student)

    return reports


# ===========================================================================

def get_assignments(course: Course,
                    stop_assignment_name: str = None,
                    exclude: List[str] = None
                    ) -> List[Tuple[int, Assignment]]:
    """Gets assignments before the given assignment.

    Args:
        course (Course): The course.
        stop_assignment_name (str): The name of the assignment to stop at (exclusive).
            Default is None (get all assignments).
        exclude (List[str]): Assignment names to exclude.
            Default is None.

    Returns:
        List[Tuple[int, Assignment]]: The assignments.
    """

    if exclude is None:
        exclude = list()

    assignments = list()

    for i, assignment in enumerate(sorted(course.assignments, key=lambda a: a.sortKey)):
        if assignment.name == stop_assignment_name: break
        if assignment.name in exclude: continue
        assignments.append((i, assignment))

    return assignments


# ===========================================================================


def get_rubric_comments(assignment: Assignment) -> Dict[int, Tuple[str, int]]:
    """Gets all the rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.

    Returns:
        Dict[int, Tuple[str, int]]: The comments in the format:
                { comment_id: (name, tier) }
            Tier 0 means the comment does not belong to a tier.
    """

    comments = dict()

    for category in assignment.rubricCategories:
        for comment in category.rubricComments:
            # get tier if has it
            match = TIER_PATTERN.match(comment.text)
            if match is None:
                tier = 0
            else:
                tier = int(match.groups()[0])

            # saving comment
            comments[comment.id] = (comment.name, tier)

    return comments


def get_assignment_comments(a_name: str,
                            assignment: Assignment,
                            log: bool = False,
                            progress_interval: int = 100
                            ) -> Dict[str, Tuple[str, List[Tuple[str, int, int]]]]:
    """Gets rubric comment usage for an assignment.

    Args:
        a_name (str): The assignment name.
        assignment (Assignment): The assignment.
        log (bool): Whether to show log messages.
            Default is False.
        progress_interval (int): The interval at which to show submission counts.
            If less than 0, nothing is shown.
            Default is 100.

    Returns:
        Dict[str, Tuple[str, List[Tuple[str, int, int]]]]: The data in the format:
            { student: (assignment_summary, [ (comment_name, tier, feedback) ]) }
    """

    if log: logger.debug('Getting rubric comment usage for "{}" assignment', assignment.name)

    submissions = assignment.list_submissions()
    if len(submissions) == 0:
        return dict()

    comments = get_rubric_comments(assignment)

    data = dict()

    for i, submission in enumerate(submissions):

        # this loop is very susceptible to codepost API runtime errors, so wrap in try
        while True:

            try:

                assignment_summary = summary(
                    a_name,
                    submitted=True,
                    graded=submission.isFinalized and assignment.isReleased,
                    viewed=submission.list_view_history()['hasViewed']
                )

                submission_comments = list()
                for file in submission.files:
                    for comment in file.comments:
                        if comment.rubricComment is None: continue
                        name, tier = comments[comment.rubricComment]
                        feedback = comment.feedback
                        submission_comments.append((name, tier, feedback))

                for student in submission.students:
                    # each student should only appear once in each assignment,
                    # so this shouldn't be overriding any students
                    data[student] = (assignment_summary, submission_comments)

                if log and progress_interval > 0 and (i + 1) % progress_interval == 0:
                    logger.debug('Done with submission {}', i + 1)

            except codepost.errors.APIError:
                if log: logger.warning('Got codePost API Runtime Error')
                time.sleep(3)
                continue

            break

    return data


# ===========================================================================


def summary(assignment_name: str,
            submitted: bool = False,
            graded: bool = False,
            viewed: bool = False
            ) -> str:
    """Creates the summary string for a submission.

    Args:
        assignment_name (str): The assignment name.
        submitted (bool): Whether the submission was submitted.
            Default is False.
        graded (bool): Whether the submission was graded.
            Default is False.
        viewed (bool): Whether the submission was viewed by the student.
            Default is False.

    Returns:
        str: The summary string.
    """
    return (assignment_name + ': '
            + ('submitted' if submitted else 'not submitted') + ', '
            + ('graded' if graded else 'not graded') + ', '
            + ('viewed' if viewed else 'not viewed'))


def get_comments(course: Course,
                 assignments: List[Tuple[int, Assignment]],
                 log: bool = False,
                 progress_interval: int = 100
                 ) -> Dict[str, Tuple[List[str], Dict, Dict]]:
    """Gets student rubric comment usage on all assignments.

    Args:
        course (Course): The course.
        assignments (List[Tuple[int, Assignment]]): The assignments.
        log (bool): Whether to show log messages.
            Default is False.
        progress_interval (int): The interval at which to show submission counts.
            If less than 0, nothing is shown.
            Default is 100.

    Returns:
        Dict[str, Tuple[List[str], Dict, Dict]]: The data in the format:
            { student: ( [summaries], { assignment_name: [comments] }, { comment: [assignments] } ) }
    """

    if log: logger.info('Getting rubric comment usage')

    # student -> ( summaries, by assignment, by comment )
    data = {
        student: (list(), dict(), dict())
        for student in codepost.roster.retrieve(course.id).students
    }
    summaries = 0
    by_assignment = 1
    by_comment = 2

    all_students = set(data.keys())

    # keep track of previous assignment names for students not in the roster
    prev_assignments = list()

    for i, assignment in assignments:

        a_name = f'{i}-{assignment.name}'

        # get comments for this assignment
        this_assignment = get_assignment_comments(a_name, assignment,
                                                  log=log, progress_interval=progress_interval)

        # save data
        students_in_assignment = set(this_assignment.keys())
        students_not_here = all_students - students_in_assignment

        for student, (assignment_summary, comments) in this_assignment.items():

            if student not in data:
                if log: logger.warning('Error: Student "{}" not in roster', student)
                data[student] = (list(), dict(), dict())
                all_students.add(student)
                # add all previous assignments to this student
                for prev_a in prev_assignments:
                    data[student][summaries].append(summary(prev_a))
                    data[student][by_assignment][prev_a] = list()

            # summary
            data[student][summaries].append(assignment_summary)

            # by assignment
            # each student should only appear once in each assignment,
            # so a student shouldn't have this assignment yet
            data[student][by_assignment][a_name] = comments

            # by comment
            for c_name, tier, feedback in comments:
                if c_name not in data[student][by_comment]:
                    data[student][by_comment][c_name] = list()
                data[student][by_comment][c_name].append((a_name, tier, feedback))

        for student in students_not_here:
            data[student][summaries].append(summary(a_name))
            data[student][by_assignment][a_name] = list()

        prev_assignments.append(a_name)

    return data


# ===========================================================================


def format_line(name: str, tier: int, feedback: int) -> str:
    """Formats the given information into a line.

    Args:
        name (str): The comment or assignment name.
        tier (int): The tier of the comment.
        feedback (int): The feedback for the comment.

    Returns:
        str: The line.
    """
    return (' ' * 4
            + '(' + (f'{feedback:+2d}' if feedback != 0 else ' ' * 2) + ') '
            + (f'T{tier}' if tier != 0 else ' ' * 2) + ' '
            + name)


def remove_duplicates(lst: List[str]) -> List[str]:
    """Removes duplicates from a list while preserving order.

    Args:
        lst (List[str]): The list.

    Returns:
        List[str]: The list without duplicates.
    """
    return list(dict.fromkeys(lst).keys())


def count_before(assignments_info: List[Tuple[str, int, int]],
                 a_name: str
                 ) -> int:
    """Count number of assignments before.

    Args:
        assignments_info (List[Tuple[str, int, int]]): The assignments info in the format:
            ( assignment_name, tier, feedback )
        a_name (str): The assignment to count before.

    Returns:
        int: The number of assignments before.
    """
    return remove_duplicates([a[0] for a in assignments_info]).index(a_name)


def create_reports(data: Dict[str, Tuple[List, Dict, Dict]],
                   log: bool = False
                   ) -> Tuple[Dict[str, int], Dict[str, str]]:
    """Creates the report files for each student.

    Args:
        data (Dict[str, Tuple[List, Dict, Dict]]): The data in the format:
            { student: ( [summaries], { assignment_name: [comments] }, { comment: [assignments] } ) }
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Tuple[Dict[str, int], Dict[str, str]]: The student report ids in the format:
                { student: id }
            and the report strings in the format:
                { student: report_str }
    """

    if log: logger.info('Creating report files for each student')

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
                c_name = comment[0]
                report_str += format_line(*comment)
                num_stars = count_before(by_comment[c_name], a_name)
                if num_stars > 0:
                    report_str += ' ' + ('*' * num_stars)
                report_str += '\n'
            report_str += '\n'

        # by comment
        report_str += line + '\nBY COMMENT\n\n'
        for comment, assignments in sorted(by_comment.items()):
            report_str += comment + '\n'
            strs = [format_line(*info) for info in assignments]
            for a_str in remove_duplicates(strs):
                report_str += a_str + '\n'

        reports[student] = report_str

    return ids, reports


# ===========================================================================

def save_ids(course: Course,
             assignment: Assignment,
             ids: Dict[str, int],
             log: bool = False
             ):
    """Saves the student report ids to a file.

    Args:
        course (Course): The course.
        assignment (Assignment): The assignment.
        ids (Dict[str, int]): The student report ids in the format:
            { student: id }
        log (bool): Whether to show log messages.
            Default is False.
    """

    data = list()
    for student, i in ids.items():
        data.append({
            'ID': i,
            'student': student,
        })

    filepath = get_path(file=REPORT_IDS_FILE, course=course, assignment=assignment, folder=REPORTS_FOLDER)
    save_csv(data, filepath, description='report ids', log=log)


def save_reports(course: Course,
                 assignment: Assignment,
                 reports: Dict[str, str],
                 log: bool = False
                 ):
    """Saves the report strings as files.

    Args:
        course (Course): The course.
        assignment (Assignment): The assignment.
        reports (Dict[str, str]): The report strings in the format:
            { student: report_str }
        log (bool): Whether to show log messages.
            Default is False.
    """

    path = get_path(course=course, assignment=assignment, folder=REPORTS_FOLDER)
    if log: logger.info('Saving reports as files in "{}"', path)

    for student, report_str in reports.items():
        student_file = os.path.join(path, f'{student}.txt')
        with open(student_file, 'w') as f:
            f.write(report_str)


# ===========================================================================

def apply_reports(assignment: Assignment,
                  reports: Dict[str, str],
                  log: bool = False,
                  progress_interval: int = 100
                  ):
    """Applies the report files to the assignment's submissions.

    Args:
        assignment (Assignment): The assignment.
        reports (Dict[str, str]): The report strings in the format:
            { student: report_str }
        log (bool): Whether to show log messages.
            Default is False.
        progress_interval (int): The interval at which to show submission counts.
            If less than 0, nothing is shown.
            Default is 100.
    """

    if log: logger.info('Applying reports to assignment "{}"', assignment.name)

    for i, submission in enumerate(assignment.list_submissions()):

        if submission.isFinalized: continue

        has_reports = list()
        no_reports = list()
        for student in submission.students:
            if student in reports:
                has_reports.append(student)
            else:
                no_reports.append(student)

        # shouldn't happen, but just in case
        if len(no_reports) > 0:
            if len(no_reports) == len(submission.students):
                if log: logger.warning('Submission {}: No reports to apply', submission.id)
                continue
            if log: logger.warning('Submission {}: No reports to apply for students: {}',
                                   submission.id, ', '.join(no_reports))

        report_str = '\n'.join(reports[student] for student in has_reports)

        # replace file if exists
        for file in submission.files:
            if file.name == REPORT_FILENAME:
                codepost.file.update(
                    id=file.id,
                    code=report_str
                )
                break
        else:
            # create new file
            codepost.file.create(
                name=REPORT_FILENAME,
                code=report_str,
                extension=REPORT_EXT,
                submission=submission.id
            )

        if log and progress_interval > 0 and (i + 1) % progress_interval == 0:
            logger.debug('Done with submission {}', i + 1)


# ===========================================================================

def main(course_name: str,
         course_period: str,
         assignment_name: str,
         from_file: bool = False,
         apply: bool = False,
         log: bool = False
         ):
    """Creates rubric comment usage reports.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        assignment_name (str): The name of the assignment to apply the reports to.
            Will track rubric comments for all preceding assignments.
        from_file (bool): Whether to read the comments from a file.
            Default is False.
        apply (bool): Whether to apply the comments.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.
    """

    if log and from_file and not apply:
        logger.warning('Reading from file but not applying')

    success = log_in_codepost(log=log)
    if not success: return

    success, course = get_course(course_name, course_period, log=log)
    if not success: return

    success, assignment = get_assignment(course, assignment_name, log=log)
    if not success: return

    reports = dict()

    if from_file:
        reports = get_report_files(course, assignment, log=log)

    if len(reports) == 0:
        assignments = get_assignments(course, assignment_name, exclude=None)

        data = get_comments(course, assignments, log=log)
        ids, reports = create_reports(data, log=log)

        save_ids(course, assignment, ids, log=log)
        save_reports(course, assignment, reports, log=log)

    if apply:
        apply_reports(assignment, reports, log=log)

# ===========================================================================
