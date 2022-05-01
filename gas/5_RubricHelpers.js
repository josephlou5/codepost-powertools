/**
 * Processes the data in the given Sheet.
 *
 * @param {string} sheetName The name of the sheet.
 * @param {Object} options Extra options.
 * @param {number} options.headerRow The header row (1-indexed). Default is 1.
 *  All rows before the header row are ignored.
 *  Any column with an empty header will be ignored.
 * @param {Object} options.headers A mapping from headers in the sheet to keys
 *  in the resulting objects.
 * @param {callback} options.transform A function to transform the data.
 *  It is given as parameters each row object and index.
 *  It should return a transformed object, or null if the row should be removed.
 * @returns {Array<number,Array<Object>>} The value in cell A1 and an array of
 *  objects, where each object represents a row in the Sheet with the headers as
 *  the keys.
 * @throws Throws an exception if `headerRow` is not at least 1.
 * @throws Throws an exception if the sheet is not found.
 * @throws Throws an exception if there are duplicate headers.
 */
function processSheet(
  sheetName,
  { headerRow = 1, headers = null, transform = null } = {}
) {
  if (headerRow < 1) {
    throw error_("processSheet()", "`headerRow` must be at least 1");
  }
  if (headers == null) headers = {};
  delete headers[""]; // don't allow keeping empty headers
  if (transform == null) transform = (row) => row;

  // get values from sheet
  const sheet = getSpreadsheet_().getSheetByName(sheetName);
  if (sheet == null) {
    throw error_("processSheet()", `sheet "${sheetName}" not found`);
  }
  const values = sheet.getDataRange().getValues();

  // get value in cell A1 (should be assignment id)
  const cellA1 = isNumber_(values[0][0]) ? Number(values[0][0]) : values[0][0];

  // get header keys
  const keys = {};
  values[headerRow - 1].forEach((header, i) => {
    header = String(header).trim();
    // get the proper key name
    let key;
    if (hasProp_(headers, header)) {
      key = String(headers[header]).trim();
    } else {
      key = header;
    }
    // ignore empty keys
    if (key === "") return;
    // check for duplicates
    if (hasProp_(keys, key)) {
      throw error_("processSheet()", `duplicate header "${header}"`);
    }
    keys[key] = i;
  });
  const headerKeys = Object.entries(keys);

  // remove header rows
  values.splice(0, headerRow);

  // process values
  const processed = values.flatMap((row, index) => {
    const rawValues = Object.fromEntries(
      headerKeys.map(([header, i]) => [header, row[i]])
    );
    const values = transform(rawValues, index);
    if (values == null) return [];
    return [values];
  });

  return [cellA1, processed];
}

/**
 * Processes the data in the current Sheet.
 *
 * @param {Object} options The options.
 * @param {number} options.headerRow The header row (1-indexed). Default is 1.
 *  All rows before the header row are ignored.
 *  Any column with an empty header will be ignored.
 * @param {Object} options.headers A mapping from headers in the sheet to keys
 *  in the resulting objects.
 * @param {callback} options.transform A function to transform the data.
 *  It is given as parameters each row object and index.
 *  It should return a transformed object, or null if the row should be removed.
 * @returns {Array<number,Array<Object>>} The value in cell A1 and an array of
 *  objects, where each object represents a row in the Sheet with the headers as
 *  the keys.
 * @throws Throws an exception if `headerRow` is not at least 1.
 * @throws Throws an exception if there are duplicate headers.
 */
function processCurrentSheet(options) {
  const sheet = SpreadsheetApp.getActiveSheet();
  try {
    return processSheet(sheet.getName(), options);
  } catch (e) {
    if (e.function == null) {
      throw error_("processCurrentSheet()", e);
    } else {
      throw error_(`processCurrentSheet(): ${e.function}`, e.message);
    }
  }
}

/**
 * Combines rubrics, overriding comments with the same name with the last such
 * comment. Note that replaced comments only need to have the same name; all
 * other values may change, including the category.
 *
 * @param {Array<Array<Object>>} rubrics The rubrics to combine.
 * @returns {Array<Object>} The combined data.
 */
function combineRubrics(...rubrics) {
  // comment name -> index
  const seenNames = {};
  const combined = [];
  for (const row of rubrics.flat()) {
    if (row.name != null) {
      if (hasProp_(seenNames, row.name)) {
        // replace previous
        combined[seenNames[row.name]] = row;
        continue;
      }
      // save index
      seenNames[row.name] = combined.length;
    }
    combined.push(row);
  }
  return combined;
}

/**
 * Processes the given data to produce a rubric for `importRubric()`.
 *
 * @param {Array<Object>} data An array of objects, where each object
 *  represents a rubric comment with the appropriate keys.
 *  Each rubric comment must have the fields "category", "name", "pointDelta",
 *  and "text". The other codePost fields of a category will be saved the first
 *  time the "category" is seen. Each comment may also have the optional
 *  codePost fields. All other fields will be ignored.
 * @param {boolean=} removeInvalid Whether to remove the invalid rows rather
 *  than throwing an exception. Default is false.
 * @returns {Array<Object>} The processed categories in the proper format
 *  to be passed to `importRubric()`.
 * @throws Throws an exception if `removeInvalid` is false and any object does
 *  not have the required fields.
 */
function processRubric(data, removeInvalid = false) {
  function makeString(val) {
    return String(val);
  }
  function makeBool(val) {
    if (val) return true;
    else return false;
  }
  function makeNumAllowNull(val) {
    if (val == null || val === "") return null;
    return Number(val);
  }

  const CATEGORY_OPTIONAL = [
    ["pointLimit", makeNumAllowNull],
    ["helpText", makeString],
    ["atMostOnce", makeBool],
  ];
  const COMMENT_REQUIRED = [
    ["name", makeString],
    ["pointDelta", makeNumAllowNull],
    ["text", makeString],
  ];
  const COMMENT_OPTIONAL = [
    ["explanation", makeString],
    ["instructionText", makeString],
    ["templateTextOn", makeBool],
  ];

  const categories = {};
  data.forEach((row, index) => {
    if (!hasProp_(row, "category") || row.category === "") {
      if (removeInvalid) return; // skip
      throw error_("processRubric()", `comment ${index}: missing "category"`);
    }
    const category = makeString(row.category);
    // create new category
    if (!hasProp_(categories, category)) {
      // save the other category args as well
      const categoryArgs = { name: category };
      for (const [field, make] of CATEGORY_OPTIONAL) {
        if (!hasProp_(row, field)) continue;
        categoryArgs[field] = make(row[field]);
      }
      categoryArgs.comments = [];
      categories[category] = categoryArgs;
    }
    // get comment args
    const comment = {};
    for (const [field, make] of COMMENT_REQUIRED) {
      if (!hasProp_(row, field) || row[field] === "") {
        if (removeInvalid) return; // skip
        throw error_("processRubric()", `comment ${index}: missing "${field}"`);
      }
      comment[field] = make(row[field]);
    }
    for (const [field, make] of COMMENT_OPTIONAL) {
      if (!hasProp_(row, field)) continue;
      comment[field] = make(row[field]);
    }
    // save comment in category
    categories[category].comments.push(comment);
  });

  // remove categories with no comments
  if (removeInvalid) {
    for (const category in categories) {
      if (categories[category].comments.length === 0) {
        delete categories[category];
      }
    }
  }

  return Object.values(categories);
}
