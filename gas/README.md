# codePost Powertools - Google Apps Script

The codePost Powertools (on Google Apps Script) are a set of tools to aid in the
rubric management of codePost courses. In particular, users may add the
Powertools as a library to a Google Apps Script project bound to a Google Sheet,
using custom menu options to easily import and export rubrics.

This file describes the process of using the codePost Powertools library in your
own Spreadsheet. For detailed descriptions on the provided functions, see the
[API reference](APIReference.md).

## codePost API

To properly use the Powertools, specifically the Sheets which use the
Powertools, you must know some resources from the
[codePost API](https://docs.codepost.io/reference/the-rubric-category-object).
In particular, look at the Rubric Category and Rubric Comment objects for a list
of their fields, some of which are required and some of which are optional. If
you regularly work with codePost rubrics, most of the fields should already be
familiar to you.

## Client Project

The Powertools are written as a library which you can add to a Google Apps
Script project bound to a Google Sheet. Access the project (which will be
automatically created) from the _Extensions > Apps Script_ menu of a
Spreadsheet.

(Note that the project must be bound to the Spreadsheet you want to work with.
If you did the above from the appropriate Spreadsheet, you're good to go.)

### Add the Powertools Library

You should by default be in the _Editor_ tab. If not, go to it.

Under the _Libraries_ section, click the add button. Enter the following as the
Script ID:

```text
1w-ocEuMf4xcp9ygSSCf4KxzCvBkiUq6YXwUmEa0y0XugCCbST2kP1Ar-
```

After clicking the "Look up" button, you should see the library "codePost
Powertools". Select the most recent version and set the identifier as
"Powertools". (You can set the identifier as whatever you want, but the
[example client](#example-client) uses "Powertools".) Click the "Add" button.

### Set Scope Permissions

<!-- todo: might be unnecessary if i get the library verified -->

The Powertools manipulates the Spreadsheet it is bound to. As such, it requires
the `"https://www.googleapis.com/auth/spreadsheets.currentonly"` scope.

Additionally, the Powertools makes external requests to the codePost API (but
no other endpoints). As such, it requires the
`"https://www.googleapis.com/auth/script.external_request"` scope.

To set these permissions, go to _Project Settings_. Under _General Settings_,
check the checkbox _Show "appsscript.json" manifest file in editor_. Go back to
the _Editor_, select the `appsscript.json` file, and enter the above scopes as
values in an array with the key `"oauthScopes"`. Your `appsscript.json` file
should look like the following:

```json
{
  "timeZone": "America/New_York",
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "dependencies": {
    "libraries": [
      {
        "userSymbol": "Powertools",
        "version": "X",
        "libraryId": "1w-ocEuMf4xcp9ygSSCf4KxzCvBkiUq6YXwUmEa0y0XugCCbST2kP1Ar-"
      }
    ]
  },
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets.currentonly",
    "https://www.googleapis.com/auth/script.external_request"
  ]
}
```

### Example Client

An example client is provided in [`ExampleClient.js`](ExampleClient.js). The
`importRubric()` and `exportRubric()` functions should be customized to your
specific use cases. If you wish, you may even customize the entire thing. See
the [API reference](APIReference.md) for details on how to use the provided
functions.

The rest of this documentation will describe steps as if you are using the
example client. It might be helpful to follow along with it for your learning.

## Powertools Config

There is some information that the Powertools will need to know that is unlikely
to change. Therefore, it is easiest to define it through a config than to pass
that information around as parameters. In particular, the following 3 properties
are expected:

1. `API_KEY`: Your
   [codePost API key](https://docs.codepost.io/reference/authentication), for
   making requests to the codePost API.
2. `INFO_SHEET`: The name of the [Info Sheet](#info-sheet).
3. `TEMPLATE_SHEET` (optional): The name of the
   [Template Sheet](#template-sheet-optional).

Use the `configSet()` function to set these properties.

## Info Sheet

Your spreadsheet must have an Info Sheet, which contains information about the
codePost course the sheet is for (the name of the course, and optionally, the
period of the course).

Although the Info Sheet itself is not hardcoded into the Powertools (i.e., you
must define the name of the Info Sheet in the Powertools config), the cells
where the required information is expected to be is fixed. Specifically, the
sheet is expected to have the following format:

|       | A             | B               |
| ----- | ------------- | --------------- |
| **1** | Course Name   | _COURSE_NAME_   |
| **2** | Course Period | _COURSE_PERIOD_ |

The values in column `A` don't matter; only the values in `B1:2` will be read.

Note that the course period is optional, and the first course found in your list
of courses (revealed by your API key) that matches the given criteria will be
returned. It is recommended to include the course period anyway.

## Rubric Sheets

The Sheets you use to represent a rubric can be highly customized to your needs.
However, there are still some hardcoded expectations.

Column `A` is for metadata and should be left blank. (It is recommended to hide
the column.) The id of the assignment of that Sheet should be in cell `A1`. You
must have a header row (default is row `2`).

There are two ways to create a rubric on a Sheet:

1. Create the rubric yourself from scratch.
2. Export an existing rubric from codePost into the Sheet, then edit it.

### Template Sheet (optional)

The "Get course assignments" menu item (which calls `getCourseAssignments()`)
will fetch all the assignments in the given codePost course (in the Info Sheet),
list them in the Info Sheet, and optionally create sheets for each assignment,
including the assignment id and assignment name in the following format:

|       | A               | B                             |
| ----- | --------------- | ----------------------------- |
| **1** | _ASSIGNMENT_ID_ | Assignment: _ASSIGNMENT_NAME_ |

If you want Sheets to be created for each assignment, you are able to customize
what that sheet looks like. In particular, you can create a Template Sheet,
passing in its name to the `TEMPLATE_SHEET` config property. A copy of the Sheet
will be created for each assignment. If you don't create a Template Sheet, don't
specify what it is, or the Sheet is not found, then a default will be created.

If a Sheet already exists for an assignment (detected through a Sheet name that
is the same as the assignment name), you will have the option to either replace
that Sheet or create a new Sheet. Replacing the Sheet just means that the
assignment id and assignment name will be updated in cells `A1:2`, and the rest
of the Sheet will remain unchanged.

### Export a Rubric

The _Export rubric from codePost_ menu item will ask for the id of the
assignment you wish to export (you can find out the assignment ids from the
Info Sheet) and whether you want to count the instances of each rubric comment,
then create a Sheet with the name "_ASSIGNMENT_NAME_ [e]". (The "[e]" is a
marker that this Sheet was exported.)

If a Sheet already exists with the same name, you will have the option to either
replace that Sheet or create a new Sheet. Replacing the Sheet will completely
clear it.

Exported Sheets will have the default format. That is, column `A` will be hidden and row `2` will be used for headers. There is currently no way to change this.

### Import a Rubric

The _Import current rubric to codePost_ menu item imports the rubric in the
current Sheet (the active Sheet when the menu item is clicked) into codePost.

Although the `processCurrentSheet()` function is used in the example client,
there is also a `processSheet()` function which takes the name of the Sheet to
process as the first parameter. See the API reference for a more detailed
description of what these functions do.

### Base Rubric Sheets

You may have a desire to always include certain comments in every assignment.
For example, say you had a set of rubric comments on code style. However,
the students might not have learned about some concepts yet (for example, in
intro CS courses, it might not be helpful to include comments about commenting
instance variables in week 1 when students are learning about `if` statements),
so you might only want to include certain comments after a certain assignment.
With the provided functions, this becomes very simple!

See the example client for an example. It first processes the "Base Rubric"
Sheet, only keeping the rubric comments whose "Week" value is less than or equal
to the current week (the week number of the current Sheet). Note that in this
example the user is expected to provide the current week number of each
assignment in cell `D1`, as well as define a week number for each comment in the
"Base Rubric". It then processes the current Sheet, combining them to produce
the final rubric to be imported.

## Powertools Exceptions

Powertools functions throw objects as exceptions. Each object has two
properties: `function`, where the error occurred, and `message`. The
`catchError()` decorator will catch exceptions and display them to the user
using an Apps Script `Ui` object.

If you wish to write your own error handler, make sure to handle the case of a
Powertools exception as well as the case of a regular error. For example, see
[`catchError()`](4_Frontend.js#L173).
