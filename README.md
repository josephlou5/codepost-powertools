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
- `os`: For working with local files and directories
- `random`: For randomness in `grading_queue.py`
- `datetime`: For the current date in the report file in `track_comments.py`
- `comma`: For working with `.csv` files

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
- `-i`/`--instances`: Whether to count instances of rubric comments. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.   
  - If running as a test and `num_assignments` is not given, `num_assignments` is set to `1`.

### sheet_to_rubric.py
Imports a codePost rubric from a Google Sheet, using the `name` field of rubric comments to account for updates.

Command-line arguments:
- `course_period`: The period of the COS126 course to import to.
- `sheet_name`: The name of the sheet to pull the rubrics from.
- `start_sheet`: The index of the first sheet to pull from (0-indexed). Default is `0`.
- `end_sheet`: The index of the last sheet to pull from (0-indexed). Default is same as `start_sheet`.
- `-o`/`--override`: Whether to override rubrics of assignments. Default is `False`.
- `-d`/`--delete`: Whether to delete comments that are not in the sheet. Default is `False`.
- `-w`/`--wipe`: Whether to completely wipe the existing rubric. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.
  - If running as a test and `start_sheet` is not given, `start_sheet` is set to `0`.

### auto_commenter.py
Automatically add rubric comments to submissions.
Skips finalized submissions and files with any comments.
Saves all the created comments to a `.txt` file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

### assign_failed.py
Assign all submissions that fail tests to a grader.
Saves all failed submissions to a `.csv` file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `grader`: The grader to assign the submissions to. Accepts netid or email.
- `-c`/`--cutoff`: The number of tests that denote "passed". Must be positive. Default is all passed.
- `-sa`/`--search-all`: Whether to search all submissions, not just those with no grader. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

### grading_queue.py
Grading queue related operations.

Run commands with:
```
> python grading_queue.py COMMAND [OPTIONS] ARGS
```

#### claim
Claims submissions to a grader.
Saves all claimed submissions to a file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-g`/`--grader`: The grader to claim to. Accepts netid or email. Default is `DUMMY_GRADER`.
- `-f`/`--from`: The grader to claim from. Accepts netid or email. Default is `None` (unclaimed submissions).
- `-n`/`--num`: The number of submissions to claim. Must be positive. Overrides `percentage` if both given. Default is ALL.
- `-p`/`--percentage`: The percentage of submissions to claim, as an `int` (e.g. 60% is 60). Default is 100%.
- `-r`/`--random`: Whether to claim random submissions. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### unclaim
Unclaims submissions from a grader.
Saves all unclaimed submissions to a file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-g`/`--grader`: The grader to unclaim from. Accepts netid or email. Default is `DUMMY_GRADER`.
- `-n`/`--num`: The number of submissions to unclaim. Must be positive. Overrides `percentage` if both given. Default is ALL.
- `-p`/`--percentage`: The percentage of submissions to unclaim, as an `int` (e.g. 60% is 60). Default is 100%.
- `-r`/`--random`: Whether to unclaim random submissions. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### stats
Lists current stats of grading queue.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### finalized
Finds finalized submissions.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-s`/`--save`: Whether to save the submissions to a file. Default is `False`.
- `-o`/`--open`: Whether to open the finalized submissions. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### audit
Deals with auditing submissions.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment.
- `-r`/`--report`: Whether to generate a report of the auditing. Default is `False`.
  - If `True`, will not do anything else.
- `-ff`/`--from-file`: Whether to read the submissions from a file. Default is `False`.
- `-f`/`--only-finalized`: Whether to only search finalized submissions. Default is `False`.
- `-n`/`--num-times`: How many times each submission should be audited. Must be positive. Default is `2`.
- `-l`/`--list-submission`: Whether to list the submissions. Default is `False`.
- `-s`/`--save`: Whether to save the submissions to a file. Default is `False`.
- `-o`/`--open`: Whether to open the submissions. Default is `False`.
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

### track_comments.py
Track rubric comment usage for students and graders and creates reports.

- `course_period`: The period of the COS126 course.
- `assignment_name`: The name of the assignment to apply the reports to.
- `-f`/`--from-file`: Whether to read the reports from files. Default is `False`.
  - If reports files for some students are missing, won't generate a report for them.
  - If no report files exist, will grab from codePost.
- `-s`/`--save-files`: Whether to save the reports as files. Default is `False`.
  - If reading reports from files was successful, no need to save files again.
- `-a`/`--apply`: Whether to apply the reports to the submissions. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.
