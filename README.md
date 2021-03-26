# codepost-powertools
Some helpful codePost tools using the
[`codePost` SDK](https://github.com/codepost-io/codepost-python)!

---

## Dependencies

### Built-ins
- `datetime`
- `functools`: For updating wrappers
- `os`
- `time`
- `typing`

### Other Packages
- `codepost`
- `comma`
- `click`
- `loguru`

---

## Usage

Get your [codePost API key](https://docs.codepost.io/docs/first-steps-with-the-codepost-python-sdk#2-obtaining-your-codepost-api-key)
and save the `.codepost-config.yaml` or `codepost-config.yaml` file in the `tools` directory.

Whenever testing, the dummy course `Joseph's Course` is used instead of an actual codePost course.

---

### grading.py
Grading related operations.
Saves output files to a folder called `output`.

Run commands with:
```
> python grading.py COMMAND [OPTIONS] ARGS
```

#### Additional dependencies
- `random`
- `pygame`: for `stats` command

#### claim
Claims submissions to a grader.
Saves claimed submissions to file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `file`: The file to read submissions ids from.
  - If `.txt` file, reads one submission id per line.
  - If `.csv` file, reads from `submission_id` column.
  - If not given or no ids found, uses the search flags to go through all submissions.
- `-g`/`--grader`: The grader to claim to. Accepts netid or email. Default is `DUMMY_GRADER`.
- `-n`/`--num`: The number of submissions to claim. Overrides `percentage` if both given. Default is ALL.
- `-p`/`--percentage`: The percentage of submissions to claim, as an `int` (e.g. 60% is 60). Default is 100%.
- `-r`/`--random`: Whether to claim random submissions. Default is `False`.
- `-sa`/`--search-all`: Search all submissions. Default is `False`.
- `-uf`/`--unfinalized`: Search unfinalized submissions. Default is `False`.
- `-uc`/`--unclaimed`: Search unclaimed submissions. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### unclaim
Unclaims submissions.
Saves unclaimed submissions to file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `file`: The file to read submissions ids from.
  - If `.txt` file, reads one submission id per line.
  - If `.csv` file, reads from `submission_id` column.
  - If not given or no ids found, gets all submissions claimed by `DUMMY_GRADER`.
- `-u`/`--unfinalize`: Whether to unfinalize and unclaim finalized submissions. Default is `False`.
- `-n`/`--num`: The number of submissions to unclaim. Overrides `percentage` if both given. Default is ALL.
- `-p`/`--percentage`: The percentage of submissions to unclaim, as an `int` (e.g. 60% is 60). Default is 100%.
- `-r`/`--random`: Whether to unclaim random submissions. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### ids
Creates mapping between student netids and submission ids.
Saves mapping to file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### find
Finds submissions.
Returns intersection of search flags.
Saves found submissions to file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `-g`/`--grader`: The grader to filter. Accepts netid or email.
- `-s`/`--student`: The student to filter. Accepts netid or email.
  - If given, prints student's submission and does not save to file.
- `-f`/`--finalized`: Find finalized submissions. Default is `False`.
- `-uf`/`--unfinalized`: Find unfinalized submissions. Default is `False`.
- `-c`/`--claimed`: Find claimed submissions. Default is `False`.
- `-uc`/`--unclaimed`: Find unclaimed submissions. Default is `False`.
- `-d`/`--drafts`: Find drafts. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### failed
Finds submissions that fail tests.
Saves found submissions and test results to files.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `-c`/`--cutoff`: The number of tests that denote "passed". Default is all passed.
  - If more than the total tests, does not save all submissions to file.
- `-sa`/`--search-all`: Whether to search all submissions, not just those with no grader. Default is `False`.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### finalize
Finalizes submissions.
Saves finalized submissions to file.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `file`: The file to read submissions ids from.
  - If `.txt` file, reads one submission id per line.
  - If `.csv` file, reads from `submission_id` column.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

#### stats
Lists current stats of the grading queue.

Command-line arguments:
- `course_period`: The period of the COS126 course.
- `assignment_name`: The assignment name.
- `-w`/`--window`: The window update interval in seconds. Must be at least 10.
  - If not given, will only print stats.
- `-t`/`--testing`: Whether to run as a test. Default is `False`.

---

### screenshot.py
Screenshots linked comments.
Saves screenshots in `screenshots > Course > Assignment`.

#### Additional dependencies
- `asyncio`
- `PIL`
- `pyppdf`: To fix a [Chromium download error](https://github.com/miyakogi/pyppeteer/issues/219#issuecomment-563077061) in `pyppeteer`
- `pyppeteer`
- `re`

Command-line arguments:
- `link` (optional): A comment link.
- `-f`/`--file`: A file to read submission links from.
  - If `.txt` file, reads one submission link per line.
  - If `.csv` file, reads from `link` column or `submission_id` and `comment_id` columns.
- `-t`/`--timeout`: Timeout limit in seconds. Must be at least 30. Default is 60 sec.
- `-nt`/`--no-timeout`: Whether to run without timeout. Default is `False`.
- `-e`/`--explanation`: Whether to show the comment explanation. Default is `False`.
- `-fc`/`--fit`: Whether to fit to comment. Default is `False`.
  - If `True`, the tattoo is automatically made one line and always put in the bottom right corner.
- `-o`/`--one-line`: Whether to make the tattoo one line. Default is `False`.
- `-c`/`--corner`: Whether to optimize the corner of the tattoo. Default is `False`.
  - Expands the height of the image.
- `-a`/`--adjust`: Whether to adjust the tattoo to not overlap the comment. Default is `False`.
  - Expands the height of the image.

---

[comment]: <> (### rubric.py)

[comment]: <> (In development.)

[comment]: <> (Create a [service account]&#40;https://gspread.readthedocs.io/en/latest/oauth2.html#for-bots-using-service-account&#41;)

[comment]: <> (and share your Google Sheet with it.)

[comment]: <> (Save the `service_account.json` file in the `tools` directory.)

[comment]: <> (Run commands with:)

[comment]: <> (```)

[comment]: <> (> python rubric.py COMMAND [OPTIONS] ARGS)

[comment]: <> (```)

[comment]: <> (#### Additional dependencies)

[comment]: <> (- `gspread`)
