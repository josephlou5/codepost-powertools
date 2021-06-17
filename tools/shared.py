"""
shared.py
Shared methods.
"""

__all__ = [
    # types
    'Color',
    'Course', 'Assignment', 'Submission', 'File', 'Comment', 'RubricCategory', 'RubricComment',
]

# ===========================================================================

from typing import Tuple

from codepost.models.assignments import Assignments
from codepost.models.comments import Comments
from codepost.models.courses import Courses
from codepost.models.files import Files
from codepost.models.rubric_categories import RubricCategories
from codepost.models.rubric_comments import RubricComments
from codepost.models.submissions import Submissions

# ===========================================================================

# types

Color = Tuple[int, int, int]

Course = Courses
Assignment = Assignments
Submission = Submissions
File = Files
Comment = Comments
RubricCategory = RubricCategories
RubricComment = RubricComments

# ===========================================================================
