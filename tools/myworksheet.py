"""
myworksheet.py
Worksheet class.

gspread API
https://gspread.readthedocs.io/en/latest/index.html

Sheet batch updating
https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
"""

__all__ = [
    'GSpreadsheet', 'GWorksheet', 'GCell',
    'Worksheet'
]

# ===========================================================================

from typing import (
    Any,
    List, Dict,
    Optional,
)

import gspread.models
from gspread.utils import (
    a1_range_to_grid_range as gridrange,
    rowcol_to_a1
)

from shared import Color

# ===========================================================================

# types
GSpreadsheet = gspread.models.Spreadsheet
GWorksheet = gspread.models.Worksheet
GCell = gspread.models.Cell

# constants
MAX_RGB: int = 255


# ===========================================================================

class Worksheet:
    """Worksheet class: Represents a Worksheet.

    Constructors:
        Worksheet(worksheet):
            Initializes a Worksheet.

    Constants:
        DEFAULT_COL_WIDTH (int): The default column width.

    Properties:
        title (str): The title of the worksheet.
        num_rows (int): The number of rows.
        num_frozen_rows (int): The number of frozen rows.

    Static Methods:
        to_a1(row, col)
            Returns the row and column in A1 notation.

    Methods:
        update()
            Update the actual Google Sheet.

        get_cell(cell)
            Get a cell of the Worksheet.

        get_values()
            Gets all the values of the Worksheet.

        get_records(empty2zero=False, head=1, default_blank='')
            Returns the values of the Worksheet with the head row as keys.

        get_row_values(self, row)
            Returns the values of a row.

        set_values(values)
            Set the values of the Worksheet.

        resize(rows=None, cols=None)
            Resize the Worksheet.

        freeze_rows(rows, update=False)
            Freeze a number of rows.

        reset_col_width(col, update=False)
            Reset the width of a column (to 100 pixels).

        set_col_width(col, width, update=False)
            Set the width of a column.

        hide_col(col, update=False)
            Hide a column.

        merge_cells(rnge, update=False)
            Merge cells.

        format_cell(rnge,
                    font_family=None,
                    bold=None,
                    background_color=None,
                    text_color=None,
                    text_align=None,
                    vertical_align=None,
                    wrap=None,
                    update=False)
            Format a cell.

        format_number_cell(rnge, fmt_type, pattern, update=False)
            Apply a number format to a cell.

        add_formula(rnge, formula, update=False)
            Add a formula to a cell.

        add_hyperlink(rnge, link, update=False)
            Add a hyperlink to a cell.
    """

    DEFAULT_COL_WIDTH: int = 100

    # ==================================================

    def __init__(self, worksheet: GWorksheet):
        """Initializes a Worksheet.

        Args:
            worksheet (GWorksheet): The worksheet.
        """

        self._sheet: GSpreadsheet = worksheet.spreadsheet
        self._wkst: GWorksheet = worksheet
        self._id: int = worksheet.id
        self._requests: List[Dict] = list()

    # ==================================================

    def __str__(self) -> str:
        return str(self._wkst)

    def __repr__(self) -> str:
        return repr(self._wkst)

    # ==================================================

    # properties

    @property
    def title(self) -> str:
        return self._wkst.title

    @title.setter
    def title(self, val: str):
        if val == self.title: return
        try:
            self._wkst.update_title(val)
        except gspread.exceptions.APIError:
            pass
        count = 1
        while True:
            try:
                self._wkst.update_title(f'{val}{count}')
                return
            except gspread.exceptions.APIError:
                count += 1

    @property
    def num_rows(self) -> int:
        return self._wkst.row_count

    @property
    def num_frozen_rows(self) -> int:
        return self._wkst.frozen_row_count

    # ==================================================

    # private methods

    def _get_range(self, rnge: str, dim: str) -> Dict[str, int]:
        """Returns the DimensionRange dict of a range.

        Args:
            rnge (str): The cell range.
            dim (str): The dimension.
                Choices: ROW, COLUMN.

        Returns:
            Dict[str, int]: The dimension range dict
        """

        if dim.lower() not in ('row', 'column'):
            raise ValueError(f'Invalid dimension: {dim}')

        grid = gridrange(rnge)

        rd = {
            'sheet_id': self._id,
            'dimension': dim.upper() + 'S',
        }

        dim = dim.title()
        if f'start{dim}Index' in grid:
            rd['startIndex'] = grid[f'start{dim}Index']
        if f'end{dim}Index' in grid:
            rd['endIndex'] = grid[f'end{dim}Index']

        return rd

    def _get_row_range(self, row: str) -> dict:
        return self._get_range(row, 'row')

    def _get_col_range(self, col: str) -> dict:
        return self._get_range(col, 'column')

    # ==================================================

    @staticmethod
    def to_a1(row: int, col: int) -> str:
        """Returns the row and column in A1 notation."""
        return rowcol_to_a1(row, col)

    # ==================================================

    # public methods

    def update(self):
        """Updates the Google Sheet with requests."""

        body = {'requests': self._requests}
        self._sheet.batch_update(body)
        self._requests.clear()

    def get_cell(self, cell: str) -> GCell:
        """Gets a cell of the Worksheet.

        Args:
            cell (str): The A1 notation of the cell.

        Returns:
            GCell: The Cell.
        """
        return self._wkst.acell(cell)

    def get_values(self) -> List[List[str]]:
        """Gets all the values of the Worksheet."""
        return self._wkst.get_all_values()

    def get_records(self, empty2zero: bool = False, head: int = 1, default_blank: Any = '') -> List[Dict[str, Any]]:
        """Gets the values of the Worksheet with the head row as keys.

        Args:
            empty2zero (bool): Whether empty cells are converted to 0.
                Default is False.
            head (int): The header row.
                Default is 1.
            default_blank (Any): The default value of blank cells.
                Default is the empty string.

        Returns:
            List[Dict[str, Any]]: The values in the format:
                [ { header1: val1, header2: val2, ... }, ... ]
        """
        return self._wkst.get_all_records(empty2zero=empty2zero, head=head, default_blank=default_blank)

    def get_row_values(self, row: int) -> List[Optional[str]]:
        """Gets the values of a row.

        Args:
            row (int): The row number (1-indexed).

        Returns:
            List[Optional[str]]: The row values.
        """
        return self._wkst.row_values(row)

    def set_values(self, *args):
        """Sets the values of the Worksheet."""
        self._wkst.update(*args)

    def resize(self, rows: int = None, cols: int = None):
        """Resizes the Worksheet.

        Args:
            rows (int): The new number of rows.
            cols (int): The new number of columns.
        """
        self._wkst.resize(rows, cols)

    def freeze_rows(self, rows: int, update: bool = False):
        """Freezes a number of rows.

        Args:
            rows (int): The number of rows to freeze.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        # self._wkst.freeze(rows=rows)
        self._requests.append({
            'updateSheetProperties': {
                'properties': {
                    'sheetId': self._id,
                    'gridProperties': {
                        'frozenRowCount': rows,
                    },
                },
                'fields': 'gridProperties.frozenRowCount',
            }
        })

        if update: self.update()

    def reset_col_width(self, col: str, update: bool = False):
        """Resets the width of a column.

        Args:
            col (str): The column range.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """
        self.set_col_width(col, self.DEFAULT_COL_WIDTH, update)

    def set_col_width(self, col: str, width: int, update: bool = False):
        """Sets the width of a column.

        Args:
            col (str): The column range.
            width (int): The new width.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        self._requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'pixelSize': width,
                },
                'fields': 'pixelSize',
                'range': self._get_col_range(col),
            }
        })

        if update: self.update()

    def hide_col(self, col: str, update: bool = False):
        """Hides a column.

        Args:
            col (str): The column range.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        self._requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'hiddenByUser': True,
                },
                'fields': 'hiddenByUser',
                'range': self._get_col_range(col),
            }
        })

        if update: self.update()

    def merge_cells(self, rnge: str, update: bool = False):
        """Merges cells.

        Args:
            rnge (str): The cell range.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        self._requests.append({
            'mergeCells': {
                'range': {
                    'sheetId': self._id,
                    **gridrange(rnge),
                },
                'mergeType': 'MERGE_ALL',
            }
        })

        if update: self.update()

    def format_cell(self,
                    rnge: str,
                    font_family: str = None,
                    bold: bool = None,
                    background_color: Color = None,
                    text_color: Color = None,
                    text_align: str = None,
                    vertical_align: str = None,
                    wrap: str = None,
                    update: bool = False):
        """Formats a cell.

        Args:
            rnge (str): The cell range.
            font_family (str): The font family.
            bold (bool): Whether the text is bold.
            background_color (Color): The background color.
            text_color (Color): The text color.
            text_align (str): The text (horizontal) alignment type.
                Choices: LEFT, CENTER, RIGHT.
            vertical_align (str): The vertical alignment type.
                Choices: TOP, MIDDLE, BOTTOM.
            wrap (str): The wrapping type.
                Choices: OVERFLOW_CELL, CLIP, WRAP.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        fmt = dict()
        text_fmt = dict()
        fields = []

        if font_family is not None:
            text_fmt['fontFamily'] = font_family
            fields.append('textFormat.fontFamily')
        if bold is not None and type(bold) is bool:
            text_fmt['bold'] = bold
            fields.append('textFormat.bold')
        if background_color is not None:
            fmt['backgroundColor'] = {
                'red': background_color[0] / MAX_RGB,
                'green': background_color[1] / MAX_RGB,
                'blue': background_color[2] / MAX_RGB,
            }
            fields.append('backgroundColor')
        if text_color is not None:
            text_fmt['foregroundColor'] = {
                'red': text_color[0] / MAX_RGB,
                'green': text_color[1] / MAX_RGB,
                'blue': text_color[2] / MAX_RGB,
            }
            fields.append('textFormat.foregroundColor')
        if text_align is not None:
            fmt['horizontalAlignment'] = text_align
            fields.append('horizontalAlignment')
        if vertical_align is not None:
            fmt['verticalAlignment'] = vertical_align
            fields.append('verticalAlignment')
        if wrap is not None:
            fmt['wrapStrategy'] = wrap
            fields.append('wrapStrategy')

        if len(fields) == 0:
            return

        if len(text_fmt) > 0:
            fmt['textFormat'] = text_fmt

        self._requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': self._id,
                    **gridrange(rnge),
                },
                'cell': {
                    'userEnteredFormat': fmt,
                },
                'fields': ','.join(f'userEnteredFormat.{f}' for f in fields),
            }
        })

        if update: self.update()

    def format_number_cell(self, rnge: str, fmt_type: str, pattern: str, update: bool = False):
        """Formats a number cell.

        Args:
            rnge (str): The cell range.
            fmt_type (str): The format type.
                Choices: TEXT, NUMBER, PERCENT, CURRENCY, DATE, TIME, DATE_TIME, SCIENTIFIC.
            pattern (str): The formatting pattern.
                https://developers.google.com/sheets/api/guides/formats
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        self._requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': self._id,
                    **gridrange(rnge),
                },
                'cell': {
                    'userEnteredFormat': {
                        'numberFormat': {
                            'type': fmt_type,
                            'pattern': pattern,
                        },
                    },
                },
                'fields': 'userEnteredFormat.numberFormat',
            }
        })

        if update: self.update()

    def add_formula(self, rnge: str, formula: str, update: bool = False):
        """Adds a formula to a cell.

        Args:
            rnge (str): The cell range.
            formula (str): The formula.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        if not formula.startswith('='):
            formula = '=' + formula

        self._requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': self._id,
                    **gridrange(rnge),
                },
                'cell': {
                    'userEnteredValue': {
                        'formulaValue': formula,
                    },
                },
                'fields': 'userEnteredValue.formulaValue',
            }
        })

        if update: self.update()

    def add_hyperlink(self, rnge: str, link: str, text: str = None, update: bool = False):
        """Adds a hyperlink to a cell.

        Args:
            rnge (str): The cell range.
            link (str): The link.
            text (str): The label text.
                Default is the link itself.
            update (bool): Whether to update the Worksheet.
                Default is False.
        """

        formula = f'=HYPERLINK("{link}"'
        if text is not None:
            formula += f', "{text}"'
        formula += ')'
        self.add_formula(rnge, formula, update)

# ===========================================================================
