// The Worker's entry. Only the default export lives here: workerd treats every named export of the
// main module as an entrypoint. The logic and its tests use lib.js.
import { handle } from "./lib.js";

export default { fetch: handle };
