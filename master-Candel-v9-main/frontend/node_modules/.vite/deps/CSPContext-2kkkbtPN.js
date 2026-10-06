import { r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
//#region node_modules/@base-ui/react/internals/csp-context/CSPContext.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
/**
* @internal
*/
var CSPContext = /*#__PURE__*/ import_react.createContext(void 0);
CSPContext.displayName = "CSPContext";
var DEFAULT_CSP_CONTEXT_VALUE = { disableStyleElements: false };
/**
* @internal
*/
function useCSPContext() {
	return import_react.useContext(CSPContext) ?? DEFAULT_CSP_CONTEXT_VALUE;
}
//#endregion
export { useCSPContext as t };
