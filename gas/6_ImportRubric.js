/**
 * Helper function to check the validity of the `rubric` arg.
 */
function checkValidRubric_(rubric) {
  const ERROR = "`rubric`:";

  if (rubric == null) {
    throw `${ERROR} missing`;
  }
  if (!Array.isArray(rubric)) {
    throw `${ERROR} not an array`;
  }

  const givenCategories = [];
  const givenComments = {};

  const seenCategories = new Set();
  const seenComments = new Set();

  rubric.forEach(({ comments, ...categoryArgs }, index1) => {
    let category;
    try {
      category = RubricCategory.checkArgs(categoryArgs);
    } catch (e) {
      throw `${ERROR} category ${index1}: ${e.message}`;
    }

    const categoryName = category.name;
    if (seenCategories.has(categoryName)) {
      throw (
        `${ERROR} category ${index1}: ` +
        `"name": not unique ("${categoryName}")`
      );
    }
    seenCategories.add(categoryName);

    givenCategories.push(category);

    if (comments == null) {
      throw `${ERROR} category ${index1}: \`comments\`: missing`;
    }
    if (!Array.isArray(comments)) {
      throw `${ERROR} category ${index1}: \`comments\`: not an array`;
    }

    givenComments[categoryName] = comments.map((commentArgs, index2) => {
      let comment;
      try {
        // check and fix args
        comment = RubricComment.checkArgs(commentArgs);
      } catch (e) {
        throw `${ERROR} category ${index1}, comment ${index2}: ${e.message}`;
      }

      const commentName = comment.name;
      if (seenComments.has(commentName)) {
        throw (
          `${ERROR} category ${index1}, comment ${index2}: ` +
          `"name": not unique ("${commentName}")`
        );
      }
      seenComments.add(commentName);

      return comment;
    });
  });

  return [givenCategories, givenComments];
}

/**
 * Helper function to import a rubric.
 */
function importRubric_(assignmentId, rubric, wipe, deleteExtra) {
  if (assignmentId == null) {
    throw "`assignmentId`: missing";
  }
  if (!isNumber_(assignmentId)) {
    throw "`assignmentId`: invalid (not a number)";
  }

  // check valid rubric and get fixed args
  const [givenCategories, givenComments] = checkValidRubric_(rubric);

  // get assignment
  const assignment = Assignment.getById(assignmentId);

  // check number submissions
  if (Assignment.getNumSubmissions(assignmentId) > 0) {
    const wantContinue = askYesNo_(
      `"${assignment.name}" assignment has existing submissions.`,
      "Do you still wish to continue?"
    );
    if (wantContinue !== YES_) {
      return;
    }
  }

  if (wipe) {
    // delete existing rubric
    RubricCategory.deleteAll(assignment.rubricCategories);

    // create categories
    const createdCategories = RubricCategory.createAll(
      givenCategories.map((category, sortKey) => {
        return {
          ...category,
          assignment: assignmentId,
          sortKey: sortKey,
        };
      })
    );

    // category name -> category id
    const categories = Object.fromEntries(
      createdCategories.map((category) => [category.name, category.id])
    );

    RubricComment.createAll(
      Object.entries(givenComments).flatMap(([categoryName, comments]) => {
        const categoryId = categories[categoryName];
        return comments.map((comment, sortKey) => {
          return {
            ...comment,
            category: categoryId,
            sortKey: sortKey,
          };
        });
      })
    );

    return;
  }

  // get existing rubric
  // category name -> category
  const cpCategories = Object.fromEntries(
    RubricCategory.getByIds(assignment.rubricCategories).map((category) => [
      category.name,
      category,
    ])
  );
  // comment name -> comment
  const cpComments = Object.fromEntries(
    RubricComment.getByIds(
      Object.values(cpCategories).flatMap((category) => category.rubricComments)
    ).map((comment) => [comment.name, comment])
  );

  // the final categories in codepost
  // category name -> category id
  const finalCategories = Object.fromEntries(
    Object.values(cpCategories).map((category) => [category.name, category.id])
  );

  // get categories in codepost
  const existingCategories = new Set(Object.keys(cpCategories));

  // create missing categories (in given but not in codepost)
  // update categories that have changed
  const createCategories = [];
  const updateCategories = [];
  givenCategories.forEach((category, sortKey) => {
    const name = category.name;

    if (!existingCategories.delete(name)) {
      // create category
      createCategories.push({
        ...category,
        assignment: assignmentId,
        sortKey: sortKey,
      });
      return;
    }

    const existing = cpCategories[name];

    // check if need to update category
    let updating = false;
    const update = {};
    for (const field of ["pointLimit", "helpText", "atMostOnce"]) {
      // if doesn't have field, ignore
      if (!hasProp_(category, field)) continue;
      if (existing[field] !== category[field]) {
        updating = true;
        update[field] = category[field];
      }
    }
    if (existing.sortKey !== sortKey) {
      updating = true;
      update.sortKey = sortKey;
    }

    if (updating) {
      // update category
      updateCategories.push({
        id: existing.id,
        data: update,
      });
    }
  });

  // create categories
  RubricCategory.createAll(createCategories).forEach((category) => {
    finalCategories[category.name] = category.id;
  });

  // deal with extra categories (in codepost but not in given)
  if (existingCategories.size > 0) {
    const categories = Array.from(existingCategories);
    if (deleteExtra) {
      // delete extra categories
      RubricCategory.deleteAll(categories.map((name) => cpCategories[name].id));
    } else {
      // sort at bottom
      const offset = rubric.length;
      categories.forEach((name, i) => {
        const category = cpCategories[name];
        const sortKey = offset + i;
        if (category.sortKey !== sortKey) {
          updateCategories.push({
            id: category.id,
            data: {
              sortKey: offset + i,
            },
          });
        }
      });
    }
  }

  // update categories
  RubricCategory.updateAll(updateCategories).forEach((category) => {
    finalCategories[category.name] = category.id;
  });

  // get comments in codepost
  const existingComments = new Set(Object.keys(cpComments));

  // create missing comments (in given but not in codepost)
  // update comments that have changed
  const createComments = [];
  const updateComments = [];
  Object.entries(givenComments).forEach(([categoryName, comments]) => {
    // creating comments in this category
    const categoryId = finalCategories[categoryName];
    comments.forEach((comment, sortKey) => {
      const name = comment.name;

      if (!existingComments.delete(name)) {
        // create comment
        createComments.push({
          ...comment,
          category: categoryId,
          sortKey: sortKey,
        });
        return;
      }

      const existing = cpComments[name];

      // check if need to update comment
      let updating = false;
      const update = {};
      for (const field of [
        "text",
        "pointDelta",
        "explanation",
        "instructionText",
        "templateTextOn",
      ]) {
        // if doesn't have field, ignore
        if (!hasProp_(comment, field)) continue;
        if (existing[field] !== comment[field]) {
          updating = true;
          update[field] = comment[field];
        }
      }
      if (existing.category !== categoryId) {
        updating = true;
        update.category = categoryId;
      }
      if (existing.sortKey !== sortKey) {
        updating = true;
        update.sortKey = sortKey;
      }

      if (updating) {
        // update comment
        updateComments.push({
          id: existing.id,
          data: update,
        });
      }
    });
  });

  // create comments
  RubricComment.createAll(createComments);

  // deal with extra comments (in codepost but not in given)
  if (existingComments.size > 0) {
    const comments = Array.from(existingComments);
    if (deleteExtra) {
      // delete extra comments
      RubricComment.deleteAll(comments.map((name) => cpComments[name].id));
    } else {
      // category id -> number of comments (next sortKey)
      const sortKeys = Object.fromEntries(
        Object.entries(givenComments).map(([categoryName, comments]) => [
          finalCategories[categoryName],
          comments.length,
        ])
      );
      // sort at bottom of their categories
      comments.forEach((name) => {
        const comment = cpComments[name];
        const sortKey = sortKeys[comment.category]++;
        if (comment.sortKey !== sortKey) {
          updateComments.push({
            id: comment.id,
            data: {
              sortKey: sortKey,
            },
          });
        }
      });
    }
  }

  // update comments
  RubricComment.updateAll(updateComments);
}

/**
 * Import a rubric into codePost.
 * Warns the user if the assignment has existing submissions.
 *
 * @param {number} assignmentId The assignment id.
 * @param {Array<Object>} rubric The rubric data.
 *  Each element should be an object representing a rubric category.
 * @param {Array<Object>} rubric[].comments
 *  The comments of the rubric category.
 *  Each element should be an object representing a rubric comment.
 * @param {Object} options Extra options.
 * @param {boolean=} options.wipe Whether to wipe the existing rubric first.
 * @param {boolean=} options.deleteExtra Whether to delete extra codePost
 *  comments that are not in the given rubric.
 * @throws Throws an exception if `assignmentId` is invalid.
 * @throws Throws an exception if an object is missing required fields.
 * @throws Throws an exception if a rubric category name is not unique.
 * @throws Throws an exception if a rubric comment name is not unique.
 * @throws Throws an exception if the assignment is not found.
 * @throws Throws an exception if the user does not have access to the
 *  assignment.
 */
function importRubric(
  assignmentId,
  rubric,
  { wipe = false, deleteExtra = false } = {}
) {
  try {
    importRubric_(assignmentId, rubric, wipe, deleteExtra);
  } catch (e) {
    if (e.function == null) {
      throw error_("importRubric()", e);
    } else {
      throw error_(`importRubric(): ${e.function}`, e.message);
    }
  }
}
