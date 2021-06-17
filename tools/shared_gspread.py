"""
shared_gspread.py
Shared methods for gspread.
"""

__all__ = [
    # types
    'Color',
    'GClient', 'GSpreadsheet', 'GWorksheet', 'GCell',

    # classes
    'Worksheet',

    # methods
    'set_up_service_account',
    'open_sheet', 'add_worksheet',
    'display_on_worksheet',
]

# ===========================================================================

import os
from typing import (
    Any,
    Tuple, List, Dict,
    Sequence,
    Optional,
)

import gspread
from loguru import logger

from myworksheet import *
from shared import Color

# ===========================================================================

# types
GClient = gspread.Client


# ===========================================================================

def set_up_service_account(filepath: str = 'service_account.json',
                           log: bool = False
                           ) -> Tuple[bool, Optional[GClient]]:
    """Sets up the Google service account to connect with Google Sheets.

    Args:
        filepath (str): The filepath of the service account file.
            Default is 'service_account.java'.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Tuple[bool, Optional[GClient]]:
            If the setup was successful, returns True and the client.
            If the setup was unsuccessful, returns False and None.
    """

    if log: logger.info('Setting up service account')

    if not os.path.exists(filepath):
        msg = f'"{filepath}" file not found in directory'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return False, None

    return True, gspread.service_account(filepath)


# ===========================================================================

def open_sheet(g_client: GClient, sheet_name: str, log: bool = False) -> Tuple[bool, Optional[GSpreadsheet]]:
    """Opens a Google Sheet.

    Args:
        g_client (GClient): The Client used.
        sheet_name (str): The name of the sheet to open.
        log (bool): Whether to show log messages.
            Default is False.

    Returns:
        Tuple[bool, Optional[GSpreadsheet]]:
            If the opening was successful, returns True and the spreadsheet.
            If the opening was unsuccessful, returns False and None.
    """

    if log: logger.info('Opening "{}" sheet', sheet_name)

    try:
        return True, g_client.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        msg = f'Spreadsheet "{sheet_name}" not found'
        if not log: raise RuntimeError(msg)
        logger.error(msg)
        return False, None


# ===========================================================================

def add_worksheet(sheet: GSpreadsheet,
                  title: str = 'Sheet',
                  rows: int = 1,
                  cols: int = 1,
                  index: int = None
                  ) -> GWorksheet:
    """Adds a temp worksheet to a sheet.

    Args:
        sheet (GSpreadsheet): The sheet.
        title (str): The title of the temp worksheet.
            Default is 'Sheet'.
            Will add numbers if the name already exists.
        rows (int): The number of rows.
            Default is 1.
        cols (int): The number of cols.
            Default is 1.
        index (int): The index where the temp worksheet should go.
            Default is None (at the end).

    Returns:
        GWorksheet: The added worksheet.
    """

    try:
        return sheet.add_worksheet(title, rows, cols, index)
    except gspread.exceptions.APIError:
        pass
    count = 1
    while True:
        try:
            return sheet.add_worksheet(f'{title}{count}', rows, cols, index)
        except gspread.exceptions.APIError:
            count += 1


# ===========================================================================

def display_on_worksheet(worksheet: Worksheet,
                         values: List[Any],
                         cell_range: str = 'A1',
                         freeze: int = 0,
                         cell_formats: Sequence[Tuple[str, Dict[str, Any]]] = None,
                         number_formats: Sequence[Tuple[str, Dict[str, Any]]] = None,
                         col_widths: Sequence[Tuple[str, int]] = None,
                         merge: Sequence[str] = None,
                         hide_cols: Sequence[str] = None
                         ):
    """Displays values on a worksheet.

    Args:
        worksheet (Worksheet): The worksheet.
        values (List[Any]): The values.
        cell_range (str): The range to display the values.
            Default is 'A1'.
        freeze (int): The number of rows to freeze.
            Default is 0.
        cell_formats (Sequence[Tuple[str, Dict[str, Any]]]): The args for formatting a cell.
            Default is None.
        number_formats (Sequence[Tuple[str, Dict[str, Any]]]): The args for formatting a number cell.
            Default is None.
        col_widths (Sequence[Tuple[str, int]]): The args for setting a column's width.
            Default is None.
        merge (Sequence[str]): The cell ranges to merge.
            Default is None.
        hide_cols (Sequence[str]): The columns to hide.
            Default is None.
    """

    # add empty rows to avoid freezing all rows error
    if len(values) < freeze:
        # reassigns `values`; doesn't mutate
        values = values + [''] * (freeze - len(values) + 1)

    worksheet.set_values(cell_range, values)

    if freeze > 0:
        worksheet.freeze_rows(freeze)
    if cell_formats is not None:
        for rnge, kwargs in cell_formats:
            worksheet.format_cell(rnge, **kwargs)
    if number_formats is not None:
        for rnge, kwargs in number_formats:
            worksheet.format_number_cell(rnge, **kwargs)
    if col_widths is not None:
        for args in col_widths:
            worksheet.set_col_width(*args)
    if merge is not None:
        for rnge in merge:
            worksheet.merge_cells(rnge)
    if hide_cols is not None:
        for rnge in hide_cols:
            worksheet.hide_col(rnge)

    worksheet.update()

# ===========================================================================
