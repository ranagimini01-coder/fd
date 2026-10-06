import { a as getComputedStyle, g as isHTMLElement } from "./useIsoLayoutEffect-DrOR77jl.js";
import { b as round } from "./DirectionContext-O998dM5m.js";
//#region node_modules/@base-ui/react/utils/getCssDimensions.mjs
function getCssDimensions(element) {
	const css = getComputedStyle(element);
	let width = parseFloat(css.width) || 0;
	let height = parseFloat(css.height) || 0;
	const hasOffset = isHTMLElement(element);
	const offsetWidth = hasOffset ? element.offsetWidth : width;
	const offsetHeight = hasOffset ? element.offsetHeight : height;
	if (round(width) !== offsetWidth || round(height) !== offsetHeight) {
		width = offsetWidth;
		height = offsetHeight;
	}
	return {
		width,
		height
	};
}
//#endregion
export { getCssDimensions as t };
