"""
myworksheet.py
Contains the Worksheet class.

gspread API
https://gspread.readthedocs.io/en/latest/index.html

sheet batch updating
https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
"""

__all__ = ['Worksheet']

# ===========================================================================

import gspread.models
from gspread.utils import a1_range_to_grid_range as gridrange

# ===========================================================================

MAX_RGB = 255


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

    Methods:
        update()
            Update the actual Google Sheet.

        get_cell(cell)
            Get a cell of the Worksheet.

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

        add_hyperlink(rnge, link, update=False)
            Add a hyperlink to a cell.
    """

    DEFAULT_COL_WIDTH = 100

    # ==================================================

    def __init__(self, worksheet):
        """Initialize a Worksheet.

        Args:
            worksheet (gspread.models.Worksheet): The worksheet.
        """
        self._sheet = worksheet.spreadsheet
        self._wkst = worksheet
        self._id = worksheet.id
        self._requests = list()

    # ==================================================

    def __str__(self):
        return str(self._wkst)

    def __repr__(self):
        return repr(self._wkst)

    # ==================================================

    # properties

    @property
    def title(self) -> str:
        return self._wkst.title

    @title.setter
    def title(self, val):
        self._wkst.update_title(val)

    @property
    def num_rows(self) -> int:
        return self._wkst.row_count

    @property
    def num_frozen_rows(self) -> int:
        return self._wkst.frozen_row_count

    # ==================================================

    # private methods

    def _get_range(self, rnge, dim) -> dict:
        """Return the DimensionRange dict of the given range str."""

        grid = gridrange(rnge)

        rd = {
            'sheet_id': self._id,
            'dimension': dim.upper() + 'S',
        }
        dim = dim[0].upper() + dim[1:].lower()
        if f'start{dim}Index' in grid:
            rd['startIndex'] = grid[f'start{dim}Index']
        if f'end{dim}Index' in grid:
            rd['endIndex'] = grid[f'end{dim}Index']

        return rd

    def _get_row_range(self, row) -> dict:
        return self._get_range(row, 'row')

    def _get_col_range(self, col) -> dict:
        return self._get_range(col, 'column')

    # ==================================================

    # public methods

    def update(self):
        """Update the actual Google Sheet."""
        body = {'requests': self._requests}
        self._sheet.batch_update(body)
        self._requests = list()

    def get_cell(self, cell) -> gspread.models.Cell:
        """Get a cell of the Worksheet.

        Args:
            cell (str): The A1 notation of the cell.

        Returns:
            gspread.models.Cell: The Cell.
        """
        return self._wkst.acell(cell)

    def get_records(self, empty2zero=False, head=1, default_blank='') -> list:
        """Returns the values of the Worksheet with the head row as keys.

        Args:
            empty2zero (bool): Whether empty cells are converted to 0.
                Default is False.
            head (int): The header row.
                Default is 1.
            default_blank (Any): The default value of blank cells.
                Default is the empty string.

        Returns:
            list: The values in the format:
                [ { header1: val1, header2: val2, ... }, ... ]
        """
        return self._wkst.get_all_records(empty2zero=empty2zero, head=head, default_blank=default_blank)

    def get_row_values(self, row) -> list:
        """Returns the values of a row.

        Args:
            row (int): The row number (1-indexed).

        Returns:
            list: The row values.
        """
        return self._wkst.row_values(row)

    def set_values(self, *args):
        """Set the values of the Worksheet."""
        self._wkst.update(*args)

    def resize(self, rows=None, cols=None):
        """Resize the Worksheet.

        Args:
            rows (int): The new number of rows.
            cols (int): The new number of columns.
        """
        self._wkst.resize(rows, cols)

    def freeze_rows(self, rows, update=False):
        """Freeze a number of rows.

        Args:
            rows (int): The number of rows to freeze.
            update (bool): Whether to update the Worksheet.
        """
        """
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
        """
        self._wkst.freeze(rows=rows)

    def reset_col_width(self, col, update=False):
        """Reset the width of a column.

        Args:
            col (str): The column range.
            update (bool): Whether to update the Worksheet.
        """
        self.set_col_width(col, self.DEFAULT_COL_WIDTH, update)

    def set_col_width(self, col, width, update=False):
        """Set the width of a column.

        Args:
            col (str): The column range.
            width (int): The new width.
            update (bool): Whether to update the Worksheet.
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

    def hide_col(self, col, update=False):
        """Hide a column.

        Args:
            col (str): The column range.
            update (bool): Whether to update the Worksheet.
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

    def merge_cells(self, rnge, update=False):
        """Merge cells.

        Args:
            rnge (str): The cell range.
            update (bool): Whether to update the Worksheet.
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

    def format_cell(self, rnge,
                    font_family=None,
                    bold=None,
                    background_color=None,
                    text_color=None,
                    text_align=None,
                    vertical_align=None,
                    wrap=None,
                    update=False):
        """Format a cell.

        Args:
            rnge (str): The cell range.
            font_family (str): The font family.
            bold (bool): Whether the text is bold.
            background_color (tuple): The background color.
            text_color (tuple): The text color.
            text_align (str): The text (horizontal) alignment type.
            vertical_align (str): The vertical alignment type.
            wrap (str): The wrapping type.
            update (bool): Whether to update the Worksheet.
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

        if len(text_fmt) > 0:
            fmt['textFormat'] = text_fmt

        if len(fields) == 0:
            return

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

    def format_number_cell(self, rnge, fmt_type, pattern, update=False):
        """Apply a number format to a cell.

        Args:
            rnge (str): The cell range.
            fmt_type (str): The format type.
                Can be NUMBER, PERCENT, etc.
            pattern (str): The formatting pattern.
            update (bool): Whether to update the Worksheet.
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

    def add_hyperlink(self, rnge, link, update=False):
        """Add a hyperlink to a cell.

        Args:
            rnge (str): The cell range.
            link (str): The link.
            update (bool): Whether to update the Worksheet.
        """
        self._requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': self._id,
                    **gridrange(rnge),
                },
                'cell': {
                    'hyperlink': link,
                },
                'fields': 'hyperlink',
            }
        })

        if update: self.update()
