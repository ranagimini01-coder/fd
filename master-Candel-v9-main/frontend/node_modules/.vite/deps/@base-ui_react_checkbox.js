import { n as __exportAll, r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
import { p as getWindow, t as useIsoLayoutEffect } from "./useIsoLayoutEffect-DrOR77jl.js";
import { c as useRefWithInit, i as NOOP, r as EMPTY_OBJECT, s as useMergedRefs, t as useRenderElement } from "./useRenderElement-BiX6Dyza.js";
import { r as mergeProps } from "./merge-props-B1zstas5.js";
import { t as useButton } from "./useButton-DFSPkxH_.js";
import { t as useControlled } from "./useControlled-CXMaCmX-.js";
import { n as visuallyHidden, r as visuallyHiddenInput, t as useValueChanged } from "./useValueChanged-Bmjcvk0Q.js";
import { a as fieldValidityMapping, i as useFieldRootContext, n as useFormContext, r as useRegisterFieldControl, t as useLabelableContext } from "./LabelableContext-eEnEuTbp.js";
import { f as none, t as createChangeEventDetails, y as useBaseUiId } from "./createBaseUIEventDetails-BNfSv2gm.js";
import { t as require_jsx_runtime } from "./react_jsx-runtime.js";
import { a as transitionStatusMapping, n as useOpenChangeComplete, t as useTransitionStatus } from "./useTransitionStatus-CDr8WmsC.js";
//#region node_modules/@base-ui/utils/getDefaultFormSubmitter.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
/**
* Returns the default button a browser uses for implicit form submission.
*
* This is useful for custom form controls that need to mirror native Enter key behavior.
* Clicking the returned submitter preserves browser semantics such as the submitter's click
* event, `SubmitEvent.submitter`, and submitter-specific attributes.
*
* The function follows the controls exposed by `form.elements`, which includes controls associated
* through the `form` attribute. Disabled submitters can be returned because the default button is
* determined before disabled state is considered; clicking a disabled submitter is a no-op.
*/
function getDefaultFormSubmitter(form) {
	if (!form) return null;
	for (const candidate of form.elements) {
		const tagName = candidate.tagName;
		if (tagName === "BUTTON" || tagName === "INPUT") {
			const button = candidate;
			if (button.type === "submit") return button;
		}
	}
	return null;
}
//#endregion
//#region node_modules/@base-ui/react/checkbox/root/CheckboxRootDataAttributes.mjs
var CheckboxRootDataAttributes = /*#__PURE__*/ function(CheckboxRootDataAttributes) {
	/**
	* Present when the checkbox is checked.
	*/
	CheckboxRootDataAttributes["checked"] = "data-checked";
	/**
	* Present when the checkbox is not checked.
	*/
	CheckboxRootDataAttributes["unchecked"] = "data-unchecked";
	/**
	* Present when the checkbox is in an indeterminate state.
	*/
	CheckboxRootDataAttributes["indeterminate"] = "data-indeterminate";
	/**
	* Present when the checkbox is disabled.
	*/
	CheckboxRootDataAttributes["disabled"] = "data-disabled";
	/**
	* Present when the checkbox is readonly.
	*/
	CheckboxRootDataAttributes["readonly"] = "data-readonly";
	/**
	* Present when the checkbox is required.
	*/
	CheckboxRootDataAttributes["required"] = "data-required";
	/**
	* Present when the checkbox is in a valid state (when wrapped in Field.Root).
	*/
	CheckboxRootDataAttributes["valid"] = "data-valid";
	/**
	* Present when the checkbox is in an invalid state (when wrapped in Field.Root).
	*/
	CheckboxRootDataAttributes["invalid"] = "data-invalid";
	/**
	* Present when the checkbox has been touched (when wrapped in Field.Root).
	*/
	CheckboxRootDataAttributes["touched"] = "data-touched";
	/**
	* Present when the checkbox's value has changed (when wrapped in Field.Root).
	*/
	CheckboxRootDataAttributes["dirty"] = "data-dirty";
	/**
	* Present when the checkbox is checked (when wrapped in Field.Root).
	*/
	CheckboxRootDataAttributes["filled"] = "data-filled";
	/**
	* Present when the checkbox is focused (when wrapped in Field.Root).
	*/
	CheckboxRootDataAttributes["focused"] = "data-focused";
	return CheckboxRootDataAttributes;
}({});
//#endregion
//#region node_modules/@base-ui/react/checkbox/utils/useStateAttributesMapping.mjs
function useStateAttributesMapping(state) {
	return import_react.useMemo(() => ({
		checked(value) {
			if (state.indeterminate) return {};
			if (value) return { [CheckboxRootDataAttributes.checked]: "" };
			return { [CheckboxRootDataAttributes.unchecked]: "" };
		},
		...fieldValidityMapping
	}), [state.indeterminate]);
}
//#endregion
//#region node_modules/@base-ui/react/field/item/FieldItemContext.mjs
var FieldItemContext = /*#__PURE__*/ import_react.createContext({ disabled: false });
FieldItemContext.displayName = "FieldItemContext";
function useFieldItemContext() {
	return import_react.useContext(FieldItemContext);
}
//#endregion
//#region node_modules/@base-ui/react/internals/labelable-provider/useAriaLabelledBy.mjs
/**
* @internal
*/
function useAriaLabelledBy(explicitAriaLabelledBy, labelId, labelSourceRef, enableFallback = true, labelSourceId) {
	const [fallbackAriaLabelledBy, setFallbackAriaLabelledBy] = import_react.useState();
	const generatedLabelId = useBaseUiId(labelSourceId ? `${labelSourceId}-label` : void 0);
	const ariaLabelledBy = explicitAriaLabelledBy ?? labelId ?? fallbackAriaLabelledBy;
	useIsoLayoutEffect(() => {
		const nextAriaLabelledBy = explicitAriaLabelledBy || labelId || !enableFallback ? void 0 : getAriaLabelledBy(labelSourceRef.current, generatedLabelId);
		if (fallbackAriaLabelledBy !== nextAriaLabelledBy) setFallbackAriaLabelledBy(nextAriaLabelledBy);
	});
	return ariaLabelledBy;
}
function getAriaLabelledBy(labelSource, generatedLabelId) {
	const label = findAssociatedLabel(labelSource);
	if (!label) return;
	if (!label.id && generatedLabelId) label.id = generatedLabelId;
	return label.id || void 0;
}
function findAssociatedLabel(labelSource) {
	if (!labelSource) return;
	const parent = labelSource.parentElement;
	if (parent && parent.tagName === "LABEL") return parent;
	const controlId = labelSource.id;
	if (controlId) {
		const nextSibling = labelSource.nextElementSibling;
		if (nextSibling && nextSibling.htmlFor === controlId) return nextSibling;
	}
	const labels = labelSource.labels;
	return labels && labels[0];
}
//#endregion
//#region node_modules/@base-ui/react/checkbox-group/CheckboxGroupContext.mjs
var CheckboxGroupContext = /*#__PURE__*/ import_react.createContext(void 0);
CheckboxGroupContext.displayName = "CheckboxGroupContext";
function useCheckboxGroupContext(optional = true) {
	const context = import_react.useContext(CheckboxGroupContext);
	if (context === void 0 && !optional) throw new Error("Base UI: CheckboxGroupContext is missing. CheckboxGroup parts must be placed within <CheckboxGroup>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/checkbox/root/CheckboxRootContext.mjs
var CheckboxRootContext = /*#__PURE__*/ import_react.createContext(void 0);
CheckboxRootContext.displayName = "CheckboxRootContext";
function useCheckboxRootContext() {
	const context = import_react.useContext(CheckboxRootContext);
	if (context === void 0) throw new Error("Base UI: CheckboxRootContext is missing. Checkbox parts must be placed within <Checkbox.Root>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/checkbox/root/CheckboxRoot.mjs
var import_jsx_runtime = require_jsx_runtime();
var PARENT_CHECKBOX = "data-parent";
/**
* Represents the checkbox itself.
* Renders a `<span>` element and a hidden `<input>` beside.
*
* Documentation: [Base UI Checkbox](https://base-ui.com/react/components/checkbox)
*/
var CheckboxRoot = /*#__PURE__*/ import_react.forwardRef(function CheckboxRoot(componentProps, forwardedRef) {
	const { checked: checkedProp, className, defaultChecked = false, "aria-labelledby": ariaLabelledByProp, disabled: disabledProp = false, form, id: idProp, indeterminate = false, inputRef: inputRefProp, name: nameProp, onCheckedChange, parent = false, readOnly = false, render, required = false, uncheckedValue, value: valueProp, nativeButton = false, style, ...elementProps } = componentProps;
	const { clearErrors } = useFormContext();
	const { disabled: rootDisabled, name: fieldName, setDirty, setFilled, setFocused, setTouched, state: fieldState, validationMode, validityData, validation: localValidation } = useFieldRootContext();
	const fieldItemContext = useFieldItemContext();
	const { labelId, controlId, registerControlId, getDescriptionProps } = useLabelableContext();
	const groupContext = useCheckboxGroupContext();
	const parentContext = groupContext?.parent;
	const isGroupedWithParent = parentContext && groupContext.allValues;
	const disabled = rootDisabled || fieldItemContext.disabled || groupContext?.disabled || disabledProp;
	const name = fieldName ?? nameProp;
	const value = valueProp ?? name;
	const id = useBaseUiId();
	const parentId = useBaseUiId();
	let inputId = controlId;
	if (isGroupedWithParent) inputId = parent ? parentId : `${parentContext.id}-${value}`;
	else if (idProp) inputId = idProp;
	let groupProps = {};
	if (isGroupedWithParent) {
		if (parent) groupProps = groupContext.parent.getParentProps();
		else if (value) groupProps = groupContext.parent.getChildProps(value);
	}
	const { checked: groupChecked = checkedProp, indeterminate: groupIndeterminate = indeterminate, onCheckedChange: groupOnChange, ...otherGroupProps } = groupProps;
	const groupValue = groupContext?.value;
	const setGroupValue = groupContext?.setValue;
	const defaultGroupValue = groupContext?.defaultValue;
	const controlRef = import_react.useRef(null);
	const controlSourceRef = useRefWithInit(() => Symbol("checkbox-control"));
	const hasRegisteredRef = import_react.useRef(false);
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		native: nativeButton
	});
	const validation = groupContext?.validation ?? localValidation;
	const [checked, setCheckedState] = useControlled({
		controlled: value && groupValue && !parent ? groupValue.includes(value) : groupChecked,
		default: value && defaultGroupValue && !parent ? defaultGroupValue.includes(value) : defaultChecked,
		name: "Checkbox",
		state: "checked"
	});
	const computedChecked = isGroupedWithParent ? Boolean(groupChecked) : checked;
	const computedIndeterminate = isGroupedWithParent ? groupIndeterminate || indeterminate : indeterminate;
	useIsoLayoutEffect(() => {
		if (registerControlId === NOOP) return;
		hasRegisteredRef.current = true;
		registerControlId(controlSourceRef.current, inputId);
	}, [
		inputId,
		registerControlId,
		controlSourceRef
	]);
	import_react.useEffect(() => {
		const controlSource = controlSourceRef.current;
		return () => {
			if (!hasRegisteredRef.current || registerControlId === NOOP) return;
			hasRegisteredRef.current = false;
			registerControlId(controlSource, void 0);
		};
	}, [registerControlId, controlSourceRef]);
	useRegisterFieldControl(controlRef, id, checked, void 0, !groupContext && !disabled, nameProp);
	const inputRef = import_react.useRef(null);
	const mergedInputRef = useMergedRefs(inputRefProp, inputRef, validation.inputRef, validation.registerInput);
	const ariaLabelledBy = useAriaLabelledBy(ariaLabelledByProp, labelId, inputRef, !nativeButton, inputId ?? void 0);
	useIsoLayoutEffect(() => {
		if (inputRef.current) {
			inputRef.current.indeterminate = computedIndeterminate;
			if (checked) setFilled(true);
		}
	}, [
		checked,
		computedIndeterminate,
		setFilled
	]);
	useValueChanged(checked, () => {
		if (groupContext) return;
		clearErrors(name);
		setFilled(checked);
		setDirty(checked !== validityData.initialValue);
		validation.change(checked);
	});
	const inputProps = mergeProps({
		checked,
		disabled,
		form,
		name: parent ? void 0 : name,
		id: nativeButton ? void 0 : inputId ?? void 0,
		required,
		ref: mergedInputRef,
		style: name ? visuallyHiddenInput : visuallyHidden,
		tabIndex: -1,
		type: "checkbox",
		"aria-hidden": true,
		onChange(event) {
			if (event.nativeEvent.defaultPrevented) return;
			if (readOnly) {
				event.preventDefault();
				return;
			}
			const nextChecked = event.currentTarget.checked;
			const details = createChangeEventDetails(none, event.nativeEvent);
			onCheckedChange?.(nextChecked, details);
			if (details.isCanceled) return;
			groupOnChange?.(nextChecked, details);
			if (details.isCanceled) return;
			setCheckedState(nextChecked);
			if (value && groupValue && setGroupValue && !parent && !isGroupedWithParent) {
				const nextGroupValue = nextChecked ? [...groupValue, value] : groupValue.filter((item) => item !== value);
				setGroupValue(nextGroupValue, details);
			}
		},
		onFocus() {
			controlRef.current?.focus();
		}
	}, valueProp !== void 0 ? { value: (groupContext ? checked && valueProp : valueProp) || "" } : EMPTY_OBJECT, getDescriptionProps, (props) => validation.getValidationProps(disabled, props));
	import_react.useEffect(() => {
		if (!parentContext || !value) return;
		const disabledStates = parentContext.disabledStatesRef.current;
		disabledStates.set(value, disabled);
		return () => {
			disabledStates.delete(value);
		};
	}, [
		parentContext,
		disabled,
		value
	]);
	const state = import_react.useMemo(() => ({
		...fieldState,
		checked: computedChecked,
		disabled,
		readOnly,
		required,
		indeterminate: computedIndeterminate
	}), [
		fieldState,
		computedChecked,
		disabled,
		readOnly,
		required,
		computedIndeterminate
	]);
	const stateAttributesMapping = useStateAttributesMapping(state);
	const element = useRenderElement("span", componentProps, {
		state,
		ref: [
			buttonRef,
			controlRef,
			forwardedRef,
			groupContext?.registerControlRef
		],
		props: [
			{
				id: nativeButton ? inputId ?? void 0 : id,
				role: "checkbox",
				"aria-checked": computedIndeterminate ? "mixed" : computedChecked,
				"aria-readonly": readOnly || void 0,
				"aria-required": required || void 0,
				"aria-labelledby": ariaLabelledBy,
				[PARENT_CHECKBOX]: parent ? "" : void 0,
				onFocus() {
					if (!disabled) setFocused(true);
				},
				onBlur() {
					const inputEl = inputRef.current;
					if (!inputEl) return;
					setTouched(true);
					setFocused(false);
					if (validationMode === "onBlur") validation.commit(groupContext ? groupValue : inputEl.checked);
				},
				onKeyDown(event) {
					if (event.key !== "Enter") return;
					event.preventBaseUIHandler();
					if (event.defaultPrevented) return;
					const formToSubmit = inputRef.current?.form ?? null;
					const currentTarget = event.currentTarget;
					const nativeEvent = event.nativeEvent;
					const originalPreventDefault = event.preventDefault;
					const originalNativePreventDefault = nativeEvent.preventDefault;
					let preventDefaultCalledAfterPropagation = false;
					event.preventDefault = () => {
						preventDefaultCalledAfterPropagation = true;
						originalPreventDefault.call(event);
					};
					nativeEvent.preventDefault = () => {
						preventDefaultCalledAfterPropagation = true;
						originalNativePreventDefault.call(nativeEvent);
					};
					originalNativePreventDefault.call(nativeEvent);
					getWindow(currentTarget).queueMicrotask(() => {
						event.preventDefault = originalPreventDefault;
						nativeEvent.preventDefault = originalNativePreventDefault;
						if (!preventDefaultCalledAfterPropagation) getDefaultFormSubmitter(formToSubmit)?.click();
					});
				},
				onClick(event) {
					if (readOnly || disabled) return;
					event.preventDefault();
					const input = inputRef.current;
					if (!input) return;
					input.dispatchEvent(new (getWindow(input)).PointerEvent("click", {
						bubbles: true,
						shiftKey: event.shiftKey,
						ctrlKey: event.ctrlKey,
						altKey: event.altKey,
						metaKey: event.metaKey
					}));
				}
			},
			elementProps,
			otherGroupProps,
			getButtonProps,
			getDescriptionProps,
			(props) => validation.getValidationProps(disabled, props)
		],
		stateAttributesMapping
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(CheckboxRootContext.Provider, {
		value: state,
		children: [
			element,
			!checked && !groupContext && name && !parent && uncheckedValue !== void 0 && /*#__PURE__*/ (0, import_jsx_runtime.jsx)("input", {
				type: "hidden",
				form,
				name,
				value: uncheckedValue,
				disabled
			}),
			/*#__PURE__*/ (0, import_jsx_runtime.jsx)("input", {
				...inputProps,
				suppressHydrationWarning: true
			})
		]
	});
});
CheckboxRoot.displayName = "CheckboxRoot";
//#endregion
//#region node_modules/@base-ui/react/checkbox/indicator/CheckboxIndicator.mjs
/**
* Indicates whether the checkbox is ticked.
* Renders a `<span>` element.
*
* Documentation: [Base UI Checkbox](https://base-ui.com/react/components/checkbox)
*/
var CheckboxIndicator = /*#__PURE__*/ import_react.forwardRef(function CheckboxIndicator(componentProps, forwardedRef) {
	const { render, className, style, keepMounted = false, ...elementProps } = componentProps;
	const rootState = useCheckboxRootContext();
	const rendered = rootState.checked || rootState.indeterminate;
	const { mounted, transitionStatus, setMounted } = useTransitionStatus(rendered);
	const indicatorRef = import_react.useRef(null);
	const state = {
		...rootState,
		transitionStatus
	};
	useOpenChangeComplete({
		open: rendered,
		ref: indicatorRef,
		onComplete() {
			if (!rendered) setMounted(false);
		}
	});
	const stateAttributesMapping = {
		...useStateAttributesMapping(rootState),
		...transitionStatusMapping,
		...fieldValidityMapping
	};
	const shouldRender = keepMounted || mounted;
	const element = useRenderElement("span", componentProps, {
		ref: [forwardedRef, indicatorRef],
		state,
		stateAttributesMapping,
		props: elementProps
	});
	if (!shouldRender) return null;
	return element;
});
CheckboxIndicator.displayName = "CheckboxIndicator";
//#endregion
//#region node_modules/@base-ui/react/checkbox/index.parts.mjs
var index_parts_exports = /* @__PURE__ */ __exportAll({
	Indicator: () => CheckboxIndicator,
	Root: () => CheckboxRoot
});
//#endregion
export { index_parts_exports as Checkbox };
