/**
 * Helper function to export a rubric.
 */
function exportRubric_(
  assignmentId,
  transform,
  headers,
  countInstances,
  finalizedOnly
) {
  if (assignmentId == null) {
    throw "`assignmentId`: missing";
  }
  if (!isNumber_(assignmentId)) {
    throw "`assignmentId`: invalid (not a number)";
  }

  if (transform == null) transform = (row) => row;
  // relies on the fact that Set retains insertion order
  const headerFields = new Set();
  const headerWidths = {};
  if (headers != null) {
    for (const [field, headerInfo] of Object.entries(headers)) {
      headerFields.add(field);
      if (Array.isArray(headerInfo)) {
        const [header, width] = headerInfo;
        headerWidths[header] = width;
      } else {
        // default width of 100
        headerWidths[headerInfo] = 100;
      }
    }
  }

  // get assignment
  const assignment = Assignment.getById(assignmentId);
  const assigmentName = assignment.name;
  // make difference between exported sheets and sheets for importing
  const sheetName = `${assigmentName} [e]`;

  // create new sheet or replace existing one
  let sheet = getSpreadsheet_().getSheetByName(sheetName);
  let createSheet = true;
  if (sheet != null) {
    const replaceExistingSheet = askYesNo_(
      `Replace existing sheet for assignment "${assigmentName}"?`,
      `Note: This will replace the sheet "${sheetName}".\n\n` +
        'Selecting "No" will create a new sheet.',
      true
    );
    if (replaceExistingSheet === CANCEL_) return;
    if (replaceExistingSheet === YES_) {
      createSheet = false;
    }
  }

  // get existing rubric
  // category id -> category
  const cpCategories = Object.fromEntries(
    RubricCategory.getByIds(assignment.rubricCategories).map((category) => [
      category.id,
      category,
    ])
  );
  // comment id -> comment
  const cpComments = Object.fromEntries(
    RubricComment.getByIds(
      Object.values(cpCategories).flatMap((category) => category.rubricComments)
    ).map((comment) => [comment.id, comment])
  );

  // process all comments with transform
  // also find any extra headers
  const processed = Object.values(cpComments).map((comment, index) => {
    const category = cpCategories[comment.category];
    const rawValues = {
      category: category.name,
      pointLimit: category.pointLimit,
      helpText: category.helpText,
      atMostOnce: category.atMostOnce,
      name: comment.name,
      pointDelta: comment.pointDelta,
      text: comment.text,
      explanation: comment.explanation,
      instructionText: comment.instructionText,
      templateTextOn: comment.templateTextOn,
    };
    const values = transform({ ...rawValues }, index) ?? rawValues;
    Object.keys(values).forEach((field) => {
      headerFields.add(field);
      if (!hasProp_(headerWidths, field)) {
        // add header with column width 100
        headerWidths[field] = 100;
      }
    });
    return values;
  });
  const finalHeaders = Array.from(headerFields);
  const numHeaders = finalHeaders.length;

  // format comments as rows (include comment ids)
  const commentRows = Object.keys(cpComments).map((id, i) => {
    const comment = processed[i];
    const row = finalHeaders.map((field) => comment[field] ?? "");
    row.unshift(id);
    return row;
  });

  if (createSheet) {
    sheet = createTemplate_(sheetName, headerWidths);
  } else {
    setTemplate_(sheet, headerWidths);
  }
  // set assignment id and name
  sheet
    .getRange("A1:B1")
    .setValues([[assignmentId, `Assignment: ${assigmentName}`]]);
  // put comments in sheet
  sheet
    .getRange(3, 1, commentRows.length, 1 + numHeaders)
    .setValues(commentRows);

  if (countInstances) {
    // 1 offset for id columns + offset for headers
    const instancesCol = 1 + numHeaders + 1;

    // create instances columns
    sheet
      .getRange(2, instancesCol, 1, 5)
      .setValues([["Instances", "Upvote", "", "Downvote", ""]]);
    // merge upvote/downvote columns
    sheet.getRange(2, instancesCol + 1, 1, 2).merge();
    sheet.getRange(2, instancesCol + 3, 1, 2).merge();
    // set number formats for percent columns
    sheet
      .getRange(3, instancesCol + 2, commentRows.length, 1)
      .setNumberFormat("0.0%");
    sheet
      .getRange(3, instancesCol + 4, commentRows.length, 1)
      .setNumberFormat("0.0%");
    // set column widths
    sheet.setColumnWidths(instancesCol, 5, 75);

    // comment id -> [total, upvoted, downvoted]
    const instances = Object.fromEntries(
      Object.keys(cpComments).map((id) => [id, [0, 0, 0]])
    );

    // count all comments
    Assignment.getAllComments(assignmentId, finalizedOnly).forEach(
      (comment) => {
        if (comment.rubricComment == null) return;
        const counts = instances[comment.rubricComment];
        counts[0]++;
        if (comment.feedback === 1) counts[1]++;
        else if (comment.feedback === -1) counts[2]++;
      }
    );

    // put in sheet
    const instancesFormatted = Object.values(instances).map(
      ([total, upvotes, downvotes]) => {
        if (total === 0) {
          return [0, "", "", "", ""];
        } else {
          return [
            total,
            upvotes,
            upvotes / total,
            downvotes,
            downvotes / total,
          ];
        }
      }
    );
    sheet
      .getRange(3, instancesCol, instancesFormatted.length, 5)
      .setValues(instancesFormatted);
  }
}

/**
 * Export a rubric from codePost into a Sheet named "ASSIGNMENT_NAME [e]".
 * If a Sheet with that name exists, asks the user if they want to replace the
 *   existing Sheet.
 *
 * @param {number} assignmentId The assignment id.
 * @param {Object} options Extra options.
 * @param {callback} options.transform A function to transform the data.
 *  It is given as parameters each rubric comment (before transforming to the
 *  headers) and its index.
 *  It should return a transformed object.
 *    If null, the original rubric comment will be used.
 *    Extra fields will force new columns to be created.
 * @param {Object} options.headers A mapping from keys of the rubric comments
 *  to headers in the Sheet.
 *  Each value should be the header string, or an array of the header string and
 *  the column width. The default column width is 100.
 * @param {boolean} options.countInstances Whether to count the instances of
 *  each rubric comment.
 *  Default is false.
 * @param {boolean} options.finalizedOnly Whether to only count the instances of
 *  comments in finalized submissions.
 *  If `countInstances` is false, has no effect.
 *  Default is false.
 * @throws Throws an exception if `assignmentId` is invalid.
 * @throws Throws an exception if the assignment is not found.
 * @throws Throws an exception if the user does not have access to the
 *  assignment.
 */
function exportRubric(
  assignmentId,
  {
    transform = null,
    headers = null,
    countInstances = false,
    finalizedOnly = false,
  } = {}
) {
  try {
    exportRubric_(
      assignmentId,
      transform,
      headers,
      countInstances,
      finalizedOnly
    );
  } catch (e) {
    if (e.function == null) {
      throw error_("exportRubric()", e);
    } else {
      throw error_(`exportRubric(): ${e.function}`, e.message);
    }
  }
}
