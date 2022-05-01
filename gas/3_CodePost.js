const COURSES_ = "courses/";
const ASSIGNMENTS_ = "assignments/";
const RUBRIC_CATEGORIES_ = "rubricCategories/";
const RUBRIC_COMMENTS_ = "rubricComments/";
// const SUBMISSIONS_ = "submissions/";
const FILES_ = "files/";
const COMMENTS_ = "comments/";

/**
 * Check and clean up the given args for creating/updating an object.
 *
 * @param {string} resource The resource type, for error messages.
 * @param {Object} required The required fields.
 * @param {Object} optional The optional fields.
 * @param {Object} args The args of the object.
 * @returns {Object} The args with additional fields removed.
 * @throws Throws an exception if `args` doesn't have all the required fields.
 */
function checkArgs_(resource, required, optional, args) {
  const functionName = `${resource}.checkArgs()`;
  if (args == null) {
    throw error_(functionName, "missing args");
  }
  const fixed = {};
  for (const [field, validate] of Object.entries(required)) {
    if (!hasProp_(args, field)) {
      throw error_(functionName, `"${field}": missing`);
    }
    try {
      validate(args[field]);
    } catch (e) {
      throw error_(functionName, `"${field}": ${e}`);
    }
    fixed[field] = args[field];
  }
  for (const [field, validate] of Object.entries(optional)) {
    if (!hasProp_(args, field)) continue;
    try {
      validate(args[field]);
    } catch (e) {
      throw error_(functionName, `"${field}": ${e}`);
    }
    fixed[field] = args[field];
  }
  return fixed;
}

class Validator {
  static alwaysValid(val) {}

  static validateNum(val) {
    if (Number.isNaN(val)) {
      throw "not a number";
    }
  }

  static validateInt(val) {
    Validator.validateNum(val);
    if (!Number.isInteger(val)) {
      throw "not an integer";
    }
  }

  static validateNonNeg(val) {
    Validator.validateNum(val);
    if (val < 0) {
      throw "not non-negative";
    }
  }

  static validateNonNegInt(val) {
    Validator.validateInt(val);
    if (val < 0) {
      throw "not non-negative";
    }
  }

  static validateNonEmpty(val) {
    if (val.trim() === "") {
      throw "invalid";
    }
  }

  static validateBool(val) {
    if (!(val === true || val === false)) {
      throw "not a boolean";
    }
  }
}

class Course {
  /**
   * Get a course by its name and period.
   * Returns the first match found in the user's list of courses.
   *
   * @param {string} name The name of the course.
   * @param {?string} period The period of the course.
   * @returns {Object} The course.
   * @throws Throws an exception if the course is not found.
   */
  static getByName(name, period = null) {
    const courses = fetchOne_("GET", COURSES_);
    for (const course of courses) {
      if (
        course.name === name &&
        (period == null || course.period === period)
      ) {
        return course;
      }
    }
    let courseDetails = `name "${name}"`;
    if (period != null) {
      courseDetails += ` and period "${period}"`;
    }
    throw error_(
      "Course.getByName()",
      `Could not find course with ${courseDetails}.`
    );
  }
}

class Assignment {
  /**
   * Get an assignment by its id.
   *
   * @param {number} assignmentId The assignment id.
   * @returns {Object} The assignment.
   * @throws Throws an exception if the assignment is not found.
   * @throws Throws an exception if the user does not have access to the
   *  assignment.
   */
  static getById(assignmentId) {
    const endpoint = `${ASSIGNMENTS_}${assignmentId}/`;
    return fetchOne_("GET", endpoint);
  }

  /**
   * Get assignments by ids.
   *
   * @param {Array<number>} ids The assignment ids.
   * @returns {Array<Object>} The assignments.
   * @throws Throws an exception if an assignment is not found.
   * @throws Throws an exception if the user does not have access to an
   *  assignment.
   */
  static getByIds(ids) {
    return fetch_("GET", ASSIGNMENTS_, ids);
  }

  /**
   * Get the submissions of an assignment.
   *
   * @param {number} assignmentId The assignment id.
   * @returns {Array<Object>} The submissions.
   * @throws Throws an exception if the assignment is not found.
   * @throws Throws an exception if the user does not have access to the
   *  assignment.
   */
  static getSubmissions(assignmentId) {
    const endpoint = `${ASSIGNMENTS_}${assignmentId}/submissions/`;
    return fetchOne_("GET", endpoint);
  }

  /**
   * Get the number of submissions of an assignment.
   *
   * @param {number} assignmentId The assignment id.
   * @returns {number} The number of submissions.
   * @throws Throws an exception if the assignment is not found.
   * @throws Throws an exception if the user does not have access to the
   *  assignment.
   */
  static getNumSubmissions(assignmentId) {
    return Assignment.getSubmissions(assignmentId).length;
  }

  /**
   * Get all the comments applied to submissions for an assignment.
   *
   * @param {number} assignmentId The assignment id.
   * @param {boolean=} finalizedOnly Whether to only include the comments in
   *  finalized submissions.
   *  Default is false.
   * @returns {Array<Object>} The comments.
   * @throws Throws an exception if the assignment is invalid.
   * @throws Throws an exception if any files are not found.
   * @throws Throws an exception if the user does not have access to a file.
   */
  static getAllComments(assignmentId, finalizedOnly = false) {
    const submissions = Assignment.getSubmissions(assignmentId);
    if (submissions.length === 0) return [];
    const fileIds = submissions.flatMap((submission) => {
      if (finalizedOnly && !submission.isFinalized) return [];
      return submission.files;
    });
    if (fileIds.length === 0) return [];
    const files = fetch_("GET", FILES_, fileIds);
    const commentIds = files.flatMap((file) => file.comments);
    if (commentIds.length === 0) return [];
    const comments = fetch_("GET", COMMENTS_, commentIds);
    return comments;
  }
}

class RubricCategory {
  /**
   * Get rubric categories by ids.
   *
   * @param {Array<number>} ids The rubric category ids.
   * @returns {Array<Object>} The rubric categories.
   * @throws Throws an exception if a rubric category is not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  category.
   */
  static getByIds(ids) {
    const categories = fetch_("GET", RUBRIC_CATEGORIES_, ids);
    // flip all pointLimit fields
    for (const category of categories) {
      // allow pointLimit to stay null
      if (category.pointLimit != null) {
        category.pointLimit = -category.pointLimit;
      }
    }
    return categories;
  }

  /**
   * Check and clean up the given args for creating/updating a rubric category.
   *
   * @param {Object} args The args of the rubric category.
   * @param {Object} options Extra options.
   * @param {boolean=} options.updating Whether the args are for updating.
   *  If false, makes all required fields optional.
   *  Default is false.
   * @param {boolean=} options.creating Whether the args are for creating.
   *  If false, excludes fields not given by the user.
   *  Default is false.
   * @returns {Object} The args with additional fields removed.
   * @throws Throws an exception if `args` doesn't have all the required fields.
   */
  static checkArgs(args, { updating = false, creating = false } = {}) {
    const REQUIRED = {
      assignment: Validator.validateNonNegInt,
      name: Validator.validateNonEmpty,
    };
    const OPTIONAL = {
      pointLimit: Validator.validateNum,
      helpText: Validator.alwaysValid,
      atMostOnce: Validator.validateBool,
      sortKey: Validator.validateNonNegInt,
    };
    if (updating) {
      for (const key in REQUIRED) {
        OPTIONAL[key] = REQUIRED[key];
        delete REQUIRED[key];
      }
    } else if (!creating) {
      delete REQUIRED.assignment;
    }
    const checked = checkArgs_("RubricCategory", REQUIRED, OPTIONAL, args);
    if (updating || creating) {
      // allow pointLimit to be null
      if (hasProp_(checked, "pointLimit") && checked.pointLimit != null) {
        // flip point limit
        checked.pointLimit = -checked.pointLimit;
      }
    }
    return checked;
  }

  /**
   * Create the given rubric categories.
   *
   * @param {Array<Object>} data The rubric categories.
   * @returns {Array<Object>} The created rubric categories.
   * @throws Throws an exception if an object is missing the required fields.
   * @throws Throws an exception if an assignment of the rubric categories is
   *  not found.
   * @throws Throws an exception if the user does not have access to an
   *  assignment of the rubric categories.
   */
  static createAll(data) {
    const creating = data.map((category) =>
      RubricCategory.checkArgs(category, { creating: true })
    );
    return fetch_("POST", RUBRIC_CATEGORIES_, creating);
  }

  /**
   * Update the given rubric categories.
   *
   * @param {Array<Object>} data The rubric categories.
   * @returns {Array<Object>} The updated rubric categories.
   * @throws Throws an exception if an object is missing the required fields.
   * @throws Throws an exception if a rubric category is not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  category.
   * @throws Throws an exception if an assignment of the rubric categories is
   *  not found.
   * @throws Throws an exception if the user does not have access to an
   *  assignment of the rubric categories.
   */
  static updateAll(data) {
    const updating = data.map((obj) => {
      return {
        id: obj.id,
        data: RubricCategory.checkArgs(obj.data, { updating: true }),
      };
    });
    return fetch_("PATCH", RUBRIC_CATEGORIES_, updating);
  }

  /**
   * Delete the given rubric categories.
   *
   * @param {Array<number>} ids The rubric category ids.
   * @throws Throws an exception if a rubric category is not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  category.
   */
  static deleteAll(ids) {
    fetch_("DELETE", RUBRIC_CATEGORIES_, ids);
  }
}

class RubricComment {
  /**
   * Get rubric comments by ids.
   *
   * @param {Array<number>} ids The rubric comment ids.
   * @returns {Array<Object>} The rubric comments.
   * @throws Throws an exception if a rubric comment is not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  comment.
   */
  static getByIds(ids) {
    const comments = fetch_("GET", RUBRIC_COMMENTS_, ids);
    // flip all pointDelta fields
    for (const comment of comments) {
      comment.pointDelta = -comment.pointDelta;
    }
    return comments;
  }

  /**
   * Check and clean up the given args for creating/updating a rubric comment.
   *
   * @param {Object} args The args of the rubric comment.
   * @param {Object} options Extra options.
   * @param {boolean=} options.updating Whether the args are for updating.
   *  If false, makes all required fields optional.
   *  Default is false.
   * @param {boolean=} options.creating Whether the args are for creating.
   *  If false, excludes fields not given by the user.
   *  Default is false.
   * @returns {Object} The args with additional fields removed.
   * @throws Throws an exception if `args` doesn't have all the required fields.
   */
  static checkArgs(args, { updating = false, creating = false } = {}) {
    const REQUIRED = {
      category: Validator.validateNonNegInt,
      // not actually required, but we will require it
      name: Validator.validateNonEmpty,
      pointDelta: Validator.validateNum,
      text: Validator.validateNonEmpty,
    };
    const OPTIONAL = {
      explanation: Validator.alwaysValid,
      instructionText: Validator.alwaysValid,
      templateTextOn: Validator.validateBool,
      sortKey: Validator.validateNonNegInt,
    };
    if (updating) {
      for (const key in REQUIRED) {
        OPTIONAL[key] = REQUIRED[key];
        delete REQUIRED[key];
      }
    } else if (!creating) {
      delete REQUIRED.category;
    }
    const checked = checkArgs_("RubricComment", REQUIRED, OPTIONAL, args);
    if (updating || creating) {
      if (hasProp_(checked, "pointDelta")) {
        // flip point delta
        checked.pointDelta = -checked.pointDelta;
      }
    }
    return checked;
  }

  /**
   * Create the given rubric comments.
   *
   * @param {Array<Object>} data The rubric comments.
   * @returns {Array<Object>} The created rubric comments.
   * @throws Throws an exception if an object is missing the required fields.
   * @throws Throws an exception if a rubric category of the rubric comments is
   *  not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  category of the rubric comments.
   */
  static createAll(data) {
    const creating = data.map((category) =>
      RubricComment.checkArgs(category, { creating: true })
    );
    return fetch_("POST", RUBRIC_COMMENTS_, creating);
  }

  /**
   * Update the given rubric comments.
   *
   * @param {Array<Object>} data The rubric comments.
   * @returns {Array<Object>} The updated rubric comments.
   * @throws Throws an exception if an object is missing the required fields.
   * @throws Throws an exception if a rubric comment is not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  comment.
   * @throws Throws an exception if a rubric category of the rubric comments is
   *  not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  category of the rubric comments.
   */
  static updateAll(data) {
    const updating = data.map((obj) => {
      return {
        id: obj.id,
        data: RubricComment.checkArgs(obj.data, { updating: true }),
      };
    });
    return fetch_("PATCH", RUBRIC_COMMENTS_, updating);
  }

  /**
   * Delete the given rubric comments.
   *
   * @param {Array<number>} ids The rubric comment ids.
   * @throws Throws an exception if a rubric comment is not found.
   * @throws Throws an exception if the user does not have access to a rubric
   *  comment.
   */
  static deleteAll(ids) {
    fetch_("DELETE", RUBRIC_COMMENTS_, ids);
  }
}
