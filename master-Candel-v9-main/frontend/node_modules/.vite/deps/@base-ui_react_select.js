import { n as __exportAll, r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
import { g as isHTMLElement, p as getWindow, r as useStableCallback, t as useIsoLayoutEffect } from "./useIsoLayoutEffect-DrOR77jl.js";
import { c as useRefWithInit, n as EMPTY_ARRAY, r as EMPTY_OBJECT, s as useMergedRefs, t as useRenderElement } from "./useRenderElement-BiX6Dyza.js";
import { r as mergeProps } from "./merge-props-B1zstas5.js";
import { t as useButton } from "./useButton-DFSPkxH_.js";
import { t as useControlled } from "./useControlled-CXMaCmX-.js";
import { n as visuallyHidden, r as visuallyHiddenInput, t as useValueChanged } from "./useValueChanged-Bmjcvk0Q.js";
import { i as ownerDocument, n as contains, r as getTarget } from "./shadowDom-BbNDe3Dh.js";
import { a as fieldValidityMapping, i as useFieldRootContext, n as useFormContext, r as useRegisterFieldControl, t as useLabelableContext } from "./LabelableContext-eEnEuTbp.js";
import { f as none, l as itemPress, n as cancelOpen, t as createChangeEventDetails, v as windowResize, y as useBaseUiId } from "./createBaseUIEventDetails-BNfSv2gm.js";
import { t as require_jsx_runtime } from "./react_jsx-runtime.js";
import { a as transitionStatusMapping, c as useAnimationFrame, n as useOpenChangeComplete, t as useTransitionStatus } from "./useTransitionStatus-CDr8WmsC.js";
import { D as useDismiss, E as useOnFirstRender, I as FloatingPortal, O as useClick, Q as getFloatingFocusElement, S as useStore, T as createSelector, Y as useValueAsRef, Z as addEventListener, bt as triggerOpenStateMapping, gt as useTimeout, i as InternalBackdrop, k as FloatingFocusManager, lt as isVirtualClick, o as FOCUSABLE_POPUP_PROPS, pt as webkit, t as useOpenInteractionType, vt as popupStateMapping, x as Store, yt as pressableTriggerOpenStateMapping, z as DROPDOWN_COLLISION_AVOIDANCE } from "./useOpenInteractionType-fml9RCjU.js";
import { t as useDirection, y as rectToClientRect } from "./DirectionContext-O998dM5m.js";
import { s as COMPOSITE_KEYS, t as inertValue } from "./inertValue-J_gNalGy.js";
import { c as useFloatingRootContext, i as useAnchorPositioning, l as platform, n as useAnchoredPopupScrollLock, o as getDisabledMountTransitionStyles, r as usePositioner, s as useToolbarRootContext, t as usePreviousValue } from "./usePreviousValue-D_tVHlXk.js";
import { i as useListNavigation, n as getPseudoElementBounds, r as useTypeahead, t as Separator } from "./Separator-Cw4HdUXQ.js";
import { t as useLabelableId } from "./useLabelableId-_zFazLnK.js";
import { i as useCompositeListItem, n as CompositeList, r as IndexGuessBehavior, t as isElementDisabled } from "./isElementDisabled-T2-7pWM4.js";
import { t as useCSPContext } from "./CSPContext-2kkkbtPN.js";
//#region node_modules/@base-ui/react/utils/useRegisteredLabelId.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
var import_jsx_runtime = require_jsx_runtime();
function useRegisteredLabelId(idProp, setLabelId) {
	const id = useBaseUiId(idProp);
	useIsoLayoutEffect(() => {
		setLabelId(id);
		return () => {
			setLabelId(void 0);
		};
	}, [id, setLabelId]);
	return id;
}
//#endregion
//#region node_modules/@base-ui/react/internals/labelable-provider/useLabel.mjs
function useLabel(params = {}) {
	const { id: idProp, fallbackControlId, native = false, setLabelId: setLabelIdProp, focusControl: focusControlProp } = params;
	const { controlId: contextControlId, setLabelId: setContextLabelId } = useLabelableContext();
	const id = useRegisteredLabelId(idProp, useStableCallback((nextLabelId) => {
		setContextLabelId(nextLabelId);
		setLabelIdProp?.(nextLabelId);
	}));
	const resolvedControlId = contextControlId ?? fallbackControlId;
	function focusControl(event) {
		if (focusControlProp) {
			focusControlProp(event, resolvedControlId);
			return;
		}
		if (!resolvedControlId) return;
		const controlElement = ownerDocument(event.currentTarget).getElementById(resolvedControlId);
		if (isHTMLElement(controlElement)) focusElementWithVisible(controlElement);
	}
	function handleInteraction(event) {
		if (getTarget(event.nativeEvent)?.closest("button,input,select,textarea")) return;
		if (!event.defaultPrevented && event.detail > 1) event.preventDefault();
		if (native) return;
		focusControl(event);
	}
	return native ? {
		id,
		htmlFor: resolvedControlId ?? void 0,
		onMouseDown: handleInteraction
	} : {
		id,
		onClick: handleInteraction,
		onPointerDown(event) {
			event.preventDefault();
		}
	};
}
function focusElementWithVisible(element) {
	element.focus({ focusVisible: true });
}
//#endregion
//#region node_modules/@base-ui/react/select/root/SelectRootContext.mjs
var SelectRootContext = /*#__PURE__*/ import_react.createContext(null);
SelectRootContext.displayName = "SelectRootContext";
var SelectFloatingContext = /*#__PURE__*/ import_react.createContext(null);
SelectFloatingContext.displayName = "SelectFloatingContext";
function useSelectRootContext() {
	const context = import_react.useContext(SelectRootContext);
	if (context === null) throw new Error("Base UI: SelectRootContext is missing. Select parts must be placed within <Select.Root>.");
	return context;
}
function useSelectFloatingContext() {
	const context = import_react.useContext(SelectFloatingContext);
	if (context === null) throw new Error("Base UI: SelectFloatingContext is missing. Select parts must be placed within <Select.Root>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/internals/itemEquality.mjs
var defaultItemEquality = (itemValue, selectedValue) => Object.is(itemValue, selectedValue);
function compareItemEquality(itemValue, selectedValue, comparer) {
	if (itemValue == null || selectedValue == null) return Object.is(itemValue, selectedValue);
	return comparer(itemValue, selectedValue);
}
function selectedValueIncludes(selectedValues, itemValue, comparer) {
	if (!selectedValues || selectedValues.length === 0) return false;
	return selectedValues.some((selectedValue) => {
		if (selectedValue === void 0) return false;
		return compareItemEquality(itemValue, selectedValue, comparer);
	});
}
function findItemIndex(itemValues, selectedValue, comparer) {
	if (!itemValues || itemValues.length === 0) return -1;
	return itemValues.findIndex((itemValue) => {
		if (itemValue === void 0) return false;
		return compareItemEquality(itemValue, selectedValue, comparer);
	});
}
function removeItem(selectedValues, itemValue, comparer) {
	return selectedValues.filter((selectedValue) => !compareItemEquality(itemValue, selectedValue, comparer));
}
//#endregion
//#region node_modules/@base-ui/react/internals/serializeValue.mjs
function serializeValue(value) {
	if (value == null) return "";
	if (typeof value === "string") return value;
	try {
		return JSON.stringify(value);
	} catch {
		return String(value);
	}
}
//#endregion
//#region node_modules/@base-ui/react/internals/resolveValueLabel.mjs
function isGroupedItems(items) {
	return items != null && items.length > 0 && typeof items[0] === "object" && items[0] != null && "items" in items[0];
}
/**
* Checks if the items array contains an item with a null value that has a non-null label.
*/
function hasNullItemLabel(items) {
	if (!Array.isArray(items)) return items != null && "null" in items;
	const arrayItems = items;
	if (isGroupedItems(arrayItems)) {
		for (const group of arrayItems) for (const item of group.items) if (item && item.value == null && item.label != null) return true;
		return false;
	}
	for (const item of arrayItems) if (item && item.value == null && item.label != null) return true;
	return false;
}
function stringifyAsLabel(item, itemToStringLabel) {
	if (itemToStringLabel && item != null) return itemToStringLabel(item) ?? "";
	if (item && typeof item === "object") {
		if ("label" in item && item.label != null) return String(item.label);
		if ("value" in item) return String(item.value);
	}
	return serializeValue(item);
}
function stringifyAsValue(item, itemToStringValue) {
	if (itemToStringValue && item != null) return itemToStringValue(item) ?? "";
	if (item && typeof item === "object" && "value" in item && "label" in item) return serializeValue(item.value);
	return serializeValue(item);
}
function resolveSelectedLabel(value, items, itemToStringLabel) {
	function fallback() {
		return stringifyAsLabel(value, itemToStringLabel);
	}
	if (itemToStringLabel && value != null) return itemToStringLabel(value);
	if (value && typeof value === "object" && "label" in value && value.label != null) return value.label;
	if (items && !Array.isArray(items)) return items[value] ?? fallback();
	if (Array.isArray(items)) {
		const arrayItems = items;
		const flatItems = isGroupedItems(arrayItems) ? arrayItems.flatMap((group) => group.items) : arrayItems;
		if (value == null || typeof value !== "object") {
			const match = flatItems.find((item) => item.value === value);
			if (match && match.label != null) return match.label;
			return fallback();
		}
		if ("value" in value) {
			const match = flatItems.find((item) => item && item.value === value.value);
			if (match && match.label != null) return match.label;
		}
	}
	return fallback();
}
function resolveMultipleLabels(values, items, itemToStringLabel) {
	return values.reduce((acc, value, index) => {
		if (index > 0) acc.push(", ");
		acc.push(/*#__PURE__*/ (0, import_jsx_runtime.jsx)(import_react.Fragment, { children: resolveSelectedLabel(value, items, itemToStringLabel) }, index));
		return acc;
	}, []);
}
//#endregion
//#region node_modules/@base-ui/react/select/store.mjs
var selectors = {
	id: createSelector((state) => state.id),
	labelId: createSelector((state) => state.labelId),
	modal: createSelector((state) => state.modal),
	multiple: createSelector((state) => state.multiple),
	items: createSelector((state) => state.items),
	itemToStringLabel: createSelector((state) => state.itemToStringLabel),
	itemToStringValue: createSelector((state) => state.itemToStringValue),
	isItemEqualToValue: createSelector((state) => state.isItemEqualToValue),
	value: createSelector((state) => state.value),
	hasSelectedValue: createSelector((state) => {
		const { value, multiple, itemToStringValue } = state;
		if (value == null) return false;
		if (multiple && Array.isArray(value)) return value.length > 0;
		return stringifyAsValue(value, itemToStringValue) !== "";
	}),
	hasNullItemLabel: createSelector((state, enabled) => {
		return enabled ? hasNullItemLabel(state.items) : false;
	}),
	open: createSelector((state) => state.open),
	mounted: createSelector((state) => state.mounted),
	forceMount: createSelector((state) => state.forceMount),
	transitionStatus: createSelector((state) => state.transitionStatus),
	openMethod: createSelector((state) => state.openMethod),
	activeIndex: createSelector((state) => state.activeIndex),
	selectedIndex: createSelector((state) => state.selectedIndex),
	isActive: createSelector((state, index) => state.activeIndex === index),
	isSelected: createSelector((state, itemValue) => {
		const comparer = state.isItemEqualToValue;
		const storeValue = state.value;
		if (state.multiple) return Array.isArray(storeValue) && storeValue.some((selectedItem) => compareItemEquality(itemValue, selectedItem, comparer));
		return compareItemEquality(itemValue, storeValue, comparer);
	}),
	isSelectedByFocus: createSelector((state, index) => {
		return state.selectedIndex === index;
	}),
	popupProps: createSelector((state) => state.popupProps),
	triggerProps: createSelector((state) => state.triggerProps),
	triggerElement: createSelector((state) => state.triggerElement),
	positionerElement: createSelector((state) => state.positionerElement),
	listElement: createSelector((state) => state.listElement),
	popupSide: createSelector((state) => state.popupSide),
	scrollUpArrowVisible: createSelector((state) => state.scrollUpArrowVisible),
	scrollDownArrowVisible: createSelector((state) => state.scrollDownArrowVisible),
	hasScrollArrows: createSelector((state) => state.hasScrollArrows)
};
//#endregion
//#region node_modules/@base-ui/react/internals/areArraysEqual.mjs
function areArraysEqual(array1, array2, itemComparer = (a, b) => a === b) {
	return array1.length === array2.length && array1.every((value, index) => itemComparer(value, array2[index]));
}
//#endregion
//#region node_modules/@base-ui/react/internals/clamp.mjs
function clamp(val, min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER) {
	return Math.max(min, Math.min(val, max));
}
function getMaxScrollOffset(scrollSize, clientSize) {
	return Math.max(0, scrollSize - clientSize);
}
function normalizeScrollOffset(value, max) {
	if (max <= 0) return 0;
	const clamped = clamp(value, 0, max);
	const startDistance = clamped;
	const endDistance = max - clamped;
	const withinStartTolerance = startDistance <= 1;
	const withinEndTolerance = endDistance <= 1;
	if (withinStartTolerance && withinEndTolerance) return startDistance <= endDistance ? 0 : max;
	if (withinStartTolerance) return 0;
	if (withinEndTolerance) return max;
	return clamped;
}
//#endregion
//#region node_modules/@base-ui/react/select/root/SelectRoot.mjs
/**
* Groups all parts of the select.
* Doesn't render its own HTML element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
function SelectRoot(props) {
	const { id, value: valueProp, defaultValue = null, onValueChange, open: openProp, defaultOpen = false, onOpenChange, name: nameProp, form, autoComplete, disabled: disabledProp = false, readOnly = false, required = false, modal = true, actionsRef, inputRef, onOpenChangeComplete, items, multiple = false, itemToStringLabel, itemToStringValue, isItemEqualToValue = defaultItemEquality, highlightItemOnHover = true, children } = props;
	const { clearErrors } = useFormContext();
	const { setDirty, setTouched, setFocused, validityData, setFilled, name: fieldName, disabled: fieldDisabled, validation, validationMode } = useFieldRootContext();
	const generatedId = useLabelableId({ id });
	const disabled = fieldDisabled || disabledProp;
	const name = fieldName ?? nameProp;
	const [value, setValueUnwrapped] = useControlled({
		controlled: valueProp,
		default: multiple ? defaultValue ?? EMPTY_ARRAY : defaultValue,
		name: "Select",
		state: "value"
	});
	const [open, setOpenUnwrapped] = useControlled({
		controlled: openProp,
		default: defaultOpen,
		name: "Select",
		state: "open"
	});
	const listRef = import_react.useRef([]);
	const labelsRef = import_react.useRef([]);
	const popupRef = import_react.useRef(null);
	const scrollHandlerRef = import_react.useRef(null);
	const scrollArrowsMountedCountRef = import_react.useRef(0);
	const valueRef = import_react.useRef(null);
	const valuesRef = import_react.useRef([]);
	const typingRef = import_react.useRef(false);
	const firstItemTextRef = import_react.useRef(null);
	const selectedItemTextRef = import_react.useRef(null);
	const selectionRef = import_react.useRef({
		allowSelectedMouseUp: false,
		allowUnselectedMouseUp: false,
		dragY: 0
	});
	const alignItemWithTriggerActiveRef = import_react.useRef(false);
	const { mounted, setMounted, transitionStatus } = useTransitionStatus(open);
	const { openMethod, triggerProps: interactionTypeProps } = useOpenInteractionType(open);
	const store = useRefWithInit(() => new Store({
		id: generatedId,
		labelId: void 0,
		modal,
		multiple,
		itemToStringLabel,
		itemToStringValue,
		isItemEqualToValue,
		value,
		open,
		mounted,
		transitionStatus,
		items,
		forceMount: false,
		openMethod: null,
		activeIndex: null,
		selectedIndex: null,
		popupProps: {},
		triggerProps: {},
		triggerElement: null,
		positionerElement: null,
		listElement: null,
		popupSide: null,
		scrollUpArrowVisible: false,
		scrollDownArrowVisible: false,
		hasScrollArrows: false
	})).current;
	const activeIndex = useStore(store, selectors.activeIndex);
	const selectedIndex = useStore(store, selectors.selectedIndex);
	const triggerElement = useStore(store, selectors.triggerElement);
	const positionerElement = useStore(store, selectors.positionerElement);
	const previousOpenMethod = usePreviousValue(openMethod);
	const renderedOpenMethod = openMethod ?? previousOpenMethod ?? null;
	const serializedValue = import_react.useMemo(() => {
		if (multiple) return "";
		return stringifyAsValue(value, itemToStringValue);
	}, [
		multiple,
		value,
		itemToStringValue
	]);
	const fieldStringValue = import_react.useMemo(() => {
		if (multiple && Array.isArray(value)) return value.map((currentValue) => stringifyAsValue(currentValue, itemToStringValue));
		return stringifyAsValue(value, itemToStringValue);
	}, [
		multiple,
		value,
		itemToStringValue
	]);
	useRegisterFieldControl(useValueAsRef(store.state.triggerElement), generatedId, value, useStableCallback(() => fieldStringValue), !disabled, nameProp);
	const initialValueRef = import_react.useRef(value);
	const hasSelectedValue = multiple ? Array.isArray(value) && value.length > 0 : value != null && stringifyAsValue(value, itemToStringValue) !== "";
	useIsoLayoutEffect(() => {
		if (value !== initialValueRef.current) store.set("forceMount", true);
	}, [store, value]);
	useIsoLayoutEffect(() => {
		setFilled(hasSelectedValue);
	}, [hasSelectedValue, setFilled]);
	useIsoLayoutEffect(function syncSelectedIndex() {
		const registry = valuesRef.current;
		let nextIndex;
		if (multiple) {
			const currentValue = Array.isArray(value) ? value : [];
			if (currentValue.length === 0) nextIndex = null;
			else {
				const lastValue = currentValue[currentValue.length - 1];
				const lastIndex = findItemIndex(registry, lastValue, isItemEqualToValue);
				nextIndex = lastIndex === -1 ? null : lastIndex;
			}
		} else {
			const index = findItemIndex(registry, value, isItemEqualToValue);
			nextIndex = index === -1 ? null : index;
		}
		if (nextIndex === null) selectedItemTextRef.current = null;
		if (open) return;
		store.set("selectedIndex", nextIndex);
	}, [
		hasSelectedValue,
		multiple,
		open,
		value,
		valuesRef,
		isItemEqualToValue,
		store,
		selectedItemTextRef
	]);
	function isSelectedValueDirty(currentValue) {
		const initialValue = validityData.initialValue;
		if (Array.isArray(currentValue) && Array.isArray(initialValue)) return !areArraysEqual(currentValue, initialValue, (itemValue, initialItemValue) => compareItemEquality(itemValue, initialItemValue, isItemEqualToValue));
		return currentValue !== initialValue;
	}
	useValueChanged(value, () => {
		clearErrors(name);
		setDirty(isSelectedValueDirty(value));
		validation.change(value);
	});
	const setOpen = useStableCallback((nextOpen, eventDetails) => {
		onOpenChange?.(nextOpen, eventDetails);
		if (eventDetails.isCanceled) return;
		setOpenUnwrapped(nextOpen);
		if (!nextOpen && (eventDetails.reason === "focus-out" || eventDetails.reason === "outside-press")) {
			setTouched(true);
			setFocused(false);
			if (validationMode === "onBlur") validation.commit(value);
		}
	});
	const handleUnmount = useStableCallback(() => {
		setMounted(false);
		store.update({
			activeIndex: null,
			openMethod: null
		});
		onOpenChangeComplete?.(false);
	});
	useOpenChangeComplete({
		enabled: !actionsRef,
		open,
		ref: popupRef,
		onComplete() {
			if (!open) handleUnmount();
		}
	});
	import_react.useImperativeHandle(actionsRef, () => ({ unmount: handleUnmount }), [handleUnmount]);
	const setValue = useStableCallback((nextValue, eventDetails) => {
		onValueChange?.(nextValue, eventDetails);
		if (eventDetails.isCanceled) return;
		setValueUnwrapped(nextValue);
	});
	const handleScrollArrowVisibility = useStableCallback(() => {
		const scroller = store.state.listElement || popupRef.current;
		if (!scroller) return;
		const maxScrollTop = getMaxScrollOffset(scroller.scrollHeight, scroller.clientHeight);
		const scrollTop = normalizeScrollOffset(scroller.scrollTop, maxScrollTop);
		const shouldShowUp = scrollTop > 0;
		const shouldShowDown = scrollTop < maxScrollTop;
		if (store.state.scrollUpArrowVisible !== shouldShowUp) store.set("scrollUpArrowVisible", shouldShowUp);
		if (store.state.scrollDownArrowVisible !== shouldShowDown) store.set("scrollDownArrowVisible", shouldShowDown);
	});
	const floatingContext = useFloatingRootContext({
		open,
		onOpenChange: setOpen,
		elements: {
			reference: triggerElement,
			floating: positionerElement
		}
	});
	const click = useClick(floatingContext, {
		enabled: !readOnly && !disabled,
		event: "mousedown"
	});
	const dismiss = useDismiss(floatingContext);
	const listNavigation = useListNavigation(floatingContext, {
		enabled: !readOnly && !disabled,
		listRef,
		activeIndex,
		selectedIndex,
		disabledIndices: EMPTY_ARRAY,
		onNavigate(nextActiveIndex) {
			if (nextActiveIndex === null && !open) return;
			store.set("activeIndex", nextActiveIndex);
		},
		focusItemOnHover: highlightItemOnHover
	});
	const typeahead = useTypeahead(floatingContext, {
		enabled: !readOnly && !disabled && (open || !multiple),
		listRef: labelsRef,
		activeIndex,
		selectedIndex,
		disabledIndices: (index) => isElementDisabled(listRef.current[index]),
		onMatch(index) {
			if (open) store.set("activeIndex", index);
			else setValue(valuesRef.current[index], createChangeEventDetails("none"));
		},
		onTyping(typing) {
			typingRef.current = typing;
		}
	});
	const mergedTriggerProps = import_react.useMemo(() => {
		const triggerInteractionProps = mergeProps(typeahead.reference, listNavigation.reference, dismiss.reference, click.reference, interactionTypeProps);
		if (generatedId) triggerInteractionProps.id = generatedId;
		return triggerInteractionProps;
	}, [
		click.reference,
		typeahead.reference,
		listNavigation.reference,
		dismiss.reference,
		interactionTypeProps,
		generatedId
	]);
	const popupProps = import_react.useMemo(() => mergeProps(FOCUSABLE_POPUP_PROPS, typeahead.floating, listNavigation.floating, dismiss.floating), [
		typeahead.floating,
		listNavigation.floating,
		dismiss.floating
	]);
	const itemProps = listNavigation.item ?? EMPTY_OBJECT;
	useOnFirstRender(() => {
		store.update({
			popupProps,
			triggerProps: mergedTriggerProps
		});
	});
	useIsoLayoutEffect(() => {
		store.update({
			id: generatedId,
			modal,
			multiple,
			value,
			open,
			mounted,
			transitionStatus,
			popupProps,
			triggerProps: mergedTriggerProps,
			items,
			itemToStringLabel,
			itemToStringValue,
			isItemEqualToValue,
			openMethod: renderedOpenMethod
		});
	}, [
		store,
		generatedId,
		modal,
		multiple,
		value,
		open,
		mounted,
		transitionStatus,
		popupProps,
		mergedTriggerProps,
		items,
		itemToStringLabel,
		itemToStringValue,
		isItemEqualToValue,
		renderedOpenMethod
	]);
	const contextValue = import_react.useMemo(() => ({
		store,
		name,
		required,
		disabled,
		readOnly,
		multiple,
		highlightItemOnHover,
		setValue,
		setOpen,
		listRef,
		popupRef,
		scrollHandlerRef,
		handleScrollArrowVisibility,
		scrollArrowsMountedCountRef,
		itemProps,
		valueRef,
		valuesRef,
		labelsRef,
		typingRef,
		selectionRef,
		firstItemTextRef,
		selectedItemTextRef,
		validation,
		onOpenChangeComplete,
		alignItemWithTriggerActiveRef,
		initialValueRef
	}), [
		store,
		name,
		required,
		disabled,
		readOnly,
		multiple,
		highlightItemOnHover,
		setValue,
		setOpen,
		itemProps,
		validation,
		onOpenChangeComplete,
		handleScrollArrowVisibility
	]);
	const ref = useMergedRefs(inputRef, validation.inputRef);
	const hasMultipleSelection = multiple && Array.isArray(value) && value.length > 0;
	const hiddenInputName = multiple ? void 0 : name;
	const hiddenInputs = import_react.useMemo(() => {
		if (!multiple || !Array.isArray(value) || !name) return null;
		return value.map((v) => {
			const currentSerializedValue = stringifyAsValue(v, itemToStringValue);
			return /*#__PURE__*/ (0, import_jsx_runtime.jsx)("input", {
				type: "hidden",
				form,
				name,
				value: currentSerializedValue,
				disabled
			}, currentSerializedValue);
		});
	}, [
		multiple,
		value,
		form,
		name,
		itemToStringValue,
		disabled
	]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(SelectRootContext.Provider, {
		value: contextValue,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(SelectFloatingContext.Provider, {
			value: floatingContext,
			children: [
				children,
				/*#__PURE__*/ (0, import_jsx_runtime.jsx)("input", {
					...validation.getValidationProps(disabled, {
						onFocus() {
							store.state.triggerElement?.focus({ focusVisible: true });
						},
						onChange(event) {
							if (event.nativeEvent.defaultPrevented || disabled || readOnly) return;
							const nextValue = event.currentTarget.value;
							const details = createChangeEventDetails(none, event.nativeEvent);
							function handleChange() {
								if (multiple) return;
								const nextValueLower = nextValue.toLowerCase();
								let matchingIndex = valuesRef.current.findIndex((candidate) => stringifyAsValue(candidate, itemToStringValue).toLowerCase() === nextValueLower || stringifyAsLabel(candidate, itemToStringLabel).toLowerCase() === nextValueLower);
								if (matchingIndex === -1) matchingIndex = valuesRef.current.findIndex((_, index) => {
									const renderedLabel = labelsRef.current[index];
									return renderedLabel != null && renderedLabel.toLowerCase() === nextValueLower;
								});
								const matchingValue = matchingIndex === -1 ? void 0 : valuesRef.current[matchingIndex];
								if (matchingValue != null) setValue(matchingValue, details);
							}
							store.set("forceMount", true);
							queueMicrotask(handleChange);
						}
					}),
					id: generatedId && hiddenInputName == null ? `${generatedId}-hidden-input` : void 0,
					form,
					name: hiddenInputName,
					autoComplete,
					value: serializedValue,
					disabled,
					required: required && !hasMultipleSelection,
					readOnly,
					ref,
					style: name ? visuallyHiddenInput : visuallyHidden,
					tabIndex: -1,
					"aria-hidden": true,
					suppressHydrationWarning: true
				}),
				hiddenInputs
			]
		})
	});
}
//#endregion
//#region node_modules/@base-ui/react/utils/resolveAriaLabelledBy.mjs
function getDefaultLabelId(id) {
	return id == null ? void 0 : `${id}-label`;
}
function resolveAriaLabelledBy(fieldLabelId, localLabelId) {
	return fieldLabelId ?? localLabelId;
}
//#endregion
//#region node_modules/@base-ui/react/select/label/SelectLabel.mjs
/**
* An accessible label that is automatically associated with the select trigger.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectLabel = /*#__PURE__*/ import_react.forwardRef(function SelectLabel(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const elementPropsWithoutId = elementProps;
	delete elementPropsWithoutId.id;
	const fieldRootContext = useFieldRootContext();
	const { store } = useSelectRootContext();
	const triggerElement = useStore(store, selectors.triggerElement);
	const rootId = useStore(store, selectors.id);
	const labelProps = useLabel({
		id: getDefaultLabelId(rootId),
		fallbackControlId: triggerElement?.id ?? rootId,
		setLabelId(nextLabelId) {
			store.set("labelId", nextLabelId);
		}
	});
	return useRenderElement("div", componentProps, {
		ref: forwardedRef,
		state: fieldRootContext.state,
		props: [labelProps, elementProps],
		stateAttributesMapping: fieldValidityMapping
	});
});
SelectLabel.displayName = "SelectLabel";
//#endregion
//#region node_modules/@base-ui/react/select/trigger/SelectTrigger.mjs
var BOUNDARY_OFFSET = 2;
var SELECTED_DELAY = 400;
var stateAttributesMapping$4 = {
	...pressableTriggerOpenStateMapping,
	...fieldValidityMapping,
	popupSide: (side) => side ? { "data-popup-side": side } : null,
	value: () => null
};
/**
* A button that opens the select popup.
* Renders a `<button>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectTrigger = /*#__PURE__*/ import_react.forwardRef(function SelectTrigger(componentProps, forwardedRef) {
	const { render, className, id: idProp, disabled: disabledProp = false, nativeButton = true, style, ...elementProps } = componentProps;
	const { setTouched, setFocused, validationMode, state: fieldState, disabled: fieldDisabled } = useFieldRootContext();
	const { labelId: fieldLabelId } = useLabelableContext();
	const { store, setOpen, selectionRef, validation, readOnly, required, alignItemWithTriggerActiveRef, disabled: selectDisabled } = useSelectRootContext();
	const disabled = fieldDisabled || selectDisabled || disabledProp;
	const open = useStore(store, selectors.open);
	const mounted = useStore(store, selectors.mounted);
	const value = useStore(store, selectors.value);
	const triggerProps = useStore(store, selectors.triggerProps);
	const positionerElement = useStore(store, selectors.positionerElement);
	const listElement = useStore(store, selectors.listElement);
	const popupSideValue = useStore(store, selectors.popupSide);
	const rootId = useStore(store, selectors.id);
	const selectLabelId = useStore(store, selectors.labelId);
	const hasSelectedValue = useStore(store, selectors.hasSelectedValue);
	const popupSide = mounted && positionerElement ? popupSideValue : null;
	const id = idProp ?? rootId;
	const ariaLabelledBy = resolveAriaLabelledBy(fieldLabelId, selectLabelId);
	useLabelableId({ id });
	const positionerRef = useValueAsRef(positionerElement);
	const triggerRef = import_react.useRef(null);
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		native: nativeButton
	});
	const setTriggerElement = useStableCallback((element) => {
		store.set("triggerElement", element);
	});
	const timeoutFocus = useTimeout();
	const timeoutMouseDown = useTimeout();
	const selectedDelayTimeout = useTimeout();
	import_react.useEffect(() => {
		if (open) {
			selectedDelayTimeout.start(SELECTED_DELAY, () => {
				selectionRef.current.allowUnselectedMouseUp = true;
				selectionRef.current.allowSelectedMouseUp = true;
			});
			return () => {
				selectedDelayTimeout.clear();
			};
		}
		selectionRef.current = {
			allowSelectedMouseUp: false,
			allowUnselectedMouseUp: false,
			dragY: 0
		};
		timeoutMouseDown.clear();
	}, [
		open,
		selectionRef,
		timeoutMouseDown,
		selectedDelayTimeout
	]);
	const mergedProps = mergeProps(triggerProps, {
		id,
		role: "combobox",
		"aria-expanded": open ? "true" : "false",
		"aria-haspopup": "listbox",
		"aria-controls": open ? listElement?.id ?? getFloatingFocusElement(positionerElement)?.id : void 0,
		"aria-labelledby": ariaLabelledBy,
		"aria-readonly": readOnly || void 0,
		"aria-required": required || void 0,
		tabIndex: disabled ? -1 : 0,
		onFocus(event) {
			setFocused(true);
			if (open && alignItemWithTriggerActiveRef.current) setOpen(false, createChangeEventDetails(none, event.nativeEvent));
			timeoutFocus.start(0, () => {
				store.set("forceMount", true);
			});
		},
		onBlur(event) {
			if (contains(positionerElement, event.relatedTarget)) return;
			setTouched(true);
			setFocused(false);
			if (validationMode === "onBlur") validation.commit(value);
		},
		onMouseDown(event) {
			if (open) return;
			const doc = ownerDocument(event.currentTarget);
			function handleMouseUp(mouseEvent) {
				if (!triggerRef.current) return;
				const mouseUpTarget = mouseEvent.target;
				if (contains(triggerRef.current, mouseUpTarget) || contains(positionerRef.current, mouseUpTarget)) return;
				const bounds = getPseudoElementBounds(triggerRef.current);
				if (mouseEvent.clientX >= bounds.left - BOUNDARY_OFFSET && mouseEvent.clientX <= bounds.right + BOUNDARY_OFFSET && mouseEvent.clientY >= bounds.top - BOUNDARY_OFFSET && mouseEvent.clientY <= bounds.bottom + BOUNDARY_OFFSET) return;
				setOpen(false, createChangeEventDetails(cancelOpen, mouseEvent));
			}
			timeoutMouseDown.start(0, () => {
				doc.addEventListener("mouseup", handleMouseUp, { once: true });
			});
		}
	}, elementProps, getButtonProps);
	const props = validation.getValidationProps(disabled, mergedProps);
	props.role = "combobox";
	const state = {
		...fieldState,
		open,
		disabled,
		value,
		readOnly,
		popupSide,
		placeholder: !hasSelectedValue
	};
	return useRenderElement("button", componentProps, {
		ref: [
			forwardedRef,
			triggerRef,
			buttonRef,
			setTriggerElement
		],
		state,
		stateAttributesMapping: stateAttributesMapping$4,
		props
	});
});
SelectTrigger.displayName = "SelectTrigger";
//#endregion
//#region node_modules/@base-ui/react/select/value/SelectValue.mjs
var stateAttributesMapping$3 = { value: () => null };
/**
* A text label of the currently selected item.
* Renders a `<span>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectValue = /*#__PURE__*/ import_react.forwardRef(function SelectValue(componentProps, forwardedRef) {
	const { className, render, children: childrenProp, placeholder, style, ...elementProps } = componentProps;
	const { store, valueRef } = useSelectRootContext();
	const value = useStore(store, selectors.value);
	const items = useStore(store, selectors.items);
	const itemToStringLabel = useStore(store, selectors.itemToStringLabel);
	const hasSelectedValue = useStore(store, selectors.hasSelectedValue);
	const shouldCheckNullItemLabel = !hasSelectedValue && placeholder != null && childrenProp == null;
	const hasNullLabel = useStore(store, selectors.hasNullItemLabel, shouldCheckNullItemLabel);
	const state = {
		value,
		placeholder: !hasSelectedValue
	};
	let children = null;
	if (typeof childrenProp === "function") children = childrenProp(value);
	else if (childrenProp != null) children = childrenProp;
	else if (!hasSelectedValue && placeholder != null && !hasNullLabel) children = placeholder;
	else if (Array.isArray(value)) children = resolveMultipleLabels(value, items, itemToStringLabel);
	else children = resolveSelectedLabel(value, items, itemToStringLabel);
	return useRenderElement("span", componentProps, {
		state,
		ref: [forwardedRef, valueRef],
		props: [{ children }, elementProps],
		stateAttributesMapping: stateAttributesMapping$3
	});
});
SelectValue.displayName = "SelectValue";
//#endregion
//#region node_modules/@base-ui/react/select/icon/SelectIcon.mjs
/**
* An icon that indicates that the trigger button opens a select popup.
* Renders a `<span>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectIcon = /*#__PURE__*/ import_react.forwardRef(function SelectIcon(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = useSelectRootContext();
	return useRenderElement("span", componentProps, {
		state: { open: useStore(store, selectors.open) },
		ref: forwardedRef,
		props: [{
			"aria-hidden": true,
			children: "▼"
		}, elementProps],
		stateAttributesMapping: triggerOpenStateMapping
	});
});
SelectIcon.displayName = "SelectIcon";
//#endregion
//#region node_modules/@base-ui/react/select/portal/SelectPortalContext.mjs
var SelectPortalContext = /*#__PURE__*/ import_react.createContext(void 0);
SelectPortalContext.displayName = "SelectPortalContext";
//#endregion
//#region node_modules/@base-ui/react/select/portal/SelectPortal.mjs
/**
* A portal element that moves the popup to a different part of the DOM.
* By default, the portal element is appended to `<body>`.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectPortal = /*#__PURE__*/ import_react.forwardRef(function SelectPortal(portalProps, forwardedRef) {
	const { store } = useSelectRootContext();
	const mounted = useStore(store, selectors.mounted);
	const forceMount = useStore(store, selectors.forceMount);
	if (!(mounted || forceMount)) return null;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(SelectPortalContext.Provider, {
		value: true,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingPortal, {
			ref: forwardedRef,
			...portalProps
		})
	});
});
SelectPortal.displayName = "SelectPortal";
//#endregion
//#region node_modules/@base-ui/react/select/backdrop/SelectBackdrop.mjs
var stateAttributesMapping$2 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* An overlay displayed beneath the select popup.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectBackdrop = /*#__PURE__*/ import_react.forwardRef(function SelectBackdrop(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = useSelectRootContext();
	const open = useStore(store, selectors.open);
	const mounted = useStore(store, selectors.mounted);
	return useRenderElement("div", componentProps, {
		state: {
			open,
			transitionStatus: useStore(store, selectors.transitionStatus)
		},
		ref: forwardedRef,
		props: [{
			role: "presentation",
			hidden: !mounted,
			style: {
				userSelect: "none",
				WebkitUserSelect: "none"
			}
		}, elementProps],
		stateAttributesMapping: stateAttributesMapping$2
	});
});
SelectBackdrop.displayName = "SelectBackdrop";
//#endregion
//#region node_modules/@base-ui/react/select/positioner/SelectPositionerContext.mjs
var SelectPositionerContext = /*#__PURE__*/ import_react.createContext(void 0);
SelectPositionerContext.displayName = "SelectPositionerContext";
function useSelectPositionerContext() {
	const context = import_react.useContext(SelectPositionerContext);
	if (!context) throw new Error("Base UI: SelectPositionerContext is missing. SelectPositioner parts must be placed within <Select.Positioner>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/select/popup/utils.mjs
function clearStyles(element, originalStyles) {
	if (element) Object.assign(element.style, originalStyles);
}
var LIST_FUNCTIONAL_STYLES = {
	position: "relative",
	maxHeight: "100%",
	overflowX: "hidden",
	overflowY: "auto"
};
//#endregion
//#region node_modules/@base-ui/react/select/positioner/SelectPositioner.mjs
var FIXED = { position: "fixed" };
/**
* Positions the select popup.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectPositioner = /*#__PURE__*/ import_react.forwardRef(function SelectPositioner(componentProps, forwardedRef) {
	const { anchor, positionMethod = "absolute", className, render, side = "bottom", align = "center", sideOffset = 0, alignOffset = 0, collisionBoundary = "clipping-ancestors", collisionPadding, arrowPadding = 5, sticky = false, disableAnchorTracking, alignItemWithTrigger = true, collisionAvoidance = DROPDOWN_COLLISION_AVOIDANCE, style, ...elementProps } = componentProps;
	const { store, listRef, labelsRef, alignItemWithTriggerActiveRef, selectedItemTextRef, valuesRef, initialValueRef, popupRef, setValue } = useSelectRootContext();
	const floatingRootContext = useSelectFloatingContext();
	const open = useStore(store, selectors.open);
	const mounted = useStore(store, selectors.mounted);
	const modal = useStore(store, selectors.modal);
	const value = useStore(store, selectors.value);
	const openMethod = useStore(store, selectors.openMethod);
	const positionerElement = useStore(store, selectors.positionerElement);
	const triggerElement = useStore(store, selectors.triggerElement);
	const isItemEqualToValue = useStore(store, selectors.isItemEqualToValue);
	const transitionStatus = useStore(store, selectors.transitionStatus);
	const scrollUpArrowRef = import_react.useRef(null);
	const scrollDownArrowRef = import_react.useRef(null);
	const [controlledAlignItemWithTrigger, setControlledAlignItemWithTrigger] = import_react.useState(alignItemWithTrigger);
	const alignItemWithTriggerActive = mounted && controlledAlignItemWithTrigger && openMethod !== "touch";
	if (!mounted && controlledAlignItemWithTrigger !== alignItemWithTrigger) setControlledAlignItemWithTrigger(alignItemWithTrigger);
	useIsoLayoutEffect(() => {
		if (!mounted) {
			if (selectors.scrollUpArrowVisible(store.state)) store.set("scrollUpArrowVisible", false);
			if (selectors.scrollDownArrowVisible(store.state)) store.set("scrollDownArrowVisible", false);
		}
	}, [store, mounted]);
	import_react.useImperativeHandle(alignItemWithTriggerActiveRef, () => alignItemWithTriggerActive);
	useAnchoredPopupScrollLock((alignItemWithTriggerActive || modal) && open, openMethod === "touch", positionerElement, triggerElement);
	const positioning = useAnchorPositioning({
		anchor,
		floatingRootContext,
		positionMethod,
		mounted,
		side,
		sideOffset,
		align,
		alignOffset,
		arrowPadding,
		collisionBoundary,
		collisionPadding,
		sticky,
		disableAnchorTracking: disableAnchorTracking ?? alignItemWithTriggerActive,
		collisionAvoidance,
		keepMounted: true
	});
	const renderedSide = alignItemWithTriggerActive ? "none" : positioning.side;
	const positionerStyles = alignItemWithTriggerActive ? FIXED : positioning.positionerStyles;
	const state = {
		open,
		side: renderedSide,
		align: positioning.align,
		anchorHidden: positioning.anchorHidden
	};
	useIsoLayoutEffect(() => {
		store.set("popupSide", positioning.side);
	}, [store, positioning.side]);
	const element = usePositioner(componentProps, state, {
		styles: positionerStyles,
		transitionStatus,
		props: elementProps,
		refs: [forwardedRef, useStableCallback((element) => {
			store.set("positionerElement", element);
		})],
		hidden: !mounted,
		inert: !open
	});
	const prevMapSizeRef = import_react.useRef(0);
	const onMapChange = useStableCallback((map) => {
		if (map.size === 0 && prevMapSizeRef.current === 0) return;
		if (valuesRef.current.length === 0) return;
		const prevSize = prevMapSizeRef.current;
		prevMapSizeRef.current = map.size;
		if (map.size === prevSize) return;
		const eventDetails = createChangeEventDetails(none);
		if (prevSize !== 0 && !store.state.multiple && value !== null) {
			if (findItemIndex(valuesRef.current, value, isItemEqualToValue) === -1) {
				const initialSelectedValue = initialValueRef.current;
				const nextValue = initialSelectedValue != null && findItemIndex(valuesRef.current, initialSelectedValue, isItemEqualToValue) !== -1 ? initialSelectedValue : null;
				setValue(nextValue, eventDetails);
				if (nextValue === null) {
					store.set("selectedIndex", null);
					selectedItemTextRef.current = null;
				}
			}
		}
		if (prevSize !== 0 && store.state.multiple && Array.isArray(value)) {
			const hasVisibleItem = (selectedItemValue) => findItemIndex(valuesRef.current, selectedItemValue, isItemEqualToValue) !== -1;
			const nextValue = value.filter((selectedItemValue) => hasVisibleItem(selectedItemValue));
			if (nextValue.length !== value.length || nextValue.some((selectedItemValue) => !selectedValueIncludes(value, selectedItemValue, isItemEqualToValue))) {
				setValue(nextValue, eventDetails);
				if (nextValue.length === 0) {
					store.set("selectedIndex", null);
					selectedItemTextRef.current = null;
				}
			}
		}
		if (open && alignItemWithTriggerActive) {
			store.update({
				scrollUpArrowVisible: false,
				scrollDownArrowVisible: false
			});
			const stylesToClear = { height: "" };
			clearStyles(positionerElement, stylesToClear);
			clearStyles(popupRef.current, stylesToClear);
		}
	});
	const contextValue = import_react.useMemo(() => ({
		...positioning,
		side: renderedSide,
		alignItemWithTriggerActive,
		setControlledAlignItemWithTrigger,
		scrollUpArrowRef,
		scrollDownArrowRef
	}), [
		positioning,
		renderedSide,
		alignItemWithTriggerActive,
		setControlledAlignItemWithTrigger
	]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(CompositeList, {
		elementsRef: listRef,
		labelsRef,
		onMapChange,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(SelectPositionerContext.Provider, {
			value: contextValue,
			children: [mounted && modal && /*#__PURE__*/ (0, import_jsx_runtime.jsx)(InternalBackdrop, {
				inert: inertValue(!open),
				cutout: triggerElement
			}), element]
		})
	});
});
SelectPositioner.displayName = "SelectPositioner";
//#endregion
//#region node_modules/@base-ui/react/utils/styles.mjs
var DISABLE_SCROLLBAR_CLASS_NAME = "base-ui-disable-scrollbar";
var styleDisableScrollbar = {
	className: DISABLE_SCROLLBAR_CLASS_NAME,
	getElement(nonce) {
		return /*#__PURE__*/ (0, import_jsx_runtime.jsx)("style", {
			nonce,
			href: DISABLE_SCROLLBAR_CLASS_NAME,
			precedence: "base-ui:low",
			children: `.${DISABLE_SCROLLBAR_CLASS_NAME}{scrollbar-width:none}.${DISABLE_SCROLLBAR_CLASS_NAME}::-webkit-scrollbar{display:none}`
		});
	}
};
styleDisableScrollbar.getElement.displayName = "styleDisableScrollbar.getElement";
//#endregion
//#region node_modules/@base-ui/react/select/popup/SelectPopup.mjs
var stateAttributesMapping$1 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* A container for the select list.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectPopup = /*#__PURE__*/ import_react.forwardRef(function SelectPopup(componentProps, forwardedRef) {
	const { render, className, style, finalFocus, ...elementProps } = componentProps;
	const { store, popupRef, onOpenChangeComplete, setOpen, valueRef, firstItemTextRef, selectedItemTextRef, multiple, handleScrollArrowVisibility, scrollHandlerRef, listRef, highlightItemOnHover } = useSelectRootContext();
	const { side, align, alignItemWithTriggerActive, isPositioned, setControlledAlignItemWithTrigger } = useSelectPositionerContext();
	const insideToolbar = useToolbarRootContext(true) != null;
	const floatingRootContext = useSelectFloatingContext();
	const direction = useDirection();
	const { nonce, disableStyleElements } = useCSPContext();
	const id = useStore(store, selectors.id);
	const open = useStore(store, selectors.open);
	const openMethod = useStore(store, selectors.openMethod);
	const mounted = useStore(store, selectors.mounted);
	const popupProps = useStore(store, selectors.popupProps);
	const transitionStatus = useStore(store, selectors.transitionStatus);
	const triggerElement = useStore(store, selectors.triggerElement);
	const positionerElement = useStore(store, selectors.positionerElement);
	const listElement = useStore(store, selectors.listElement);
	const reachedMaxHeightRef = import_react.useRef(false);
	const initialPlacedRef = import_react.useRef(false);
	const originalPositionerStylesRef = import_react.useRef({});
	const scrollArrowFrame = useAnimationFrame();
	const handleScroll = useStableCallback((scroller) => {
		if (!positionerElement || !popupRef.current || !initialPlacedRef.current) return;
		if (reachedMaxHeightRef.current || !alignItemWithTriggerActive) {
			handleScrollArrowVisibility();
			return;
		}
		const isTopPositioned = positionerElement.style.top === "0px";
		const isBottomPositioned = positionerElement.style.bottom === "0px";
		if (!isTopPositioned && !isBottomPositioned) {
			handleScrollArrowVisibility();
			return;
		}
		const scale = getScale(positionerElement);
		const currentHeight = normalizeSize(positionerElement.getBoundingClientRect().height, "y", scale);
		const doc = ownerDocument(positionerElement);
		const win = getWindow(positionerElement);
		const positionerStyles = win.getComputedStyle(positionerElement);
		const marginTop = parseFloat(positionerStyles.marginTop);
		const marginBottom = parseFloat(positionerStyles.marginBottom);
		const maxPopupHeight = getMaxPopupHeight(win.getComputedStyle(popupRef.current));
		const maxAvailableHeight = Math.min(doc.documentElement.clientHeight - marginTop - marginBottom, maxPopupHeight);
		const scrollTop = scroller.scrollTop;
		const maxScrollTop = getMaxScrollTop(scroller);
		let nextPositionerHeight = 0;
		let nextScrollTop = null;
		let setReachedMax = false;
		let scrollToMax = false;
		const setHeight = (height) => {
			positionerElement.style.height = `${height}px`;
		};
		const handleSmallDiff = (diff, targetScrollTop) => {
			const heightDelta = clamp(diff, 0, maxAvailableHeight - currentHeight);
			if (heightDelta > 0) setHeight(currentHeight + heightDelta);
			scroller.scrollTop = targetScrollTop;
			if (maxAvailableHeight - (currentHeight + heightDelta) <= 1) reachedMaxHeightRef.current = true;
			handleScrollArrowVisibility();
		};
		const diff = isTopPositioned ? maxScrollTop - scrollTop : scrollTop;
		const nextHeight = Math.min(currentHeight + diff, maxAvailableHeight);
		nextPositionerHeight = nextHeight;
		if (diff <= 1) {
			handleSmallDiff(diff, isTopPositioned ? maxScrollTop : 0);
			return;
		}
		if (maxAvailableHeight - nextHeight > 1) if (isTopPositioned) scrollToMax = true;
		else nextScrollTop = 0;
		else {
			setReachedMax = true;
			if (isBottomPositioned && scrollTop < maxScrollTop) nextScrollTop = scrollTop - (diff - (currentHeight + diff - maxAvailableHeight));
		}
		nextPositionerHeight = Math.ceil(nextPositionerHeight);
		if (nextPositionerHeight !== 0) setHeight(nextPositionerHeight);
		if (scrollToMax || nextScrollTop != null) {
			const nextMaxScrollTop = getMaxScrollTop(scroller);
			const target = scrollToMax ? nextMaxScrollTop : clamp(nextScrollTop, 0, nextMaxScrollTop);
			if (Math.abs(scroller.scrollTop - target) > 1) scroller.scrollTop = target;
		}
		if (setReachedMax || nextPositionerHeight >= maxAvailableHeight - 1) reachedMaxHeightRef.current = true;
		handleScrollArrowVisibility();
	});
	import_react.useImperativeHandle(scrollHandlerRef, () => handleScroll, [handleScroll]);
	useOpenChangeComplete({
		open,
		ref: popupRef,
		onComplete() {
			if (open) onOpenChangeComplete?.(true);
		}
	});
	const state = {
		open,
		transitionStatus,
		side,
		align
	};
	useIsoLayoutEffect(() => {
		if (!positionerElement || !popupRef.current || Object.keys(originalPositionerStylesRef.current).length) return;
		originalPositionerStylesRef.current = {
			top: positionerElement.style.top || "0",
			left: positionerElement.style.left || "0",
			right: positionerElement.style.right,
			height: positionerElement.style.height,
			bottom: positionerElement.style.bottom,
			minHeight: positionerElement.style.minHeight,
			maxHeight: positionerElement.style.maxHeight,
			marginTop: positionerElement.style.marginTop,
			marginBottom: positionerElement.style.marginBottom
		};
	}, [popupRef, positionerElement]);
	useIsoLayoutEffect(() => {
		if (open || alignItemWithTriggerActive) return;
		initialPlacedRef.current = false;
		reachedMaxHeightRef.current = false;
		clearStyles(positionerElement, originalPositionerStylesRef.current);
	}, [
		open,
		alignItemWithTriggerActive,
		positionerElement,
		popupRef
	]);
	useIsoLayoutEffect(() => {
		const popupElement = popupRef.current;
		if (!open || !triggerElement || !positionerElement || !popupElement || alignItemWithTriggerActive && !isPositioned || store.state.transitionStatus === "ending") return;
		if (!alignItemWithTriggerActive) {
			initialPlacedRef.current = true;
			scrollArrowFrame.request(handleScrollArrowVisibility);
			popupElement.style.removeProperty("--transform-origin");
			return;
		}
		const restoreTransformStyles = unsetTransformStyles(popupElement);
		popupElement.style.removeProperty("--transform-origin");
		try {
			let textElement = selectedItemTextRef.current;
			if (!textElement?.isConnected) textElement = !selectors.hasSelectedValue(store.state) && firstItemTextRef.current?.isConnected ? firstItemTextRef.current : null;
			const valueElement = valueRef.current;
			const win = getWindow(positionerElement);
			const positionerStyles = win.getComputedStyle(positionerElement);
			const popupStyles = win.getComputedStyle(popupElement);
			const doc = ownerDocument(triggerElement);
			const scale = getScale(triggerElement);
			const triggerRect = normalizeRect(triggerElement.getBoundingClientRect(), scale);
			const positionerRect = normalizeRect(positionerElement.getBoundingClientRect(), scale);
			const triggerHeight = triggerRect.height;
			const scroller = listElement || popupElement;
			const scrollHeight = scroller.scrollHeight;
			const borderBottom = parseFloat(popupStyles.borderBottomWidth);
			const marginTop = parseFloat(positionerStyles.marginTop) || 10;
			const marginBottom = parseFloat(positionerStyles.marginBottom) || 10;
			const minHeight = parseFloat(positionerStyles.minHeight) || 100;
			const maxPopupHeight = getMaxPopupHeight(popupStyles);
			const paddingLeft = 5;
			const paddingRight = 5;
			const triggerCollisionThreshold = 20;
			const viewportHeight = doc.documentElement.clientHeight - marginTop - marginBottom;
			const viewportWidth = doc.documentElement.clientWidth;
			const availableSpaceBeneathTrigger = viewportHeight - triggerRect.bottom + triggerHeight;
			let textRect;
			let alignedLeft = direction === "rtl" ? triggerRect.right - positionerRect.width : triggerRect.left;
			let offsetY = 0;
			if (textElement && valueElement) {
				const valueRect = normalizeRect(valueElement.getBoundingClientRect(), scale);
				textRect = normalizeRect(textElement.getBoundingClientRect(), scale);
				alignedLeft = positionerRect.left + (direction === "rtl" ? valueRect.right - textRect.right : valueRect.left - textRect.left);
				const valueCenterFromTriggerTop = valueRect.top - triggerRect.top + valueRect.height / 2;
				offsetY = textRect.top - positionerRect.top + textRect.height / 2 - valueCenterFromTriggerTop;
			}
			const idealHeight = availableSpaceBeneathTrigger + offsetY + marginBottom + borderBottom;
			let height = Math.min(viewportHeight, idealHeight);
			const maxHeight = viewportHeight - marginTop - marginBottom;
			const scrollTop = idealHeight - height;
			const maxRight = viewportWidth - paddingRight;
			positionerElement.style.left = `${clamp(alignedLeft, paddingLeft, maxRight - positionerRect.width)}px`;
			positionerElement.style.height = `${height}px`;
			positionerElement.style.maxHeight = "none";
			positionerElement.style.marginTop = `${marginTop}px`;
			positionerElement.style.marginBottom = `${marginBottom}px`;
			popupElement.style.height = "100%";
			const maxScrollTop = getMaxScrollTop(scroller);
			const isTopPositioned = scrollTop >= maxScrollTop - 1;
			if (isTopPositioned) height = Math.min(viewportHeight, positionerRect.height) - (scrollTop - maxScrollTop);
			const fallbackToAlignPopupToTrigger = triggerRect.top < triggerCollisionThreshold || triggerRect.bottom > viewportHeight - triggerCollisionThreshold || Math.ceil(height) + 1 < Math.min(scrollHeight, minHeight);
			const isPinchZoomed = (win.visualViewport?.scale ?? 1) !== 1 && webkit;
			if (fallbackToAlignPopupToTrigger || isPinchZoomed) {
				initialPlacedRef.current = true;
				clearStyles(positionerElement, originalPositionerStylesRef.current);
				setControlledAlignItemWithTrigger(false);
				return;
			}
			const initialHeight = Math.max(minHeight, height);
			if (isTopPositioned) {
				const topOffset = Math.max(0, viewportHeight - idealHeight);
				positionerElement.style.top = positionerRect.height >= maxHeight ? "0" : `${topOffset}px`;
				positionerElement.style.height = `${height}px`;
				scroller.scrollTop = getMaxScrollTop(scroller);
			} else {
				positionerElement.style.bottom = "0";
				scroller.scrollTop = scrollTop;
			}
			if (textRect) {
				const popupTop = positionerRect.top;
				const popupHeight = positionerRect.height;
				const textCenterY = textRect.top + textRect.height / 2;
				const clampedY = clamp(popupHeight > 0 ? (textCenterY - popupTop) / popupHeight * 100 : 50, 0, 100);
				popupElement.style.setProperty("--transform-origin", `50% ${clampedY}%`);
			}
			if (initialHeight === viewportHeight || height >= maxPopupHeight) reachedMaxHeightRef.current = true;
			handleScrollArrowVisibility();
			if (highlightItemOnHover && store.state.selectedIndex === null && store.state.activeIndex === null && listRef.current[0] != null) store.set("activeIndex", 0);
			initialPlacedRef.current = true;
		} finally {
			restoreTransformStyles();
		}
	}, [
		store,
		open,
		positionerElement,
		triggerElement,
		valueRef,
		firstItemTextRef,
		selectedItemTextRef,
		popupRef,
		handleScrollArrowVisibility,
		alignItemWithTriggerActive,
		setControlledAlignItemWithTrigger,
		scrollArrowFrame,
		listElement,
		listRef,
		highlightItemOnHover,
		direction,
		isPositioned
	]);
	import_react.useEffect(() => {
		if (!alignItemWithTriggerActive || !positionerElement || !open) return;
		const win = getWindow(positionerElement);
		function handleResize(event) {
			setOpen(false, createChangeEventDetails(windowResize, event));
		}
		return addEventListener(win, "resize", handleResize);
	}, [
		setOpen,
		alignItemWithTriggerActive,
		positionerElement,
		open
	]);
	const defaultProps = {
		...listElement ? {
			role: "presentation",
			"aria-orientation": void 0
		} : {
			role: "listbox",
			"aria-multiselectable": multiple || void 0,
			id: `${id}-list`
		},
		onKeyDown(event) {
			if (insideToolbar && COMPOSITE_KEYS.has(event.key)) event.stopPropagation();
		},
		onScroll(event) {
			if (listElement) return;
			handleScroll(event.currentTarget);
		},
		...alignItemWithTriggerActive && { style: listElement ? { height: "100%" } : LIST_FUNCTIONAL_STYLES }
	};
	const element = useRenderElement("div", componentProps, {
		ref: [forwardedRef, popupRef],
		state,
		stateAttributesMapping: stateAttributesMapping$1,
		props: [
			popupProps,
			defaultProps,
			getDisabledMountTransitionStyles(transitionStatus),
			{ className: !listElement && alignItemWithTriggerActive ? styleDisableScrollbar.className : void 0 },
			elementProps
		]
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(import_react.Fragment, { children: [!disableStyleElements && styleDisableScrollbar.getElement(nonce), /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingFocusManager, {
		context: floatingRootContext,
		modal: false,
		disabled: !mounted,
		openInteractionType: openMethod,
		returnFocus: finalFocus,
		restoreFocus: true,
		children: element
	})] });
});
SelectPopup.displayName = "SelectPopup";
function getMaxPopupHeight(popupStyles) {
	const maxHeightStyle = popupStyles.maxHeight || "";
	return maxHeightStyle.endsWith("px") ? parseFloat(maxHeightStyle) || Infinity : Infinity;
}
function getMaxScrollTop(scroller) {
	return getMaxScrollOffset(scroller.scrollHeight, scroller.clientHeight);
}
function getScale(element) {
	return platform.getScale(element);
}
function normalizeSize(size, axis, scale) {
	return size / scale[axis];
}
function normalizeRect(rect, scale) {
	return rectToClientRect({
		x: normalizeSize(rect.x, "x", scale),
		y: normalizeSize(rect.y, "y", scale),
		width: normalizeSize(rect.width, "x", scale),
		height: normalizeSize(rect.height, "y", scale)
	});
}
var TRANSFORM_STYLE_RESETS = [
	["transform", "none"],
	["scale", "1"],
	["translate", "0 0"]
];
function unsetTransformStyles(popupElement) {
	const { style } = popupElement;
	const originalStyles = {};
	for (const [property, value] of TRANSFORM_STYLE_RESETS) {
		originalStyles[property] = style.getPropertyValue(property);
		style.setProperty(property, value, "important");
	}
	return () => {
		for (const [property] of TRANSFORM_STYLE_RESETS) {
			const originalValue = originalStyles[property];
			if (originalValue) style.setProperty(property, originalValue);
			else style.removeProperty(property);
		}
	};
}
//#endregion
//#region node_modules/@base-ui/react/select/list/SelectList.mjs
/**
* A container for the select items.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectList = /*#__PURE__*/ import_react.forwardRef(function SelectList(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store, scrollHandlerRef } = useSelectRootContext();
	const { alignItemWithTriggerActive } = useSelectPositionerContext();
	const hasScrollArrows = useStore(store, selectors.hasScrollArrows);
	const openMethod = useStore(store, selectors.openMethod);
	const multiple = useStore(store, selectors.multiple);
	const defaultProps = {
		id: `${useStore(store, selectors.id)}-list`,
		role: "listbox",
		"aria-multiselectable": multiple || void 0,
		onScroll(event) {
			scrollHandlerRef.current?.(event.currentTarget);
		},
		...alignItemWithTriggerActive && { style: LIST_FUNCTIONAL_STYLES },
		className: hasScrollArrows && openMethod !== "touch" ? styleDisableScrollbar.className : void 0
	};
	return useRenderElement("div", componentProps, {
		ref: [forwardedRef, useStableCallback((element) => {
			store.set("listElement", element);
		})],
		props: [defaultProps, elementProps]
	});
});
SelectList.displayName = "SelectList";
//#endregion
//#region node_modules/@base-ui/react/select/item/SelectItemContext.mjs
var SelectItemContext = /*#__PURE__*/ import_react.createContext(void 0);
SelectItemContext.displayName = "SelectItemContext";
function useSelectItemContext() {
	const context = import_react.useContext(SelectItemContext);
	if (!context) throw new Error("Base UI: SelectItemContext is missing. SelectItem parts must be placed within <Select.Item>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/select/item/SelectItem.mjs
/**
* An individual option in the select popup.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectItem = /*#__PURE__*/ import_react.memo(/*#__PURE__*/ import_react.forwardRef(function SelectItem(componentProps, forwardedRef) {
	const { render, className, style, value: itemValue = null, label, disabled = false, nativeButton = false, ...elementProps } = componentProps;
	const textRef = import_react.useRef(null);
	const listItem = useCompositeListItem({
		label,
		textRef,
		indexGuessBehavior: IndexGuessBehavior.GuessFromOrder
	});
	const { store, itemProps, setOpen, setValue, selectionRef, typingRef, valuesRef, multiple, selectedItemTextRef, disabled: selectDisabled, readOnly } = useSelectRootContext();
	const highlighted = useStore(store, selectors.isActive, listItem.index);
	const open = useStore(store, selectors.open);
	const selected = useStore(store, selectors.isSelected, itemValue);
	const selectedByFocus = useStore(store, selectors.isSelectedByFocus, listItem.index);
	const isItemEqualToValue = useStore(store, selectors.isItemEqualToValue);
	const index = listItem.index;
	const hasRegistered = index !== -1;
	const itemRef = import_react.useRef(null);
	useIsoLayoutEffect(() => {
		if (!hasRegistered) return;
		const values = valuesRef.current;
		values[index] = itemValue;
		return () => {
			delete values[index];
		};
	}, [
		hasRegistered,
		index,
		itemValue,
		valuesRef
	]);
	useIsoLayoutEffect(() => {
		if (!hasRegistered) return;
		const selectedValue = store.state.value;
		let selectedCandidate = selectedValue;
		if (multiple && Array.isArray(selectedValue)) selectedCandidate = selectedValue.length > 0 ? selectedValue[selectedValue.length - 1] : void 0;
		if (selectedCandidate !== void 0 && compareItemEquality(itemValue, selectedCandidate, isItemEqualToValue)) {
			store.set("selectedIndex", index);
			if (textRef.current) selectedItemTextRef.current = textRef.current;
		}
	}, [
		hasRegistered,
		index,
		multiple,
		isItemEqualToValue,
		store,
		itemValue,
		selectedItemTextRef
	]);
	const lastKeyRef = import_react.useRef(null);
	const pointerTypeRef = import_react.useRef("mouse");
	const allowMouseSelectionRef = import_react.useRef(false);
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		focusableWhenDisabled: true,
		native: nativeButton,
		composite: true
	});
	const state = {
		disabled,
		selected,
		highlighted
	};
	function commitSelection(event) {
		if (selectDisabled || readOnly) return;
		const selectedValue = store.state.value;
		if (multiple) {
			const currentValue = Array.isArray(selectedValue) ? selectedValue : [];
			const nextValue = selected ? removeItem(currentValue, itemValue, isItemEqualToValue) : [...currentValue, itemValue];
			setValue(nextValue, createChangeEventDetails(itemPress, event));
		} else {
			setValue(itemValue, createChangeEventDetails(itemPress, event));
			setOpen(false, createChangeEventDetails(itemPress, event));
		}
	}
	function resetDragMovement() {
		selectionRef.current.dragY = 0;
	}
	const defaultProps = {
		role: "option",
		"aria-selected": selected,
		tabIndex: open && highlighted ? 0 : -1,
		onKeyDown(event) {
			lastKeyRef.current = event.key;
			store.set("activeIndex", index);
			if (event.key === " " && typingRef.current) event.preventDefault();
		},
		onClick(event) {
			const isMouseClick = event.type === "click" && pointerTypeRef.current !== "touch";
			const clickPointerType = event.nativeEvent.pointerType;
			const isVirtualMouseClick = isMouseClick && isVirtualClick(event.nativeEvent) && (clickPointerType !== void 0 || highlighted);
			const isInvalidMouseClick = isMouseClick && !isVirtualMouseClick && !allowMouseSelectionRef.current;
			allowMouseSelectionRef.current = false;
			if (event.type === "keydown" && lastKeyRef.current === null) return;
			if (disabled || event.type === "keydown" && lastKeyRef.current === " " && typingRef.current || isInvalidMouseClick) return;
			lastKeyRef.current = null;
			commitSelection(event.nativeEvent);
		},
		onPointerEnter(event) {
			pointerTypeRef.current = event.pointerType;
		},
		onPointerMove(event) {
			if (event.pointerType === "mouse" && event.buttons === 1) {
				const selection = selectionRef.current;
				selection.dragY += event.movementY;
				if (selection.dragY ** 2 >= 64) selection.allowUnselectedMouseUp = true;
			}
		},
		onPointerDown(event) {
			pointerTypeRef.current = event.pointerType;
			allowMouseSelectionRef.current = true;
			resetDragMovement();
		},
		onMouseUp() {
			resetDragMovement();
			if (disabled || pointerTypeRef.current === "touch") return;
			if (allowMouseSelectionRef.current) return;
			const disallowSelectedMouseUp = !selectionRef.current.allowSelectedMouseUp && selected;
			const disallowUnselectedMouseUp = !selectionRef.current.allowUnselectedMouseUp && !selected;
			if (disallowSelectedMouseUp || disallowUnselectedMouseUp) return;
			allowMouseSelectionRef.current = true;
			itemRef.current?.click();
			allowMouseSelectionRef.current = false;
		}
	};
	const element = useRenderElement("div", componentProps, {
		ref: [
			buttonRef,
			forwardedRef,
			listItem.ref,
			itemRef
		],
		state,
		props: [
			itemProps,
			defaultProps,
			elementProps,
			getButtonProps
		]
	});
	const contextValue = import_react.useMemo(() => ({
		selected,
		index,
		textRef,
		selectedByFocus,
		hasRegistered
	}), [
		selected,
		index,
		textRef,
		selectedByFocus,
		hasRegistered
	]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(SelectItemContext.Provider, {
		value: contextValue,
		children: element
	});
}));
SelectItem.displayName = "SelectItem";
//#endregion
//#region node_modules/@base-ui/react/select/item-indicator/SelectItemIndicator.mjs
/**
* Indicates whether the select item is selected.
* Renders a `<span>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectItemIndicator = /*#__PURE__*/ import_react.forwardRef(function SelectItemIndicator(componentProps, forwardedRef) {
	const keepMounted = componentProps.keepMounted ?? false;
	const { selected } = useSelectItemContext();
	if (!(keepMounted || selected)) return null;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(Inner, {
		...componentProps,
		ref: forwardedRef
	});
});
SelectItemIndicator.displayName = "SelectItemIndicator";
var Inner = /*#__PURE__*/ import_react.memo(/*#__PURE__*/ import_react.forwardRef((componentProps, forwardedRef) => {
	const { render, className, style, keepMounted, ...elementProps } = componentProps;
	const { selected } = useSelectItemContext();
	const indicatorRef = import_react.useRef(null);
	const { transitionStatus, setMounted } = useTransitionStatus(selected);
	const element = useRenderElement("span", componentProps, {
		ref: [forwardedRef, indicatorRef],
		state: {
			selected,
			transitionStatus
		},
		props: [{
			"aria-hidden": true,
			children: "✔️"
		}, elementProps],
		stateAttributesMapping: transitionStatusMapping
	});
	useOpenChangeComplete({
		open: selected,
		ref: indicatorRef,
		onComplete() {
			if (!selected) setMounted(false);
		}
	});
	return element;
}));
Inner.displayName = "Inner";
//#endregion
//#region node_modules/@base-ui/react/select/item-text/SelectItemText.mjs
/**
* A text label of the select item.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectItemText = /*#__PURE__*/ import_react.memo(/*#__PURE__*/ import_react.forwardRef(function SelectItemText(componentProps, forwardedRef) {
	const { index, textRef, selectedByFocus, hasRegistered } = useSelectItemContext();
	const { firstItemTextRef, selectedItemTextRef } = useSelectRootContext();
	const { render, className, style, ...elementProps } = componentProps;
	return useRenderElement("div", componentProps, {
		ref: [
			import_react.useCallback((node) => {
				if (!node) return;
				if (hasRegistered && index === 0) firstItemTextRef.current = node;
				if (hasRegistered && selectedByFocus) selectedItemTextRef.current = node;
			}, [
				firstItemTextRef,
				selectedItemTextRef,
				index,
				selectedByFocus,
				hasRegistered
			]),
			forwardedRef,
			textRef
		],
		props: elementProps
	});
}));
SelectItemText.displayName = "SelectItemText";
//#endregion
//#region node_modules/@base-ui/react/select/arrow/SelectArrow.mjs
var stateAttributesMapping = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* Displays an element positioned against the select popup anchor.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectArrow = /*#__PURE__*/ import_react.forwardRef(function SelectArrow(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = useSelectRootContext();
	const { side, align, arrowRef, arrowStyles, arrowUncentered, alignItemWithTriggerActive } = useSelectPositionerContext();
	const element = useRenderElement("div", componentProps, {
		state: {
			open: useStore(store, selectors.open),
			side,
			align,
			uncentered: arrowUncentered
		},
		ref: [arrowRef, forwardedRef],
		props: [{
			style: arrowStyles,
			"aria-hidden": true
		}, elementProps],
		stateAttributesMapping
	});
	if (alignItemWithTriggerActive) return null;
	return element;
});
SelectArrow.displayName = "SelectArrow";
//#endregion
//#region node_modules/@base-ui/react/select/scroll-arrow/SelectScrollArrow.mjs
/**
* @internal
*/
var SelectScrollArrow = /*#__PURE__*/ import_react.forwardRef(function SelectScrollArrow(componentProps, forwardedRef) {
	const { render, className, style, direction, keepMounted = false, ...elementProps } = componentProps;
	const isUp = direction === "up";
	const { store, popupRef, listRef, handleScrollArrowVisibility, scrollArrowsMountedCountRef } = useSelectRootContext();
	const { side, scrollDownArrowRef, scrollUpArrowRef } = useSelectPositionerContext();
	const stateVisible = useStore(store, isUp ? selectors.scrollUpArrowVisible : selectors.scrollDownArrowVisible);
	const openMethod = useStore(store, selectors.openMethod);
	const visible = stateVisible && openMethod !== "touch";
	const timeout = useTimeout();
	const scrollArrowRef = isUp ? scrollUpArrowRef : scrollDownArrowRef;
	const { mounted, transitionStatus, setMounted } = useTransitionStatus(visible);
	useIsoLayoutEffect(() => {
		scrollArrowsMountedCountRef.current += 1;
		if (!store.state.hasScrollArrows) store.set("hasScrollArrows", true);
		return () => {
			scrollArrowsMountedCountRef.current = Math.max(0, scrollArrowsMountedCountRef.current - 1);
			if (scrollArrowsMountedCountRef.current === 0 && store.state.hasScrollArrows) store.set("hasScrollArrows", false);
		};
	}, [store, scrollArrowsMountedCountRef]);
	useOpenChangeComplete({
		open: visible,
		ref: scrollArrowRef,
		onComplete() {
			if (!visible) setMounted(false);
		}
	});
	const element = useRenderElement("div", componentProps, {
		ref: [forwardedRef, scrollArrowRef],
		state: {
			direction,
			visible,
			side,
			transitionStatus
		},
		props: [{
			"aria-hidden": true,
			children: isUp ? "▲" : "▼",
			style: { position: "absolute" },
			onMouseMove(event) {
				if (event.movementX === 0 && event.movementY === 0 || timeout.isStarted()) return;
				store.set("activeIndex", null);
				function scrollNextItem() {
					const scroller = store.state.listElement ?? popupRef.current;
					if (!scroller) return;
					store.set("activeIndex", null);
					handleScrollArrowVisibility();
					const maxScrollTop = getMaxScrollOffset(scroller.scrollHeight, scroller.clientHeight);
					const scrollTop = normalizeScrollOffset(scroller.scrollTop, maxScrollTop);
					const isScrolledToEdge = scrollTop === (isUp ? 0 : maxScrollTop);
					const items = listRef.current;
					if (scrollTop !== scroller.scrollTop) scroller.scrollTop = scrollTop;
					if (items.length === 0) store.set(isUp ? "scrollUpArrowVisible" : "scrollDownArrowVisible", !isScrolledToEdge);
					if (isScrolledToEdge) {
						timeout.clear();
						return;
					}
					if (items.length > 0) {
						const scrollArrowHeight = scrollArrowRef.current?.offsetHeight || 0;
						scroller.scrollTop = getTargetScrollTop(items, isUp, scrollTop, scroller.clientHeight, scrollArrowHeight, maxScrollTop);
					}
					timeout.start(40, scrollNextItem);
				}
				timeout.start(40, scrollNextItem);
			},
			onMouseLeave() {
				timeout.clear();
			}
		}, elementProps],
		stateAttributesMapping: transitionStatusMapping
	});
	if (!(mounted || keepMounted)) return null;
	return element;
});
SelectScrollArrow.displayName = "SelectScrollArrow";
function getTargetScrollTop(items, isUp, scrollTop, clientHeight, scrollArrowHeight, maxScrollTop) {
	if (isUp) {
		let firstVisibleIndex = 0;
		const visibleTop = scrollTop + scrollArrowHeight - 1;
		for (let i = 0; i < items.length; i += 1) {
			const item = items[i];
			if (item && item.offsetTop >= visibleTop) {
				firstVisibleIndex = i;
				break;
			}
		}
		const targetIndex = Math.max(0, firstVisibleIndex - 1);
		const targetItem = items[targetIndex];
		return targetIndex < firstVisibleIndex && targetItem ? normalizeScrollOffset(targetItem.offsetTop - scrollArrowHeight, maxScrollTop) : 0;
	}
	let lastVisibleIndex = items.length - 1;
	const visibleBottom = scrollTop + clientHeight - scrollArrowHeight + 1;
	for (let i = 0; i < items.length; i += 1) {
		const item = items[i];
		if (item && item.offsetTop + item.offsetHeight > visibleBottom) {
			lastVisibleIndex = Math.max(0, i - 1);
			break;
		}
	}
	const targetIndex = Math.min(items.length - 1, lastVisibleIndex + 1);
	const targetItem = items[targetIndex];
	return targetIndex > lastVisibleIndex && targetItem ? normalizeScrollOffset(targetItem.offsetTop + targetItem.offsetHeight - clientHeight + scrollArrowHeight, maxScrollTop) : maxScrollTop;
}
//#endregion
//#region node_modules/@base-ui/react/select/scroll-down-arrow/SelectScrollDownArrow.mjs
/**
* An element that scrolls the select popup down when hovered. Does not render when using touch input.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectScrollDownArrow = /*#__PURE__*/ import_react.forwardRef(function SelectScrollDownArrow(props, forwardedRef) {
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(SelectScrollArrow, {
		...props,
		ref: forwardedRef,
		direction: "down"
	});
});
SelectScrollDownArrow.displayName = "SelectScrollDownArrow";
//#endregion
//#region node_modules/@base-ui/react/select/scroll-up-arrow/SelectScrollUpArrow.mjs
/**
* An element that scrolls the select popup up when hovered. Does not render when using touch input.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectScrollUpArrow = /*#__PURE__*/ import_react.forwardRef(function SelectScrollUpArrow(props, forwardedRef) {
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(SelectScrollArrow, {
		...props,
		ref: forwardedRef,
		direction: "up"
	});
});
SelectScrollUpArrow.displayName = "SelectScrollUpArrow";
//#endregion
//#region node_modules/@base-ui/react/select/group/SelectGroupContext.mjs
var SelectGroupContext = /*#__PURE__*/ import_react.createContext(void 0);
SelectGroupContext.displayName = "SelectGroupContext";
function useSelectGroupContext() {
	const context = import_react.useContext(SelectGroupContext);
	if (context === void 0) throw new Error("Base UI: SelectGroupContext is missing. SelectGroup parts must be placed within <Select.Group>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/select/group/SelectGroup.mjs
/**
* Groups related select items with the corresponding label.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectGroup = /*#__PURE__*/ import_react.forwardRef(function SelectGroup(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const [labelId, setLabelId] = import_react.useState();
	const contextValue = import_react.useMemo(() => ({
		labelId,
		setLabelId
	}), [labelId, setLabelId]);
	const element = useRenderElement("div", componentProps, {
		ref: forwardedRef,
		props: [{
			role: "group",
			"aria-labelledby": labelId
		}, elementProps]
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(SelectGroupContext.Provider, {
		value: contextValue,
		children: element
	});
});
SelectGroup.displayName = "SelectGroup";
//#endregion
//#region node_modules/@base-ui/react/select/group-label/SelectGroupLabel.mjs
/**
* An accessible label that is automatically associated with its parent group.
* Renders a `<div>` element.
*
* Documentation: [Base UI Select](https://base-ui.com/react/components/select)
*/
var SelectGroupLabel = /*#__PURE__*/ import_react.forwardRef(function SelectGroupLabel(componentProps, forwardedRef) {
	const { render, className, style, id: idProp, ...elementProps } = componentProps;
	const { setLabelId } = useSelectGroupContext();
	const id = useBaseUiId(idProp);
	useIsoLayoutEffect(() => {
		setLabelId(id);
	}, [id, setLabelId]);
	return useRenderElement("div", componentProps, {
		ref: forwardedRef,
		props: [{ id }, elementProps]
	});
});
SelectGroupLabel.displayName = "SelectGroupLabel";
//#endregion
//#region node_modules/@base-ui/react/select/index.parts.mjs
var index_parts_exports = /* @__PURE__ */ __exportAll({
	Arrow: () => SelectArrow,
	Backdrop: () => SelectBackdrop,
	Group: () => SelectGroup,
	GroupLabel: () => SelectGroupLabel,
	Icon: () => SelectIcon,
	Item: () => SelectItem,
	ItemIndicator: () => SelectItemIndicator,
	ItemText: () => SelectItemText,
	Label: () => SelectLabel,
	List: () => SelectList,
	Popup: () => SelectPopup,
	Portal: () => SelectPortal,
	Positioner: () => SelectPositioner,
	Root: () => SelectRoot,
	ScrollDownArrow: () => SelectScrollDownArrow,
	ScrollUpArrow: () => SelectScrollUpArrow,
	Separator: () => Separator,
	Trigger: () => SelectTrigger,
	Value: () => SelectValue
});
//#endregion
export { index_parts_exports as Select };
