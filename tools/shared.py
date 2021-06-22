"""
shared.py
Shared.
"""

__all__ = [
    # types
    'Color',
    'Course', 'Assignment', 'Submission', 'File', 'Comment', 'RubricCategory', 'RubricComment',
]

# ===========================================================================

from typing import Tuple

from codepost.models.courses import Courses as Course
from codepost.models.rubric_categories import RubricCategories as RubricCategory
from codepost.models.rubric_comments import RubricComments as RubricComment
from codepost.models.assignments import Assignments as Assignment
from codepost.models.submissions import Submissions as Submission
from codepost.models.files import Files as File
from codepost.models.comments import Comments as Comment

# ===========================================================================

# types

Color = Tuple[int, int, int]

# ===========================================================================
