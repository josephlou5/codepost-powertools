const BASE_ENDPOINT_ = "https://api.codepost.io/";

// All accepted method types and their success response codes.
const METHODS_ = {
  GET: 200,
  POST: 201,
  PATCH: 200,
  DELETE: 204,
};

/**
 * Check and fix a request method type.
 *
 * @param {string} method The method type.
 * @returns {string} The fixed method.
 * @throws Throws an exception for unknown method types.
 */
function checkMethod_(method) {
  method = method.trim().toUpperCase();
  if (!hasProp_(METHODS_, method)) {
    throw error_("fetch()", `unknown request method "${method}"`);
  }
  return method;
}

/**
 * Fix an endpoint.
 *
 * @param {string} endpoint The endpoint.
 * @returns {string} The fixed endpoint.
 */
function fixEndpoint_(endpoint) {
  if (endpoint.startsWith("/")) {
    endpoint = endpoint.substring(1);
  }
  if (!endpoint.endsWith("/")) {
    endpoint += "/";
  }
  return endpoint;
}

/**
 * Make options for a codePost API request.
 *
 * @param {string} method The method type.
 * @returns {Object} The options.
 * @throws Throws an exception if the API key is not found.
 */
function makeOptions_(method) {
  const apiKey = configGet("API_KEY");
  if (apiKey == null) {
    throw error_(
      "fetch()",
      'API key not found. Use the "Set API Key" menu to set your API key.'
    );
  }
  return {
    method: method,
    headers: {
      Accept: "application/json",
      Authorization: `Token ${apiKey}`,
    },
    muteHttpExceptions: true,
  };
}

/**
 * Process the result of a codePost API request.
 *
 * @param {string} method The method type.
 * @param {string} endpoint The endpoint.
 * @param {HTTPResponse} response The response.
 * @throws Throws an exception if the API call failed.
 */
function processResult_(method, endpoint, res) {
  const RESPONSE_CODE = METHODS_[method];

  const content = res.getContentText() || JSON.stringify({});
  const parsed = JSON.parse(content);
  const resCode = res.getResponseCode();
  console.log(`${method} ${endpoint} ${resCode}: ${content}`);
  if (resCode !== RESPONSE_CODE) {
    // parse codepost error
    const message = parsed.detail || JSON.stringify(parsed);
    throw error_("fetch()", `${method} ${endpoint}: ${message}`);
  }

  return parsed;
}

/**
 * Make codePost API request calls.
 * Supports GET, POST, PATCH, and DELETE requests.
 * Assumes data is valid for POST and PATCH requests.
 *
 * @param {string} method The method type.
 * @param {string} endpoint The resource endpoint.
 * @param {Array<number|Object>} data
 *  The ids after the endpoint, or
 *  the data for POST requests, or
 *  the ids and data for PATCH requests.
 * @param {number} data[].id The id for PATCH requests.
 * @param {Object} data[].data The data for PATCH requests.
 * @returns {Array<Object>} The parsed request results.
 * @throws Throws an exception for unknown method types.
 * @throws Throws an exception if a POST or PATCH request has no data.
 * @throws Throws an exception if an API call fails.
 */
function fetch_(method, endpoint, data) {
  method = checkMethod_(method);
  endpoint = fixEndpoint_(endpoint);

  const endpoints = [];
  const requests = [];
  data.forEach((request, index) => {
    let thisEndpoint = endpoint;
    const options = makeOptions_(method);

    if (method === "POST") {
      if (request == null) {
        throw error_("fetch()", `"POST" request ${index} missing data`);
      }
      Object.assign(options, {
        contentType: "application/json",
        payload: JSON.stringify(request),
      });
    } else if (method === "PATCH") {
      // get id and data
      if (request == null) {
        throw error_("fetch()", `"PATCH" request ${index} missing`);
      }
      if (request.data == null) {
        throw error_("fetch()", `"PATCH" request ${index} missing data`);
      }
      if (request.id == null) {
        throw error_("fetch()", `"PATCH" request ${index} missing id`);
      }

      thisEndpoint += `${request.id}/`;
      Object.assign(options, {
        contentType: "application/json",
        payload: JSON.stringify(request.data),
      });
    } else {
      // GET and DELETE methods
      // get id; ignore data
      if (isNumber_(request)) {
        thisEndpoint += `${request}/`;
      } else {
        if (!isNumber_(request.id)) {
          throw error_("fetch()", `"${method}" request ${index} has no id`);
        }
        thisEndpoint += `${request.id}/`;
      }
    }

    options.url = `${BASE_ENDPOINT_}${thisEndpoint}`;

    endpoints.push("/" + thisEndpoint);
    requests.push(options);
  });

  if (requests.length === 0) {
    return [];
  }

  // make requests
  const responses = UrlFetchApp.fetchAll(requests);

  // process responses
  const processed = responses.map((res, index) =>
    processResult_(method, endpoints[index], res)
  );

  return processed;
}

/**
 * Make a codePost API request call.
 * Supports GET, POST, PATCH, and DELETE requests.
 * Assumes data is valid for POST and PATCH requests.
 *
 * @param {string} method The method type.
 * @param {string} endpoint The resource endpoint.
 * @param {?Object} data The data for PATCH requests.
 * @returns {Object} The parsed request result.
 * @throws Throws an exception for unknown method types.
 * @throws Throws an exception if a PATCH method has no data.
 * @throws Throws an exception if the API call fails.
 */
function fetchOne_(method, endpoint, data = null) {
  method = checkMethod_(method);
  endpoint = fixEndpoint_(endpoint);

  const options = makeOptions_(method);

  if (method === "POST" || method === "PATCH") {
    if (data == null) {
      throw error_("fetch()", `"${method}" request missing data`);
    }
    Object.assign(options, {
      contentType: "application/json",
      payload: JSON.stringify(data),
    });
  }

  // make url
  const url = `${BASE_ENDPOINT_}${endpoint}`;

  // make request
  const response = UrlFetchApp.fetch(url, options);

  // process response
  return processResult_(method, endpoint, response);
}
