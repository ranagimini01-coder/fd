import { r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
import { r as useStableCallback, t as useIsoLayoutEffect } from "./useIsoLayoutEffect-DrOR77jl.js";
import { t as useRenderElement } from "./useRenderElement-BiX6Dyza.js";
import { t as useControlled } from "./useControlled-CXMaCmX-.js";
import { i as ownerDocument, t as activeElement } from "./shadowDom-BbNDe3Dh.js";
import { a as fieldValidityMapping, i as useFieldRootContext, n as useFormContext, r as useRegisterFieldControl, t as useLabelableContext } from "./LabelableContext-eEnEuTbp.js";
import { f as none, t as createChangeEventDetails } from "./createBaseUIEventDetails-BNfSv2gm.js";
import { t as require_jsx_runtime } from "./react_jsx-runtime.js";
import { t as useLabelableId } from "./useLabelableId-_zFazLnK.js";
//#region node_modules/@base-ui/react/field/control/FieldControl.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
/**
* The form control to label and validate.
* Renders an `<input>` element.
*
* You can omit this part and use any Base UI input component instead. For example,
* [Input](https://base-ui.com/react/components/input), [Checkbox](https://base-ui.com/react/components/checkbox),
* or [Select](https://base-ui.com/react/components/select), among others, will work with Field out of the box.
*
* Documentation: [Base UI Field](https://base-ui.com/react/components/field)
*/
var FieldControl = /*#__PURE__*/ import_react.forwardRef(function FieldControl(componentProps, forwardedRef) {
	const { render, className, id: idProp, name: nameProp, value: valueProp, disabled: disabledProp = false, onValueChange, defaultValue, autoFocus = false, style, ...elementProps } = componentProps;
	const { state: fieldState, name: fieldName, disabled: fieldDisabled, setTouched, setDirty, validityData, setFocused, setFilled, validationMode, validation } = useFieldRootContext();
	const { clearErrors } = useFormContext();
	const disabled = fieldDisabled || disabledProp;
	const name = fieldName ?? nameProp;
	const state = {
		...fieldState,
		disabled
	};
	const { labelId } = useLabelableContext();
	const id = useLabelableId({ id: idProp });
	useIsoLayoutEffect(() => {
		const hasExternalValue = valueProp != null;
		if (validation.inputRef.current?.value || hasExternalValue && valueProp !== "") setFilled(true);
		else if (hasExternalValue && valueProp === "") setFilled(false);
	}, [
		validation.inputRef,
		setFilled,
		valueProp
	]);
	const inputRef = import_react.useRef(null);
	useIsoLayoutEffect(() => {
		if (autoFocus && inputRef.current === activeElement(ownerDocument(inputRef.current))) setFocused(true);
	}, [autoFocus, setFocused]);
	const [valueUnwrapped] = useControlled({
		controlled: valueProp,
		default: defaultValue,
		name: "FieldControl",
		state: "value"
	});
	const isControlled = valueProp !== void 0;
	const value = isControlled ? valueUnwrapped : void 0;
	const getValueFromInput = useStableCallback(() => validation.inputRef.current?.value);
	useRegisterFieldControl(validation.inputRef, id, value, getValueFromInput, !disabled, nameProp);
	return useRenderElement("input", componentProps, {
		ref: [forwardedRef, inputRef],
		state,
		props: [
			{
				id,
				disabled,
				name,
				ref: validation.inputRef,
				"aria-labelledby": labelId,
				autoFocus,
				...isControlled ? { value } : { defaultValue },
				onChange(event) {
					const inputValue = event.currentTarget.value;
					onValueChange?.(inputValue, createChangeEventDetails(none, event.nativeEvent));
					setDirty(inputValue !== validityData.initialValue);
					setFilled(inputValue !== "");
					if (!event.nativeEvent.defaultPrevented) {
						clearErrors(name);
						validation.change(inputValue);
					}
				},
				onFocus() {
					setFocused(true);
				},
				onBlur(event) {
					setTouched(true);
					setFocused(false);
					if (validationMode === "onBlur") validation.commit(event.currentTarget.value);
				},
				onKeyDown(event) {
					if (event.currentTarget.tagName === "INPUT" && event.key === "Enter") {
						setTouched(true);
						validation.commit(event.currentTarget.value);
					}
				}
			},
			elementProps,
			(props) => validation.getValidationProps(disabled, props)
		],
		stateAttributesMapping: fieldValidityMapping
	});
});
FieldControl.displayName = "FieldControl";
//#endregion
//#region node_modules/@base-ui/react/input/Input.mjs
var import_jsx_runtime = require_jsx_runtime();
var Input = /*#__PURE__*/ import_react.forwardRef(function Input(props, forwardedRef) {
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FieldControl, {
		ref: forwardedRef,
		...props
	});
});
Input.displayName = "Input";
//#endregion
export { Input };
