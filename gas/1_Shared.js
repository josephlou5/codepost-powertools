function hasProp_(obj, prop) {
  return obj.hasOwnProperty(prop);
}

function isNumber_(val) {
  if (val == null || val.trim?.() === "") return false;
  return !Number.isNaN(Number(val));
}

function error_(functionName, message) {
  return {
    function: functionName,
    message: message,
  };
}
