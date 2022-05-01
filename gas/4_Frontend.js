/*============================================================================*/
/* Helpers                                                                    */
/*============================================================================*/

function getUi_() {
  return SpreadsheetApp.getUi();
}

function alert_(title, message = "", buttons = "OK") {
  const ui = getUi_();
  const buttonSet = {
    OK: ui.ButtonSet.OK,
    OK_CANCEL: ui.ButtonSet.OK_CANCEL,
    YES_NO: ui.ButtonSet.YES_NO,
    YES_NO_CANCEL: ui.ButtonSet.YES_NO_CANCEL,
  }[buttons];
  ui.alert(title, message, buttonSet);
}

const YES_ = 0;
const NO_ = 1;
const CANCEL_ = 2;
function askYesNo_(title, message, cancellable = false) {
  const ui = getUi_();
  const buttonSet = cancellable
    ? ui.ButtonSet.YES_NO_CANCEL
    : ui.ButtonSet.YES_NO;
  const response = ui.alert(title, message, buttonSet);
  if (response === ui.Button.YES) return YES_;
  if (response === ui.Button.NO) return NO_;
  return CANCEL_; // close button also counts as cancel
}

function getSpreadsheet_() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

function getInfoSheet_() {
  const INFO_SHEET = configGet("INFO_SHEET");
  if (INFO_SHEET == null) {
    throw "Info sheet not set.";
  }
  const sheet = getSpreadsheet_().getSheetByName(INFO_SHEET);
  if (sheet === null) {
    throw `Could not find info sheet "${INFO_SHEET}".`;
  }
  return sheet;
}

function addSheet_(name, options = {}) {
  const ss = getSpreadsheet_();
  const index = ss.getNumSheets();
  try {
    return ss.insertSheet(name, index, options);
  } catch (e) {}
  let i = 1;
  while (true) {
    try {
      return ss.insertSheet(name + i, index, options);
    } catch (e) {}
    i++;
  }
}

function setTemplate_(sheet, headers, blankRows = 1) {
  blankRows = Math.max(blankRows, 1) - 1;

  // make only A1
  sheet.deleteRows(2, sheet.getMaxRows() - 1);
  sheet.deleteColumns(2, sheet.getMaxColumns() - 1);
  // set font and vertical alignment of entire sheet
  sheet
    .getRange("A1")
    .clear()
    .setFontFamily("Fira Code")
    .setFontSize(10)
    .setVerticalAlignment("middle");

  // add header rows and first blank row
  const headerLabels = Object.keys(headers);
  const numHeaders = headerLabels.length;
  if (numHeaders === 0) {
    // no headers, but create B column and 3 rows anyway
    sheet.insertColumnAfter(1).insertRowsAfter(1, 2);
  } else {
    const row1 = Array(numHeaders).fill("Assignment: Name", 0, 1).fill("", 1);
    sheet
      .getRange(1, 2, 3, numHeaders)
      .setValues([row1, headerLabels, Array(numHeaders).fill("")]);

    // set column widths
    Object.values(headers).forEach((width, col) => {
      // 1-indexed, and start at column B
      sheet.setColumnWidth(col + 2, width);
    });
  }

  // style the header rows (except the first column)
  sheet
    .getRange("B1:2")
    .setBackgroundRGB(109, 177, 84) // codePost green
    .setFontWeight("bold")
    .setFontColor("white");
  sheet.getRange("B2:2").setHorizontalAlignment("center");

  // style rest of the sheet (inserted rows inherit style)
  sheet.getRange("B3:3").setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  // insert rest of the blank rows
  if (blankRows > 0) {
    sheet.insertRowsAfter(3, blankRows);
  }

  // freeze the header rows
  sheet.setFrozenRows(2);
  // hide the id column
  sheet.hideColumns(1);
}

function createTemplate_(name, headers, blankRows = 1) {
  const sheet = addSheet_(name);
  setTemplate_(sheet, headers, blankRows);
  return sheet;
}

/*============================================================================*/
/* Frontend methods                                                           */
/*============================================================================*/

/**
 * Get the value of the given property.
 *
 * @param {string} key The property key to get.
 * @returns {?string} The value of the property, or null if it doesn't exist.
 */
function configGet(key) {
  const props = PropertiesService.getDocumentProperties();
  return props.getProperty(key);
}

/**
 * Save the values of the given properties.
 *
 * @param {Object<string,string>} properties The properties to be set.
 */
function configSet(properties) {
  const props = PropertiesService.getDocumentProperties();
  props.setProperties(properties);
}

/**
 * Delete the bindings of the given properties.
 * If no properties are given, all properties will be deleted.
 *
 * @param {Array<string>} deleting The properties to be deleted.
 */
function configDelete(deleting = []) {
  const props = PropertiesService.getDocumentProperties();
  if (deleting.length === 0) {
    props.deleteAllProperties();
  } else {
    for (const key of deleting) {
      props.deleteProperty(key);
    }
  }
}

/**
 * A decorator for catching exceptions thrown by Powertools functions and
 * properly displaying them to the user.
 *
 * @param {function} func The function to decorate.
 */
function catchError(func) {
  return function (...args) {
    try {
      return func(...args);
    } catch (e) {
      let title = "Error";
      let message;
      if (e.function == null) {
        message = String(e);
      } else {
        title += ": " + e.function;
        message = e.message;
      }
      alert_(title, message);
      return null;
    }
  };
}

/**
 * Get the course from the Info Sheet, then fetch all the course's assignments.
 * Asks the user if they want to create sheets for each assignment.
 *
 * @throws Throws an exception if the Info Sheet is not set.
 * @throws Throws an exception if the Info Sheet could not be found.
 * @throws Throws an exception if the Info Sheet is missing the course name.
 */
function getCourseAssignments() {
  function createTemplateSheet() {
    const HEADERS = {
      "Category": 100,
      "Max": 50,
      "Subcategory": 130,
      "Name": 150,
      "Points": 75,
      "Grader Caption": 200,
      "Explanation": 650,
      "Instructions": 300,
      "Template?": 100,
      "Example": 100,
      "Notes": 500,
    };
    return createTemplate_("_temp_template", HEADERS, 10);
  }

  const ss = getSpreadsheet_();

  let infoSheet;
  try {
    infoSheet = getInfoSheet_();
  } catch (e) {
    throw error_("getCourseAssignments()", e);
  }

  // look for course values
  const values = infoSheet.getRange("B1:B2").getValues();
  const courseName = values[0][0].trim();
  // allow course period to be null
  const coursePeriod = values[1][0].trim() || null;
  if (courseName === "") {
    throw error_("getCourseAssignments()", "Info Sheet: missing course name");
  }

  // get course and assignments
  const course = Course.getByName(courseName, coursePeriod);
  const assignments = Assignment.getByIds(course.assignments).sort(
    (a, b) => a.sortKey - b.sortKey
  );
  // assignment name -> assignment id
  const assignmentIds = Object.fromEntries(
    assignments.map((a) => [a.name, a.id])
  );

  // populate info sheet
  if (infoSheet.getColumnWidth(1) < 125) infoSheet.setColumnWidth(1, 125);
  if (infoSheet.getColumnWidth(2) < 100) infoSheet.setColumnWidth(2, 100);
  infoSheet
    .getRange(4, 1, 1, 2)
    .setFontWeight("bold")
    .setValues([["Assignment Name", "Assignment ID"]]);
  infoSheet
    .getRange(5, 1, assignments.length, 2)
    .setFontWeight("normal")
    .setValues(Object.entries(assignmentIds));

  const createAssignmentSheets = askYesNo_(
    "Create assignment sheets?",
    'Selecting "Yes" will create a template sheet (or replace existing ' +
      "sheets) with the assignment id and name embedded in the sheet."
  );
  if (createAssignmentSheets !== YES_) return;

  // populate assignment sheets
  // create new assignment sheets or replace existing ones
  const assignmentSheets = {};
  let couldReplace = false;
  ss.getSheets().forEach((sheet) => {
    const name = sheet.getName();
    // don't replace info sheet
    if (name === infoSheet.getName()) return;
    // not an assignment name, so skip
    if (!hasProp_(assignmentIds, name)) return;
    // replacing first sheet, so skip
    if (hasProp_(assignmentSheets, name)) return;
    // save this sheet
    assignmentSheets[name] = sheet;
    couldReplace = true;
  });
  let createSheets = true;
  if (couldReplace) {
    const replaceExistingSheets = askYesNo_(
      "Replace existing sheets?",
      'Selecting "No" will create new sheets.',
      true
    );
    if (replaceExistingSheets === CANCEL_) return;
    if (replaceExistingSheets === YES_) {
      createSheets = false;
    }
  }

  // get template sheet
  let TEMPLATE_SHEET = ss.getSheetByName(configGet("TEMPLATE_SHEET"));
  let deleteTemplate = false;
  if (TEMPLATE_SHEET == null) {
    TEMPLATE_SHEET = createTemplateSheet();
    deleteTemplate = true;
  }

  // create sheets with template and put assignment info
  // FUTURE: change order of sheets to match order of assignments
  Object.entries(assignmentIds).forEach(([name, id]) => {
    let sheet;
    if (!createSheets && hasProp_(assignmentSheets, name)) {
      sheet = assignmentSheets[name];
    } else {
      sheet = addSheet_(name, { template: TEMPLATE_SHEET });
    }
    sheet.getRange("A1:B1").setValues([[id, `Assignment: ${name}`]]);
  });

  // delete the created template sheet
  if (deleteTemplate) {
    ss.deleteSheet(TEMPLATE_SHEET);
  }
}

/**
 * Show the help message in an alert box.
 */
function showHelp() {
  alert_(
    "Powertools Help",
    "Please see the Powertools repository on GitHub for help and " +
      "documentation:\n\n" +
      "https://github.com/josephlou5/codepost-powertools/blob/main/gas/Help.md"
  );
}
