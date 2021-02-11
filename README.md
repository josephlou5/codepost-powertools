# codepost-rubric-import-export
Imports/exports codePost rubrics from/to Google Sheets
using the [`codePost` SDK](https://github.com/codepost-io/codepost-python)
and the [`gspread` package](https://gspread.readthedocs.io/en/latest/).

## Dependencies
- `codepost`: To work with codePost
- `gspread`: To work with Google Sheets
- `click`: For command line interface
- `loguru`: For logging status messages
- `time`: For timing

## Usage

Get your [codePost API key](https://docs.codepost.io/docs/first-steps-with-the-codepost-python-sdk#2-obtaining-your-codepost-api-key)
and save the `.codepost-config.yaml` or `codepost-config.yaml` file in the `rubric` directory.

Create a [service account](https://gspread.readthedocs.io/en/latest/oauth2.html#for-bots-using-service-account)
and share your Google Sheet with it. Save the `service_account.json` file in the `rubric` directory.
The name of this file can be customized in `shared.py`.

### rubric_to_sheet.py
Exports a codePost rubric to a Google Sheet. Takes in the following command-line arguments:
- `course_period`: The period of the COS126 course to export from.
- `sheet_name`: The name of the sheet to import the rubrics to.
- `num_assignments`: The number of assignments to get from the course. Default is ALL.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.   
  - If running as a test and `num_assignments` is not given, `num_assignments` is set to 1.
- `-i`/`--instances`: Whether to count instances of rubric comments. Default is `False`.

### sheet_to_rubric.py
Imports a codePost rubric from a Google Sheet. Takes in the following command-line arguments:
- `course_period`: The period of the COS126 course to import to.
- `sheet_name`: The name of the sheet to pull the rubrics from.
- `num_assignments`: The number of assignments to get from the sheet. Default is ALL.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.
  - If running as a test and `num_assignments` is not given, `num_assignments` is set to 1.
- `-o`/`--override`: Whether to override rubrics of assignments if submissions exist. Default is `False`.

### assign_failed.py
Assign all submissions that fail any tests to a grader. Takes in the following command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `grader`: The grader to assign the submissions to.
- `testing`: Whether to run as a test. Default is `False`.
