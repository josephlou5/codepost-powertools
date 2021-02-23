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
- `json`: For file dump in `claim.py`

## Usage

Get your [codePost API key](https://docs.codepost.io/docs/first-steps-with-the-codepost-python-sdk#2-obtaining-your-codepost-api-key)
and save the `.codepost-config.yaml` or `codepost-config.yaml` file in the `rubric` directory.

Create a [service account](https://gspread.readthedocs.io/en/latest/oauth2.html#for-bots-using-service-account)
and share your Google Sheet with it. Save the `service_account.json` file in the `rubric` directory.
The name of this file can be customized in `shared.py`.

Whenever testing, the dummy course `Joseph's Course` is used instead of an actual codePost course.

### rubric_to_sheet.py
Exports a codePost rubric to a Google Sheet. Replaces the entire sheet.

Command-line arguments:
- `course_period`: The period of the COS126 course to export from.
- `sheet_name`: The name of the sheet to import the rubrics to.
- `num_assignments`: The number of assignments to get from the course. Default is ALL.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.   
  - If running as a test and `num_assignments` is not given, `num_assignments` is set to `1`.
- `-i`/`--instances`: Whether to count instances of rubric comments. Default is `False`.

### sheet_to_rubric.py
Imports a codePost rubric from a Google Sheet, using the `name` field of rubric comments to account for updates.

Command-line arguments:
- `course_period`: The period of the COS126 course to import to.
- `sheet_name`: The name of the sheet to pull the rubrics from.
- `start_sheet`: The index of the first sheet to pull from (0-indexed). Default is `0`.
- `end_sheet`: The index of the last sheet to pull from (0-indexed). Default is same as `start_sheet`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.
  - If running as a test and `start_sheet` is not given, `start_sheet` is set to `0`.
- `-o`/`--override`: Whether to override rubrics of assignments. Default is `False`.
- `-d`/`--delete`: Whether to delete comments that are not in the sheet. Default is `False`.
- `-w`/`--wipe`: Whether to completely wipe the existing rubric. Default is `False`.

### assign_failed.py
Assign all submissions that fail tests to a grader.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `grader`: The grader to assign the submissions to.
- `cutoff`: The number of tests that denote "passed". Default is all passed.
- `-sa`/`--search-all`: Whether to search all submissions, not just those with no grader. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

### auto_comments.py
Automatically add rubric comments to submissions.
Skips finalized submissions and files with any comments.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

### claim.py
Claims all remaining submissions to a dummy grader account,
or unclaims all submissions assigned to the dummy grader account.
If claiming, dumps all the graders for the submissions into a `.json` file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `claiming`: Whether to claim or unclaim submissions.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

### find_no_comments.py
Find all submissions that have no comments.
To "open" a submission means to remove its grader and mark it as unfinalized,
so that another grader can claim it from the queue.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-lf`/`--list-finalized`: Whether to list finalized submissions that have no comments. Default is `False`.
- `-la`/`--list-all`: Whether to list all submissions that have no comments. Default is `False`.
- `-of`/`--open-finalized`: Whether to open finalized submissions that have no comments. Default is `False`.
- `-oa`/`--open-all`: Whether to open all submissions that have no comments. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.
