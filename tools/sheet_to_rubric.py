"""
sheet_to_rubric.py
Imports a codePost rubric from a Google Sheet.
"""

# ===========================================================================

from typing import (
    Tuple, List, Dict,
    Iterable,
    Optional, Union,
)

import codepost
from loguru import logger

from shared import *
from shared_codepost import *
from shared_gspread import *

# ===========================================================================

SHEET_HEADERS = {
    # info: header title on sheet
    'category': 'Category',
    'max points': 'Max',

    'name': 'Name',
    'tier': 'Tier',
    'point delta': 'Points',
    'caption': 'Grader Caption',
    'explanation': 'Explanation',
    'instructions': 'Instructions',
    'is template': 'Template?',
}

TEMPLATE_YES = ('x', 'yes', 'y')


# ===========================================================================

def get_worksheets(sheet: GSpreadsheet,
                   assignments: Iterable[Assignment],
                   start_sheet: int = 0,
                   end_sheet: int = 0,
                   log: bool = False
                   ) -> List[Optional[Worksheet]]:
    """Gets the worksheets for the given assignments.

    Args:
        sheet (GSpreadsheet): The sheet.
        assignments (Iterable[Assignment]): The assignments.
        start_sheet (int): The index of the start sheet (0-indexed).
            Default is 0.
        end_sheet (int): The index of the end sheet (0-indexed, inclusive).
            Default is same as `start_sheet`.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        List[Optional[Worksheet]]: The Worksheets in parallel with `assignments`.
            If no Worksheet exists for an Assignment, its value is None in the list.
    """

    if log: logger.info('Finding worksheets for each assignment')

    start_sheet = max(0, start_sheet)
    end_sheet = max(start_sheet, end_sheet)

    worksheets = {a.id: None for a in assignments}

    num_found = 0
    for index in range(start_sheet, end_sheet + 1):
        w = sheet.get_worksheet(index)
        if w is None: continue

        worksheet = Worksheet(w)

        # check assignment id in A1
        try:
            a_id = int(worksheet.get_cell('A1').value)
        except ValueError:
            continue

        if a_id not in worksheets: continue

        # TODO: necessary?
        if worksheets[a_id] is not None:
            if log: logger.warning('The assignment of the "{}" worksheet already exists', worksheet.title)
            continue

        worksheets[a_id] = worksheet
        num_found += 1

    if log:
        num_assignments = len(worksheets)
        if num_found == num_assignments:
            logger.debug('Found worksheets for each assignment')
        else:
            logger.debug('Found worksheets for {} out of {} assignments', num_found, num_assignments)

    return list(worksheets.values())


# ===========================================================================


def get_sheet_rubric(worksheet: Worksheet,
                     log: bool = False
                     ) -> Dict[str, Tuple[Optional[int], List[Dict[str, Union[str, float]]]]]:
    """Gets the rubric comments from a worksheet.

    Args:
        worksheet (Worksheet): The worksheet.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Dict[str, Tuple[Optional[int], List[Dict[str, Union[str, float]]]]]: The rubric comments in the format:
                { category: (max_points, [comments]) }
            where `comments` are the keyword arguments for creating a rubric comment.
    """

    if log: logger.debug('Getting rubric from "{}" worksheet', worksheet.title)

    data = dict()

    # go through the rows of the worksheet
    values = worksheet.get_records(head=2)
    for row in values:

        # get category
        category = row.get(SHEET_HEADERS['category'], None)
        if category is None or category == '':
            continue

        # get comment info

        # if name does not exist, skip
        name = row.get(SHEET_HEADERS['name'], None)
        if name is None or name == '':
            continue
        # if tier does not exist, do not add it
        tier = row.get(SHEET_HEADERS['tier'], None)
        # if points does not exist, default is 0
        points = -1 * row.get(SHEET_HEADERS['point delta'], 0)
        # if text does not exist, skip
        text = row.get(SHEET_HEADERS['caption'], None)
        if text is None or text == '':
            continue
        # if explanation does not exist, default is None
        explanation = row.get(SHEET_HEADERS['explanation'], None)
        # if instructions does not exist, default is None
        instructions = row.get(SHEET_HEADERS['instructions'], None)
        # if template does not exist, default is False
        template = row.get(SHEET_HEADERS['is template'], '')
        is_template = (template.lower() in TEMPLATE_YES)

        # add tier to comment text
        if tier is not None and tier != '':
            text = TIER_FORMAT.format(tier=tier, text=text)

        comment = {
            'name': name,
            'text': text,
            'pointDelta': points,
            'explanation': explanation,
            'instructionText': instructions,
            'templateTextOn': is_template,
        }

        # create entries for category and comment
        if category not in data:
            max_points = row.get(SHEET_HEADERS['max points'], None)
            if max_points == '':
                max_points = None
            else:
                max_points = -1 * int(max_points)
            data[category] = (max_points, list())
        data[category][1].append(comment)

    return data


# ===========================================================================

def update_assignment_rubric(assignment: Assignment,
                             rubric: Dict[str, Tuple[Optional[int], List[Dict[str, Union[str, float]]]]],
                             force_update: bool = False,
                             delete_missing: bool = False,
                             wipe: bool = False,
                             log: bool = False
                             ):
    """Creates the rubric comments for an assignment.

    Args:
        assignment (Assignment): The assignment.
        rubric (Dict[str, Tuple[Optional[int], List[Dict[str, Union[str, float]]]]]):
            The rubric comments in the format:
                { category: (max_points, [comments]) }
            where `comments` are the keyword arguments for creating a rubric comment.
        force_update (bool): Whether to force updating the rubric.
            Default is False.
            If False, will not update a rubric if the assignment has existing submissions.
        delete_missing (bool): Whether to delete the rubric comments not in the sheet.
            Default is False.
        wipe (bool): Whether to wipe the existing rubric.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.
    """

    a_id = assignment.id
    a_name = assignment.name

    if log: logger.debug('Updating rubric for "{}" assignment', a_name)

    # check for existing submissions
    has_submissions = len(assignment.list_submissions()) > 0
    if has_submissions:
        if log: logger.warning('"{}" assignment has existing submissions', a_name)
        if not force_update:
            if log: logger.debug('Rubric creation for "{}" assignment unsuccessful', a_name)
            return
        if log: logger.warning('Forcing rubric update')

    # wipe existing rubric
    if wipe:

        if log: logger.debug('Deleting existing rubric')
        for category in assignment.rubricCategories:
            if log: logger.debug('Deleting "{}" rubric category', category.name)
            category.delete()
        if log: logger.debug('Deleted rubric')

        # create new comments
        if log: logger.debug('Creating new rubric categories')
        for sort_key, (c_name, (max_points, comments)) in enumerate(rubric.items()):

            if log: logger.debug('Creating "{}" rubric category', c_name)

            category = codepost.rubric_category.create(
                name=c_name,
                assignment=a_id,
                pointLimit=max_points,
                sortKey=sort_key,
            )
            c_id = category.id

            # create comments
            for comment in comments:
                codepost.rubric_comment.create(category=c_id, **comment)

        if log: logger.debug('Rubric creation for "{}" assignment successful', a_name)
        return

    # get all existing rubric comments
    if log: logger.debug('Getting existing rubric comments')
    codepost_comments: Dict[str, RubricComment] = dict()
    categories: Dict[str, RubricCategory] = dict()
    ids: Dict[int, str] = dict()
    empty_categories: List[RubricCategory] = list()
    for category in assignment.rubricCategories:
        comments = category.rubricComments
        if len(comments) == 0:
            empty_categories.append(category)
            continue
        categories[category.name] = category
        ids[category.id] = category.name
        for comment in comments:
            codepost_comments[comment.name] = comment

    # get all rubric comments from sheet
    # maps comment name -> category name
    sheet_categories: Dict[str, str] = dict()
    # maps comment name -> comment info (in kwargs format)
    sheet_comments: Dict[str, Dict[str, Union[str, float]]] = dict()
    # maps comment name -> sort key
    sort_keys: Dict[str, int] = dict()
    for category_name, (_, comments) in rubric.items():
        sort_key = 0
        for comment in comments:
            name = comment['name']
            sheet_categories[name] = category_name
            sheet_comments[name] = comment
            sort_keys[name] = sort_key
            sort_key += 1

    # missing comments
    missing_comments: List[RubricComment] = list()
    sheet_names = set(sheet_comments.keys())
    for name in codepost_comments.keys():
        try:
            # if this succeeds, this name already exists in the sheet
            sheet_names.remove(name)
            continue
        except KeyError:
            pass
        # if it's not in the sheet, then it's an already existing codepost comment
        missing_comments.append(codepost_comments.pop(name))
    del sheet_names

    if len(missing_comments) > 0:
        if log: logger.debug('Found {} comments not in the sheet: {}',
                             len(missing_comments), ','.join(c.name for c in missing_comments))

        # delete rubric comments not in the sheet
        if delete_missing:
            if log: logger.debug('Deleting comments not in the sheet')
            search = set()
            for comment in missing_comments:
                search.add(ids[comment.rubricCategory])
                comment.delete()
            if log: logger.debug('Deleted {} comments', len(missing_comments))

            # find possible empty categories
            for c_name in search:
                category = categories[c_name]
                if len(category.rubricComments) == 0:
                    categories.pop(c_name)
                    empty_categories.append(category)

        # if not deleting, then sort them properly
        else:
            offsets = dict()
            for comment in missing_comments:
                c_name = ids[comment.rubricComment]
                if c_name not in offsets:
                    offsets[c_name] = len(rubric[c_name][1])
                codepost.rubric_comment.update(
                    id=comment.id,
                    sortKey=offsets[c_name]
                )
                offsets[c_name] += 1

    if len(empty_categories) > 0:
        if log: logger.debug('Found {} empty categories: {}',
                             len(empty_categories), ','.join(c.name for c in empty_categories))

        # delete rubric categories not in the sheet
        if delete_missing:
            if log: logger.debug('Deleting empty categories')
            for category in empty_categories:
                category.delete()
            if log: logger.debug('Deleted {} empty categories', len(empty_categories))

    # create new categories (if needed)
    # the order of the sets doesn't matter because of sortkey ordering later
    existing_categories = set(categories.keys())
    new_categories = set(rubric.keys())
    missing_categories = new_categories - existing_categories
    del existing_categories, new_categories

    if len(missing_categories) > 0:
        if log: logger.debug('Creating missing rubric categories')
        for c_name in missing_categories:
            max_points = rubric[c_name][0]
            category = codepost.rubric_category.create(
                name=c_name,
                assignment=a_id,
                pointLimit=max_points,
            )
            categories[c_name] = category
        if log: logger.debug('Created {} missing rubric categories', len(missing_categories))

    # sort categories
    for sort_key, category_name in enumerate(rubric.keys()):
        codepost.rubric_category.update(
            id=categories[category_name].id,
            sortKey=sort_key,
        )

    # include category id and sort keys in comment info
    for name, comment_info in sheet_comments.items():
        category_id = categories[sheet_categories[name]].id
        comment_info['category'] = category_id
        comment_info['sortKey'] = sort_keys[name]

    # update existing comments
    logger.debug('Updating existing rubric comments')
    for name, comment in codepost_comments.items():
        comment_info = sheet_comments[name]
        old_comment = {
            'name': comment.name,
            'text': comment.text,
            'pointDelta': comment.pointDelta,
            'category': comment.category,
            'explanation': comment.explanation,
            'instructionText': comment.instructionText,
            'templateTextOn': comment.templateTextOn,
            'sortKey': comment_info['sortKey'],
        }

        # if anything isn't the same, update the comment
        if old_comment != comment_info:
            codepost.rubric_comment.update(comment.id, **comment_info)
            logger.debug('Updated "{}"', name)

    # create new comments
    new_names: List[str] = list()
    existing_names = set(codepost_comments.keys())
    for name in sheet_comments.keys():
        try:
            # if this succeeds, this name already exists in codepost
            existing_names.remove(name)
            continue
        except KeyError:
            pass
        # if it's not yet in codepost, it's a new comment
        new_names.append(name)
    del existing_names

    if len(new_names) == 0:
        if log: logger.debug('No new rubric comments to create')
    else:
        if log: logger.debug('Creating new rubric comments')
        for name in new_names:
            comment_info = sheet_comments[name]
            codepost.rubric_comment.create(**comment_info)
            if log: logger.debug('Created "{}" in "{}"', name, sheet_categories[name])
        if log: logger.debug('Created {} new rubric comments', len(new_names))

    if log: logger.debug('Rubric creation for "{}" assignment successful', a_name)


# ===========================================================================

def main(course_name: str,
         course_period: str,
         sheet_name: str,
         start_sheet: int = 0,
         end_sheet: int = 0,
         force_update: bool = False,
         delete_missing: bool = False,
         wipe: bool = False,
         log: bool = False
         ):
    """Imports a codePost rubric from a Google Sheet.

    Args:
        course_name (str): The course name.
        course_period (str): The course period.
        sheet_name (str): The sheet name.
        start_sheet (int): The start sheet (0-indexed).
            Default is 0.
        end_sheet (int): The end sheet (0-indexed, inclusive).
            Default is same as `start_sheet`.
        force_update (bool): Whether to force updating the rubric.
            If False, will not update a rubric if the assignment has existing submissions.
            Default is False.
        delete_missing (bool): Whether to delete the rubric comments not in the sheet.
            Default is False.
        wipe (bool): Whether to wipe the existing rubric.
            Default is False.
        log (bool): Whether to show log messages.
            Default is False.
    """

    success = log_in_codepost(log=log)
    if not success: return

    success, g_client = set_up_service_account(log=log)
    if not success: return

    success, course = get_course(course_name, course_period, log=log)
    if not success: return

    success, sheet = open_sheet(g_client, sheet_name, log=log)
    if not success: return

    assignments = sorted(course.assignments, key=lambda a: a.sortKey)
    worksheets = get_worksheets(sheet, assignments, start_sheet, end_sheet, log=log)

    if worksheets == [None] * len(worksheets):
        msg = 'No matching worksheets for assignments'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return

    if log: logger.info('Updating assignment rubrics')

    for assignment, worksheet in zip(assignments, worksheets):
        if worksheet is None:
            if log: logger.debug('No worksheet for assignment "{}"', assignment.name)
            continue

        rubric = get_sheet_rubric(worksheet, log=log)

        update_assignment_rubric(
            assignment, rubric,
            force_update=force_update,
            delete_missing=delete_missing,
            wipe=wipe,
            log=log
        )

    if log: logger.info('Created all rubrics')

# ===========================================================================
