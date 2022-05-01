# API Reference

## codePost API

To properly use the Powertools, specifically the Sheets which use the
Powertools, you must know some resources from the
[codePost API](https://docs.codepost.io/reference/the-rubric-category-object).
In particular, look at the Rubric Category and Rubric Comment objects for a list
of their fields, some of which are required and some of which are optional. If
you regularly work with codePost rubrics, most of the fields should already be
familiar to you.

## Miscellaneous

### `catchError(func)`

A decorator for catching exceptions thrown by Powertools functions and properly
displaying them to the user.

### `showHelp()`

Show the help message in an alert box.

## Powertools Config

### `configGet(key)`

Get the value of the given property.

#### Parameters

| Name  | Type     | Description              |
| ----- | -------- | ------------------------ |
| `key` | `string` | The property key to get. |

#### Returns

Type: `?string`

The value of the property, or `null` if it doesn't exist.

### `configSet(properties)`

Save the values of the given properties.

#### Parameters

| Name         | Type                    | Description               |
| ------------ | ----------------------- | ------------------------- |
| `properties` | `Object<string,string>` | The properties to be set. |

### `configDelete()`

### `configDelete(deleting)`

Delete the bindings of the given properties.

If no properties are given, all properites will be deleted.

#### Parameters

| Name       | Type            | Description                   |
| ---------- | --------------- | ----------------------------- |
| `deleting` | `Array<string>` | The properties to be deleted. |

## Course Assignments

### `getCourseAssignments()`

Get the course from the Info Sheet, then fetch all the course's assignments.
Asks the user if they want to create sheets for each assignment.

#### Throws

- Throws an exception if the Info Sheet is not set.
- Throws an exception if the Info Sheet could not be found.
- Throws an exception if the Info Sheet is missing the course name.

## Import Rubric

### `processSheet(sheetName)`

### `processSheet(sheetName, options)`

### `processCurrentSheet()`

### `processCurrentSheet(options)`

Processes the data in the given Sheet, or the current Sheet.

The headers are extracted from the header row, then transformed according to the
`headers` mapping. Any column with an empty header will be ignored. (Map a
header to the empty string `""` to ignore that column.) All rows before the
header row are ignored. All the successive rows are assumed to have data.

Each row is turned into an object with the keys corresponding to the transformed
headers. The `transform()` function is given as parameters each row object and
index. It should return a transformed object, or `null` if the row should be
removed. An array of these resulting objects are returned.

The value in cell `A1` is also returned. This is assumed to be the assignment id
of the Sheet.

#### Parameters

| Name                | Type                    | Description                                                           |
| ------------------- | ----------------------- | --------------------------------------------------------------------- |
| `sheetName`         | `string`                | The name of the sheet.                                                |
| `options`           | `Object`                | Extra options.                                                        |
| `options.headerRow` | `number`                | The header row (1-indexed). Default is `1`.                           |
| `options.headers`   | `Object<string,string>` | A mapping from headers in the sheet to keys in the resulting objects. |
| `options.transform` | `callback`              | A function to transform the data.                                     |

#### Throws

- Throws an exception if `headerRow` is not at least 1.
- Throws an exception if the sheet is not found.
- Throws an exception if there are duplicate headers.

#### Returns

Type: `[number,Array<Object>]`

The value in cell `A1` and an array of objects, where each object represents a
row in the Sheet with the headers as the keys.

### `combineRubrics(...rubrics)`

Combines rubrics, overriding comments with the same name with the last such
comment. Note that replaced comments only need to have the same name; all other
values may change, including the category.

The order of the comments is preserved in the order they were first seen. The
last version of a comment with the same `name` field will be in that position.

#### Parameters

| Name        | Type            | Description             |
| ----------- | --------------- | ----------------------- |
| `rubrics[]` | `Array<Object>` | The rubrics to combine. |

#### Returns

Type: `Array<Object>`

The combined data.

### `processRubric(data)`

Processes the given data to produce a rubric for `importRubric()`.

Each object in `data` must have the following fields:

- `category`: the name of the category this comment belongs to
- `name`: the comment name
- `pointDelta`: the point value
- `text`: the grader caption

The optional codePost fields of a category will be saved the first time the
category name is seen:

- `pointLimit`
- `helpText`
- `atMostOnce`

The optional codePost fields of a comment will also be saved for each comment:

- `explanation`
- `instructionText`
- `templateTextOn`

All other fields will be ignored.

#### Parameters

| Name            | Type            | Description                                                                                   |
| --------------- | --------------- | --------------------------------------------------------------------------------------------- |
| `data`          | `Array<Object>` | An array of objects, where each object represents a rubric comment with the appropriate keys. |
| `removeInvalid` | `boolean`       | Whether to remove the invalid rows rather than throwing an exception. Default is `false`.     |

#### Throws

- Throws an exception if `removeInvalid` is false and any object does not have
  the required fields.

#### Returns

Type: `Array<Object>`

The processed categories in the proper format to be passed to `importRubric()`.

### `importRubric(assignmentId, rubric)`

### `importRubric(assignmentId, rubric, options)`

Import a rubric into codePost.

Each element of `rubric` must have the following fields:

- `name`: the category name
- `comments`: the comments of the category

Each element may also have the optional category fields:

- `pointLimit`
- `helpText`
- `atMostOnce`

Each element of `rubric[].comments` must have the following fields:

- `name`: the comment name
- `pointDelta`: the point value
- `text`: the grader caption

Each element may also have the optional comment fields:

- `explanation`
- `instructionText`
- `templateTextOn`

All other fields will be ignored.

If the given assignment has existing submissions, a dialog will ask the user if
they wish to continue. (Changing the rubric will affect all comments that are
already applied.)

#### Parameters

| Name                  | Type            | Description                                                                                          |
| --------------------- | --------------- | ---------------------------------------------------------------------------------------------------- |
| `assignmentId`        | `number`        | The assignment id.                                                                                   |
| `rubric`              | `Array<Object>` | The rubric data. Each element should be an object representing a rubric category.                    |
| `rubric[].comments`   | `Array<Object>` | The comments of the rubric category. Each element should be an object representing a rubric comment. |
| `options`             | `Object`        | Extra options.                                                                                       |
| `options.wipe`        | `boolean`       | Whether to wipe the existing rubric first.                                                           |
| `options.deleteExtra` | `boolean`       | Whether to delete extra codePost comments that are not in the given rubric.                          |

#### Throws

- Throws an exception if `assignmentId` is invalid.
- Throws an exception if an object is missing required fields.
- Throws an exception if a rubric category name is not unique.
- Throws an exception if a rubric comment name is not unique.
- Throws an exception if the assignment is not found.
- Throws an exception if the user does not have access to the assignment.

## Export Rubric

### `exportRubric(assignmentId)`

### `exportRubric(assignmentId, options)`

Export a rubric from codePost into a Sheet named "_ASSIGNMENT_NAME_ [e]".

If a Sheet with that name exists, asks the user if they want to replace the
existing Sheet.

The rubric categories and comments are fetched from codePost. Each comment is
turned into an object with the following fields:

- `category`: the name of the category this comment belongs to
- `pointLimit`: the category point limit
- `helpText`
- `atMostOnce`
- `name`: the comment name
- `pointDelta`: the point value
- `text`: the grader caption
- `explanation`
- `instructionText`
- `templateTextOn`

The `transform()` function is given as parameters each comment object and index.
It should return a transformed object with keys corresponding to the ones given
in the `headers` option. Any extra keys will force new columns to be created,
whose header title is simply the field name. If the result of the `transform()`
function is `null`, the original rubric comment object will be used. These
resulting objects are then displayed as rows in the Sheet.

The `headers` option must be a mapping with the keys corresponding to the given
list above. (To delete a field from being shown in the exported Sheet, remove
it from the returned object in `transform()`.) The values can either be a
string, which is the header title, or it can be an array of length 2, where the
first element is the header title and the second element is the width of the
column. The default column width is 100.

If `countInstances` is `true`, five additional columns will be appended to the
end: the total number of instances, the number of upvotes, the percentage of
upvotes, the number of downvotes, and the percentage of downvotes.

#### Parameters

| Name                     | Type       | Description                                                                                                                                                 |
| ------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assignmentId`           | `number`   | The assignment id.                                                                                                                                          |
| `options`                | `Object`   | Extra options.                                                                                                                                              |
| `options.transform`      | `callback` | A function to transform the data.                                                                                                                           |
| `options.headers`        | `Object`   | A mapping from keys of the rubric comments to headers in the Sheet, or an array of the header string and the column width. The default column width is 100. |
| `options.countInstances` | `boolean`  | Whether to count the instances of each rubric comment. Default is `false`.                                                                                  |
| `options.finalizedOnly`  | `boolean`  | Whether to only count the instances of comments in finalized submissions. Default is `false`.                                                               |

#### Throws

- Throws an exception if `assignmentId` is invalid.
- Throws an exception if the assignment is not found.
- Throws an exception if the user does not have access to the assignment.
