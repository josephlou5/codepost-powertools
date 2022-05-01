/*============================================================================*/
/* This is an example client for codePost Powertools on Google Apps Script.   */
/* It demonstrates importing and exporting rubrics, taking advantage of some  */
/* powerful features to highlight the customizability of this tool.           */
/*============================================================================*/

function getUi_() {
  return SpreadsheetApp.getUi();
}

function onOpen() {
  const ui = getUi_();
  ui.createMenu("Powertools")
    .addItem("Get course assignments", "getCourseAssignments")
    .addSeparator()
    .addItem("Import current rubric to codePost", "importRubric")
    .addItem("Export rubric from codePost", "exportRubric")
    .addSeparator()
    .addItem("Help", "Powertools.showHelp")
    .addToUi();

  config();
}

function config() {
  Powertools.configSet({
    API_KEY: "YOUR_API_KEY",
    INFO_SHEET: "Info",
    TEMPLATE_SHEET: "Template",
  });
}

let getCourseAssignments = Powertools.catchError(
  Powertools.getCourseAssignments
);

let importRubric = Powertools.catchError(function () {
  const sheetHeaders = {
    "Category": "category",
    "Max": "pointLimit",
    "Subcategory": "",
    "Name": "name",
    "Tier": "tier",
    "Points": "pointDelta",
    "Grader Caption": "text",
    "Explanation": "explanation",
    "Instructions": "instructionText",
    "Template?": "templateTextOn",
    "Example": "",
    "Notes": "",
  };
  const baseHeaders = { ...sheetHeaders, Week: "week" };

  function transform(row) {
    // delete rows with no category or comment names
    if (row.category === "" || row.name === "") return null;
    const { tier, templateTextOn, ...updated } = row;
    // combine tier with explanation text
    if (tier !== "") {
      updated.text = "\\[T" + tier + "\\] " + updated.text;
    }
    // template text on (accept "yes" and "x")
    if (["yes", "x"].includes(templateTextOn.toLowerCase())) {
      updated.templateTextOn = true;
    } else {
      updated.templateTextOn = false;
    }
    return updated;
  }

  // get the week value from the current week (cell D1)
  const currWeek = SpreadsheetApp.getActiveSheet().getRange("D1").getValue();
  function transformBase(row, index) {
    // delete rows that come after the current week number
    if (row.week > currWeek) return null;
    delete row.week;
    return transform(row, index);
  }

  const [a1, baseRubric] = Powertools.processSheet("Base Rubric", {
    headerRow: 2,
    headers: baseHeaders,
    transform: transformBase,
  });
  const [assignmentId, data] = Powertools.processCurrentSheet({
    headerRow: 2,
    headers: sheetHeaders,
    transform: transform,
  });
  const combined = Powertools.combineRubrics(baseRubric, data);
  const rubric = Powertools.processRubric(combined);
  Powertools.importRubric(assignmentId, rubric);
});

let exportRubric = Powertools.catchError(function () {
  const ui = getUi_();

  // ask for assignment id
  let response = ui.prompt(
    "Export rubric",
    "Enter the id of the assignment to export:",
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) {
    return;
  }
  const assignmentId = response.getResponseText();

  // ask about counting instances
  response = ui.alert(
    "Count instances",
    "Count instances of rubric comments?",
    ui.ButtonSet.YES_NO
  );
  if (response === ui.Button.CLOSE) {
    return;
  }
  const countInstances = response === ui.Button.YES;

  // ask about finalized only
  let finalizedOnly = false;
  if (countInstances) {
    const response = ui.alert(
      "Count instances",
      "Count rubric comment instances in finalized submissions only?",
      ui.ButtonSet.YES_NO
    );
    if (response === ui.Button.CLOSE) {
      return;
    }
    finalizedOnly = response === ui.Button.YES;
  }

  // export rubric to sheet
  const headers = {
    category: ["Category", 100],
    pointLimit: ["Max", 50],
    name: ["Name", 150],
    tier: ["Tier", 50],
    pointDelta: ["Points", 75],
    text: ["Grader Caption", 200],
    explanation: ["Explanation", 650],
    instructionText: ["Instructions", 300],
    isTemplate: ["Template?", 100],
  };
  Powertools.exportRubric(assignmentId, {
    headers: headers,
    countInstances: countInstances,
    finalizedOnly: finalizedOnly,
    transform: (row) => {
      const { templateTextOn, ...updated } = row;
      // remove help text and at most once
      delete updated.helpText;
      delete updated.atMostOnce;
      if (templateTextOn) {
        updated.isTemplate = "YES";
      } else {
        updated.isTemplate = "";
      }
      const match = updated.text.match(/\\\[T(\d+)\\\] /);
      if (match != null) {
        // extract tier
        updated.tier = match[1];
        // fix text
        updated.text = updated.text.slice(updated.text.indexOf(" ") + 1);
      }
      return updated;
    },
  });
});
