import { n as __exportAll, r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
import { _ as isLastTraversableNode, f as getParentNode, g as isHTMLElement, h as isElement, i as SafeReact, p as getWindow, r as useStableCallback, t as useIsoLayoutEffect } from "./useIsoLayoutEffect-DrOR77jl.js";
import { a as warn, c as useRefWithInit, n as EMPTY_ARRAY, r as EMPTY_OBJECT, s as useMergedRefs, t as useRenderElement } from "./useRenderElement-BiX6Dyza.js";
import { r as mergeProps } from "./merge-props-B1zstas5.js";
import { r as useCompositeRootContext, t as useButton } from "./useButton-DFSPkxH_.js";
import { t as useControlled } from "./useControlled-CXMaCmX-.js";
import { i as ownerDocument, n as contains, r as getTarget, t as activeElement } from "./shadowDom-BbNDe3Dh.js";
import { b as useId, h as triggerFocus, l as itemPress, m as siblingOpen, n as cancelOpen, s as imperativeAction, t as createChangeEventDetails, y as useBaseUiId } from "./createBaseUIEventDetails-BNfSv2gm.js";
import { t as require_jsx_runtime } from "./react_jsx-runtime.js";
import { a as transitionStatusMapping, n as useOpenChangeComplete, r as useAnimationsFinished, t as useTransitionStatus } from "./useTransitionStatus-CDr8WmsC.js";
import { A as FloatingNode, B as POPUP_COLLISION_AVOIDANCE, C as fastComponent, D as useDismiss, F as FloatingTreeStore, H as createAttribute, I as FloatingPortal, J as FocusGuard, M as useFloatingNodeId, N as useFloatingParentNodeId, O as useClick, P as useFloatingTree, T as createSelector, X as mergeCleanups, Z as addEventListener, _ as useTriggerRegistration, a as PopupTriggerMap, b as ReactStore, bt as triggerOpenStateMapping, d as useInitialOpenSync, et as isTargetInsideEnabledTrigger, f as useOpenStateTransitions, g as useTriggerDataForwarding, gt as useTimeout, i as InternalBackdrop, j as FloatingTree, k as FloatingFocusManager, l as setPopupOpenState, mt as mac, nt as isTypeableElement, o as FOCUSABLE_POPUP_PROPS, p as usePopupInteractionProps, pt as webkit, rt as matchesFocusVisible, s as attachPreventUnmountOnClose, t as useOpenInteractionType, u as useImplicitActiveTrigger, v as useSyncedFloatingRootContext, vt as popupStateMapping, w as fastComponentRef, yt as pressableTriggerOpenStateMapping, z as DROPDOWN_COLLISION_AVOIDANCE } from "./useOpenInteractionType-fml9RCjU.js";
import { a as useHoverFloatingInteraction, i as useHoverReferenceInteraction, n as useTriggerFocusGuards, r as safePolygon, t as usePopupViewport } from "./usePopupViewport-9tQdVQKu.js";
import { t as useDirection } from "./DirectionContext-O998dM5m.js";
import { s as COMPOSITE_KEYS, t as inertValue } from "./inertValue-J_gNalGy.js";
import { a as adaptiveOrigin, i as useAnchorPositioning, n as useAnchoredPopupScrollLock, o as getDisabledMountTransitionStyles, r as usePositioner, s as useToolbarRootContext } from "./usePreviousValue-D_tVHlXk.js";
import { r as popupStoreSelectors, t as createInitialPopupStoreState } from "./store-DgHEBjVg.js";
import { i as useListNavigation, n as getPseudoElementBounds, r as useTypeahead, t as Separator } from "./Separator-Cw4HdUXQ.js";
import { i as useCompositeListItem, n as CompositeList, t as isElementDisabled } from "./isElementDisabled-T2-7pWM4.js";
import { t as useCompositeItem } from "./useCompositeItem-o3_Mt2wQ.js";
//#region node_modules/@base-ui/react/floating-ui-react/hooks/useFocus.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
var isMacSafari = mac && webkit;
/**
* Opens the floating element while the reference element has focus, like CSS
* `:focus`.
* @see https://floating-ui.com/docs/useFocus
*/
function useFocus(context, props = {}) {
	const { enabled = true, delay } = props;
	const store = "rootStore" in context ? context.rootStore : context;
	const { events, dataRef } = store.context;
	const blockFocusRef = import_react.useRef(false);
	const blockedReferenceRef = import_react.useRef(null);
	const keyboardModalityRef = import_react.useRef(true);
	const timeout = useTimeout();
	import_react.useEffect(() => {
		const domReference = store.select("domReferenceElement");
		if (!enabled) return;
		const win = getWindow(domReference);
		function onBlur() {
			const currentDomReference = store.select("domReferenceElement");
			if (!store.select("open") && isHTMLElement(currentDomReference) && currentDomReference === activeElement(ownerDocument(currentDomReference))) blockFocusRef.current = true;
		}
		function onKeyDown() {
			keyboardModalityRef.current = true;
		}
		function onPointerDown() {
			keyboardModalityRef.current = false;
		}
		return mergeCleanups(addEventListener(win, "blur", onBlur), isMacSafari && addEventListener(win, "keydown", onKeyDown, true), isMacSafari && addEventListener(win, "pointerdown", onPointerDown, true));
	}, [store, enabled]);
	import_react.useEffect(() => {
		if (!enabled) return;
		function onOpenChangeLocal(details) {
			if (details.reason === "trigger-press" || details.reason === "escape-key") {
				const referenceElement = store.select("domReferenceElement");
				if (isElement(referenceElement)) {
					blockedReferenceRef.current = referenceElement;
					blockFocusRef.current = true;
				}
			}
		}
		events.on("openchange", onOpenChangeLocal);
		return () => {
			events.off("openchange", onOpenChangeLocal);
		};
	}, [
		events,
		enabled,
		store
	]);
	const reference = import_react.useMemo(() => {
		function resetBlockedFocus() {
			blockFocusRef.current = false;
			blockedReferenceRef.current = null;
		}
		return {
			onMouseLeave() {
				resetBlockedFocus();
			},
			onFocus(event) {
				const focusTarget = event.currentTarget;
				if (blockFocusRef.current) {
					if (blockedReferenceRef.current === focusTarget) return;
					resetBlockedFocus();
				}
				const target = getTarget(event.nativeEvent);
				if (isElement(target)) {
					if (isMacSafari && !event.relatedTarget) {
						if (!keyboardModalityRef.current && !isTypeableElement(target)) return;
					} else if (!matchesFocusVisible(target)) return;
				}
				const movedFromOtherEnabledTrigger = isTargetInsideEnabledTrigger(event.relatedTarget, store.context.triggerElements);
				const { nativeEvent, currentTarget } = event;
				const delayValue = typeof delay === "function" ? delay() : delay;
				if (store.select("open") && movedFromOtherEnabledTrigger || delayValue === 0 || delayValue === void 0) {
					store.setOpen(true, createChangeEventDetails(triggerFocus, nativeEvent, currentTarget));
					return;
				}
				timeout.start(delayValue, () => {
					if (blockFocusRef.current) return;
					store.setOpen(true, createChangeEventDetails(triggerFocus, nativeEvent, currentTarget));
				});
			},
			onBlur(event) {
				resetBlockedFocus();
				const relatedTarget = event.relatedTarget;
				const nativeEvent = event.nativeEvent;
				const movedToFocusGuard = isElement(relatedTarget) && relatedTarget.hasAttribute(createAttribute("focus-guard")) && relatedTarget.getAttribute("data-type") === "outside";
				timeout.start(0, () => {
					const domReference = store.select("domReferenceElement");
					const activeEl = activeElement(ownerDocument(domReference));
					if (!relatedTarget && activeEl === domReference) return;
					if (contains(dataRef.current.floatingContext?.refs.floating.current, activeEl) || contains(domReference, activeEl) || movedToFocusGuard) return;
					if (isTargetInsideEnabledTrigger(relatedTarget ?? activeEl, store.context.triggerElements)) return;
					store.setOpen(false, createChangeEventDetails(triggerFocus, nativeEvent));
				});
			}
		};
	}, [
		dataRef,
		delay,
		store,
		timeout
	]);
	return import_react.useMemo(() => enabled ? {
		reference,
		trigger: reference
	} : {}, [enabled, reference]);
}
//#endregion
//#region node_modules/@base-ui/react/menu/positioner/MenuPositionerContext.mjs
var MenuPositionerContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuPositionerContext.displayName = "MenuPositionerContext";
function useMenuPositionerContext(optional) {
	const context = import_react.useContext(MenuPositionerContext);
	if (context === void 0 && !optional) throw new Error("Base UI: MenuPositionerContext is missing. MenuPositioner parts must be placed within <Menu.Positioner>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/root/MenuRootContext.mjs
var MenuRootContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuRootContext.displayName = "MenuRootContext";
function useMenuRootContext(optional) {
	const context = import_react.useContext(MenuRootContext);
	if (context === void 0 && !optional) throw new Error("Base UI: MenuRootContext is missing. Menu parts must be placed within <Menu.Root>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/arrow/MenuArrow.mjs
/**
* Displays an element positioned against the menu anchor.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuArrow = /*#__PURE__*/ import_react.forwardRef(function MenuArrow(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = useMenuRootContext();
	const { arrowRef, side, align, arrowUncentered, arrowStyles } = useMenuPositionerContext();
	const state = {
		open: store.useState("open"),
		side,
		align,
		uncentered: arrowUncentered
	};
	return useRenderElement("div", componentProps, {
		ref: [arrowRef, forwardedRef],
		stateAttributesMapping: popupStateMapping,
		state,
		props: {
			style: arrowStyles,
			"aria-hidden": true,
			...elementProps
		}
	});
});
MenuArrow.displayName = "MenuArrow";
//#endregion
//#region node_modules/@base-ui/react/context-menu/root/ContextMenuRootContext.mjs
var ContextMenuRootContext = /*#__PURE__*/ import_react.createContext(void 0);
ContextMenuRootContext.displayName = "ContextMenuRootContext";
function useContextMenuRootContext(optional = true) {
	const context = import_react.useContext(ContextMenuRootContext);
	if (context === void 0 && !optional) throw new Error("Base UI: ContextMenuRootContext is missing. ContextMenu parts must be placed within <ContextMenu.Root>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/backdrop/MenuBackdrop.mjs
var stateAttributesMapping$2 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* An overlay displayed beneath the menu popup.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuBackdrop = /*#__PURE__*/ import_react.forwardRef(function MenuBackdrop(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = useMenuRootContext();
	const open = store.useState("open");
	const mounted = store.useState("mounted");
	const transitionStatus = store.useState("transitionStatus");
	const lastOpenChangeReason = store.useState("lastOpenChangeReason");
	const contextMenuContext = useContextMenuRootContext();
	const state = {
		open,
		transitionStatus
	};
	return useRenderElement("div", componentProps, {
		ref: contextMenuContext?.backdropRef ? [forwardedRef, contextMenuContext.backdropRef] : forwardedRef,
		state,
		stateAttributesMapping: stateAttributesMapping$2,
		props: [{
			role: "presentation",
			hidden: !mounted,
			style: {
				pointerEvents: lastOpenChangeReason === "trigger-hover" ? "none" : void 0,
				userSelect: "none",
				WebkitUserSelect: "none"
			}
		}, elementProps]
	});
});
MenuBackdrop.displayName = "MenuBackdrop";
//#endregion
//#region node_modules/@base-ui/react/menu/checkbox-item/MenuCheckboxItemContext.mjs
var MenuCheckboxItemContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuCheckboxItemContext.displayName = "MenuCheckboxItemContext";
function useMenuCheckboxItemContext() {
	const context = import_react.useContext(MenuCheckboxItemContext);
	if (context === void 0) throw new Error("Base UI: MenuCheckboxItemContext is missing. MenuCheckboxItem parts must be placed within <Menu.CheckboxItem>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/item/useMenuItemCommonProps.mjs
/**
* Returns common props shared by all menu item types.
* This hook extracts the shared logic for id, role, tabIndex, onKeyDown,
* onMouseMove, onClick, and onMouseUp handlers.
*/
function useMenuItemCommonProps(params) {
	const { closeOnClick, highlighted, id, nodeId, store, typingRef, itemRef, itemMetadata } = params;
	const { events: menuEvents } = store.useState("floatingTreeRoot");
	const open = store.useState("open");
	const contextMenuContext = useContextMenuRootContext(true);
	const isContextMenu = contextMenuContext !== void 0;
	return import_react.useMemo(() => ({
		id,
		role: "menuitem",
		tabIndex: open && highlighted ? 0 : -1,
		onKeyDown(event) {
			if (event.key === " " && typingRef?.current) event.preventDefault();
		},
		onMouseMove(event) {
			if (!nodeId) return;
			menuEvents.emit("itemhover", {
				nodeId,
				target: event.currentTarget
			});
		},
		onClick(event) {
			if (closeOnClick) menuEvents.emit("close", {
				domEvent: event,
				reason: itemPress
			});
		},
		onMouseUp(event) {
			if (contextMenuContext) {
				const initialCursorPoint = contextMenuContext.initialCursorPointRef.current;
				contextMenuContext.initialCursorPointRef.current = null;
				if (isContextMenu && initialCursorPoint && Math.abs(event.clientX - initialCursorPoint.x) <= 1 && Math.abs(event.clientY - initialCursorPoint.y) <= 1) return;
				if (isContextMenu && !mac && event.button === 2) return;
			}
			if (itemRef.current && store.context.allowMouseUpTriggerRef.current && (!isContextMenu || event.button === 2)) {
				if (!itemMetadata || itemMetadata.type === "regular-item") itemRef.current.click();
			}
		}
	}), [
		closeOnClick,
		highlighted,
		id,
		menuEvents,
		nodeId,
		open,
		store,
		typingRef,
		itemRef,
		contextMenuContext,
		isContextMenu,
		itemMetadata
	]);
}
//#endregion
//#region node_modules/@base-ui/react/menu/item/useMenuItem.mjs
var REGULAR_ITEM = { type: "regular-item" };
function useMenuItem(params) {
	const { closeOnClick, disabled: disabledProp = false, highlighted, id, store, typingRef = store.context.typingRef, nativeButton, itemMetadata, nodeId } = params;
	const rootDisabled = store.useState("disabled");
	const disabled = disabledProp || rootDisabled;
	const itemRef = import_react.useRef(null);
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		focusableWhenDisabled: true,
		native: nativeButton,
		composite: true
	});
	const commonProps = useMenuItemCommonProps({
		closeOnClick,
		highlighted,
		id,
		nodeId,
		store,
		typingRef,
		itemRef,
		itemMetadata
	});
	const getItemProps = import_react.useCallback((externalProps) => {
		return mergeProps(commonProps, { onMouseEnter() {
			if (itemMetadata.type !== "submenu-trigger") return;
			itemMetadata.setActive();
		} }, externalProps, getButtonProps);
	}, [
		commonProps,
		getButtonProps,
		itemMetadata
	]);
	const mergedRef = useMergedRefs(itemRef, buttonRef);
	return import_react.useMemo(() => ({
		getItemProps,
		itemRef: mergedRef
	}), [getItemProps, mergedRef]);
}
//#endregion
//#region node_modules/@base-ui/react/menu/checkbox-item/MenuCheckboxItemDataAttributes.mjs
var MenuCheckboxItemDataAttributes = /*#__PURE__*/ function(MenuCheckboxItemDataAttributes) {
	/**
	* Present when the menu checkbox item is checked.
	*/
	MenuCheckboxItemDataAttributes["checked"] = "data-checked";
	/**
	* Present when the menu checkbox item is not checked.
	*/
	MenuCheckboxItemDataAttributes["unchecked"] = "data-unchecked";
	/**
	* Present when the menu checkbox item is disabled.
	*/
	MenuCheckboxItemDataAttributes["disabled"] = "data-disabled";
	/**
	* Present when the menu checkbox item is highlighted.
	*/
	MenuCheckboxItemDataAttributes["highlighted"] = "data-highlighted";
	return MenuCheckboxItemDataAttributes;
}({});
//#endregion
//#region node_modules/@base-ui/react/menu/utils/stateAttributesMapping.mjs
var itemMapping = {
	checked(value) {
		if (value) return { [MenuCheckboxItemDataAttributes.checked]: "" };
		return { [MenuCheckboxItemDataAttributes.unchecked]: "" };
	},
	...transitionStatusMapping
};
//#endregion
//#region node_modules/@base-ui/react/menu/checkbox-item/MenuCheckboxItem.mjs
var import_jsx_runtime = require_jsx_runtime();
/**
* A menu item that toggles a setting on or off.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuCheckboxItem = /*#__PURE__*/ import_react.forwardRef(function MenuCheckboxItem(componentProps, forwardedRef) {
	const { render, className, id: idProp, label, nativeButton = false, disabled = false, closeOnClick = false, checked: checkedProp, defaultChecked, onCheckedChange, style, ...elementProps } = componentProps;
	const listItem = useCompositeListItem({ label });
	const menuPositionerContext = useMenuPositionerContext(true);
	const id = useBaseUiId(idProp);
	const { store } = useMenuRootContext();
	const highlighted = store.useState("isActive", listItem.index);
	const itemProps = store.useState("itemProps");
	const [checked, setChecked] = useControlled({
		controlled: checkedProp,
		default: defaultChecked ?? false,
		name: "MenuCheckboxItem",
		state: "checked"
	});
	const { getItemProps, itemRef } = useMenuItem({
		closeOnClick,
		disabled,
		highlighted,
		id,
		store,
		nativeButton,
		nodeId: menuPositionerContext?.context.nodeId,
		itemMetadata: REGULAR_ITEM
	});
	const state = import_react.useMemo(() => ({
		disabled,
		highlighted,
		checked
	}), [
		disabled,
		highlighted,
		checked
	]);
	function handleClick(event) {
		const details = createChangeEventDetails(itemPress, event.nativeEvent, void 0, { preventUnmountOnClose() {} });
		onCheckedChange?.(!checked, details);
		if (details.isCanceled) return;
		setChecked((currentlyChecked) => !currentlyChecked);
	}
	const element = useRenderElement("div", componentProps, {
		state,
		stateAttributesMapping: itemMapping,
		props: [
			itemProps,
			{
				role: "menuitemcheckbox",
				"aria-checked": checked,
				onClick: handleClick
			},
			elementProps,
			getItemProps
		],
		ref: [
			itemRef,
			forwardedRef,
			listItem.ref
		]
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuCheckboxItemContext.Provider, {
		value: state,
		children: element
	});
});
MenuCheckboxItem.displayName = "MenuCheckboxItem";
//#endregion
//#region node_modules/@base-ui/react/menu/checkbox-item-indicator/MenuCheckboxItemIndicator.mjs
/**
* Indicates whether the checkbox item is ticked.
* Renders a `<span>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuCheckboxItemIndicator = /*#__PURE__*/ import_react.forwardRef(function MenuCheckboxItemIndicator(componentProps, forwardedRef) {
	const { render, className, style, keepMounted = false, ...elementProps } = componentProps;
	const item = useMenuCheckboxItemContext();
	const indicatorRef = import_react.useRef(null);
	const { transitionStatus, setMounted } = useTransitionStatus(item.checked);
	useOpenChangeComplete({
		open: item.checked,
		ref: indicatorRef,
		onComplete() {
			if (!item.checked) setMounted(false);
		}
	});
	return useRenderElement("span", componentProps, {
		state: {
			checked: item.checked,
			disabled: item.disabled,
			highlighted: item.highlighted,
			transitionStatus
		},
		ref: [forwardedRef, indicatorRef],
		stateAttributesMapping: itemMapping,
		props: {
			"aria-hidden": true,
			...elementProps
		},
		enabled: keepMounted || item.checked
	});
});
MenuCheckboxItemIndicator.displayName = "MenuCheckboxItemIndicator";
//#endregion
//#region node_modules/@base-ui/react/menu/group/MenuGroupContext.mjs
var MenuGroupContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuGroupContext.displayName = "MenuGroupContext";
function useMenuGroupRootContext() {
	const context = import_react.useContext(MenuGroupContext);
	if (context === void 0) throw new Error("Base UI: MenuGroupContext is missing. Menu group parts must be used within <Menu.Group> or <Menu.RadioGroup>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/group/MenuGroup.mjs
/**
* Groups related menu items with the corresponding label.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuGroup = /*#__PURE__*/ import_react.forwardRef(function MenuGroup(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const [labelId, setLabelId] = import_react.useState(void 0);
	const element = useRenderElement("div", componentProps, {
		ref: forwardedRef,
		props: {
			role: "group",
			"aria-labelledby": labelId,
			...elementProps
		}
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuGroupContext.Provider, {
		value: setLabelId,
		children: element
	});
});
MenuGroup.displayName = "MenuGroup";
//#endregion
//#region node_modules/@base-ui/react/menu/group-label/MenuGroupLabel.mjs
/**
* An accessible label that is automatically associated with its parent group.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuGroupLabel = /*#__PURE__*/ import_react.forwardRef(function MenuGroupLabel(componentProps, forwardedRef) {
	const { render, className, style, id: idProp, ...elementProps } = componentProps;
	const id = useBaseUiId(idProp);
	const setLabelId = useMenuGroupRootContext();
	useIsoLayoutEffect(() => {
		setLabelId(id);
		return () => {
			setLabelId(void 0);
		};
	}, [setLabelId, id]);
	return useRenderElement("div", componentProps, {
		ref: forwardedRef,
		props: {
			id,
			role: "presentation",
			...elementProps
		}
	});
});
MenuGroupLabel.displayName = "MenuGroupLabel";
//#endregion
//#region node_modules/@base-ui/react/menu/item/MenuItem.mjs
/**
* An individual interactive item in the menu.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuItem = /*#__PURE__*/ import_react.forwardRef(function MenuItem(componentProps, forwardedRef) {
	const { render, className, id: idProp, label, nativeButton = false, disabled = false, closeOnClick = true, style, ...elementProps } = componentProps;
	const listItem = useCompositeListItem({ label });
	const menuPositionerContext = useMenuPositionerContext(true);
	const id = useBaseUiId(idProp);
	const { store } = useMenuRootContext();
	const highlighted = store.useState("isActive", listItem.index);
	const itemProps = store.useState("itemProps");
	const { getItemProps, itemRef } = useMenuItem({
		closeOnClick,
		disabled,
		highlighted,
		id,
		store,
		nativeButton,
		nodeId: menuPositionerContext?.context.nodeId,
		itemMetadata: REGULAR_ITEM
	});
	return useRenderElement("div", componentProps, {
		state: {
			disabled,
			highlighted
		},
		props: [
			itemProps,
			elementProps,
			getItemProps
		],
		ref: [
			itemRef,
			forwardedRef,
			listItem.ref
		]
	});
});
MenuItem.displayName = "MenuItem";
//#endregion
//#region node_modules/@base-ui/react/menu/link-item/MenuLinkItem.mjs
/**
* A link in the menu that can be used to navigate to a different page or section.
* Renders an `<a>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuLinkItem = /*#__PURE__*/ import_react.forwardRef(function MenuLinkItem(componentProps, forwardedRef) {
	const { render, className, id: idProp, label, closeOnClick = false, style, ...elementProps } = componentProps;
	const linkRef = import_react.useRef(null);
	const listItem = useCompositeListItem({ label });
	const nodeId = useMenuPositionerContext(true)?.context.nodeId;
	const id = useBaseUiId(idProp);
	const { store } = useMenuRootContext();
	const highlighted = store.useState("isActive", listItem.index);
	const itemProps = store.useState("itemProps");
	const typingRef = store.context.typingRef;
	const { getButtonProps, buttonRef } = useButton({
		native: false,
		composite: true
	});
	const commonProps = useMenuItemCommonProps({
		closeOnClick,
		highlighted,
		id,
		nodeId,
		store,
		typingRef,
		itemRef: linkRef
	});
	function getItemProps(externalProps) {
		return mergeProps(commonProps, externalProps, getButtonProps);
	}
	return useRenderElement("a", componentProps, {
		state: { highlighted },
		props: [
			itemProps,
			elementProps,
			getItemProps
		],
		ref: [
			linkRef,
			buttonRef,
			forwardedRef,
			listItem.ref
		]
	});
});
MenuLinkItem.displayName = "MenuLinkItem";
//#endregion
//#region node_modules/@base-ui/react/menu/popup/MenuPopup.mjs
var stateAttributesMapping$1 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* A container for the menu items.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuPopup = /*#__PURE__*/ import_react.forwardRef(function MenuPopup(componentProps, forwardedRef) {
	const { render, className, style, finalFocus, ...elementProps } = componentProps;
	const { store } = useMenuRootContext();
	const { side, align } = useMenuPositionerContext();
	const insideToolbar = useToolbarRootContext(true) != null;
	const open = store.useState("open");
	const transitionStatus = store.useState("transitionStatus");
	const popupProps = store.useState("popupProps");
	const mounted = store.useState("mounted");
	const instantType = store.useState("instantType");
	const triggerElement = store.useState("activeTriggerElement");
	const parent = store.useState("parent");
	const lastOpenChangeReason = store.useState("lastOpenChangeReason");
	const rootId = store.useState("rootId");
	const floatingContext = store.useState("floatingRootContext");
	const floatingTreeRoot = store.useState("floatingTreeRoot");
	const closeDelay = store.useState("closeDelay");
	const activeTriggerElement = store.useState("activeTriggerElement");
	const hoverEnabled = store.useState("hoverEnabled");
	const disabled = store.useState("disabled");
	const openMethod = store.useState("openMethod");
	const isContextMenu = parent.type === "context-menu";
	useOpenChangeComplete({
		open,
		ref: store.context.popupRef,
		onComplete() {
			if (open) store.context.onOpenChangeComplete?.(true);
		}
	});
	import_react.useEffect(() => {
		function handleClose(event) {
			store.setOpen(false, createChangeEventDetails(event.reason, event.domEvent));
		}
		floatingTreeRoot.events.on("close", handleClose);
		return () => {
			floatingTreeRoot.events.off("close", handleClose);
		};
	}, [floatingTreeRoot.events, store]);
	useHoverFloatingInteraction(floatingContext, {
		enabled: hoverEnabled && !disabled && !isContextMenu && parent.type !== "menubar",
		closeDelay
	});
	const setPopupElement = import_react.useCallback((element) => {
		store.set("popupElement", element);
	}, [store]);
	const element = useRenderElement("div", componentProps, {
		state: {
			transitionStatus,
			side,
			align,
			open,
			nested: parent.type === "menu",
			instant: instantType
		},
		ref: [
			forwardedRef,
			store.context.popupRef,
			setPopupElement
		],
		stateAttributesMapping: stateAttributesMapping$1,
		props: [
			popupProps,
			{ onKeyDown(event) {
				if (insideToolbar && COMPOSITE_KEYS.has(event.key)) event.stopPropagation();
			} },
			getDisabledMountTransitionStyles(transitionStatus),
			elementProps,
			{ "data-rootownerid": rootId }
		]
	});
	let returnFocus = parent.type === void 0 || isContextMenu;
	if (triggerElement || parent.type === "menubar" && lastOpenChangeReason !== "outside-press") returnFocus = true;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingFocusManager, {
		context: floatingContext,
		openInteractionType: openMethod,
		modal: isContextMenu,
		disabled: !mounted,
		returnFocus: finalFocus === void 0 ? returnFocus : finalFocus,
		initialFocus: parent.type !== "menu",
		restoreFocus: true,
		externalTree: parent.type !== "menubar" ? floatingTreeRoot : void 0,
		previousFocusableElement: activeTriggerElement,
		nextFocusableElement: parent.type === void 0 ? store.context.triggerFocusTargetRef : void 0,
		beforeContentFocusGuardRef: parent.type === void 0 ? store.context.beforeContentFocusGuardRef : void 0,
		children: element
	});
});
MenuPopup.displayName = "MenuPopup";
//#endregion
//#region node_modules/@base-ui/react/menu/portal/MenuPortalContext.mjs
var MenuPortalContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuPortalContext.displayName = "MenuPortalContext";
function useMenuPortalContext() {
	const value = import_react.useContext(MenuPortalContext);
	if (value === void 0) throw new Error("Base UI: <Menu.Portal> is missing.");
	return value;
}
//#endregion
//#region node_modules/@base-ui/react/menu/portal/MenuPortal.mjs
/**
* A portal element that moves the popup to a different part of the DOM.
* By default, the portal element is appended to `<body>`.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuPortal = /*#__PURE__*/ import_react.forwardRef(function MenuPortal(props, forwardedRef) {
	const { keepMounted = false, ...portalProps } = props;
	const { store } = useMenuRootContext();
	if (!(store.useState("mounted") || keepMounted)) return null;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuPortalContext.Provider, {
		value: keepMounted,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingPortal, {
			ref: forwardedRef,
			...portalProps
		})
	});
});
MenuPortal.displayName = "MenuPortal";
//#endregion
//#region node_modules/@base-ui/react/menu/positioner/MenuPositioner.mjs
/**
* Positions the menu popup against the trigger.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuPositioner = /*#__PURE__*/ import_react.forwardRef(function MenuPositioner(componentProps, forwardedRef) {
	const { anchor: anchorProp, positionMethod: positionMethodProp = "absolute", className, render, side, align: alignProp, sideOffset: sideOffsetProp = 0, alignOffset: alignOffsetProp = 0, collisionBoundary = "clipping-ancestors", collisionPadding = 5, arrowPadding = 5, sticky = false, disableAnchorTracking = false, collisionAvoidance: collisionAvoidanceProp = DROPDOWN_COLLISION_AVOIDANCE, style, ...elementProps } = componentProps;
	const { store } = useMenuRootContext();
	const keepMounted = useMenuPortalContext();
	const contextMenuContext = useContextMenuRootContext(true);
	const parent = store.useState("parent");
	const floatingRootContext = store.useState("floatingRootContext");
	const floatingTreeRoot = store.useState("floatingTreeRoot");
	const mounted = store.useState("mounted");
	const open = store.useState("open");
	const modal = store.useState("modal");
	const openMethod = store.useState("openMethod");
	const triggerElement = store.useState("activeTriggerElement");
	const transitionStatus = store.useState("transitionStatus");
	const positionerElement = store.useState("positionerElement");
	const instantType = store.useState("instantType");
	const hasViewport = store.useState("hasViewport");
	const lastOpenChangeReason = store.useState("lastOpenChangeReason");
	const floatingNodeId = store.useState("floatingNodeId");
	const floatingParentNodeId = store.useState("floatingParentNodeId");
	const domReference = floatingRootContext.useState("domReferenceElement");
	const previousTriggerRef = import_react.useRef(null);
	const runOnceAnimationsFinish = useAnimationsFinished(positionerElement, false, false);
	let anchor = anchorProp;
	let sideOffset = sideOffsetProp;
	let alignOffset = alignOffsetProp;
	let align = alignProp;
	let collisionAvoidance = collisionAvoidanceProp;
	if (parent.type === "context-menu") {
		anchor = anchorProp ?? parent.context?.anchor;
		align = align ?? "start";
		if (!side && align !== "center") {
			alignOffset = componentProps.alignOffset ?? 2;
			sideOffset = componentProps.sideOffset ?? -5;
		}
	}
	let computedSide = side;
	let computedAlign = align;
	if (parent.type === "menu") {
		computedSide = computedSide ?? "inline-end";
		computedAlign = computedAlign ?? "start";
		collisionAvoidance = componentProps.collisionAvoidance ?? POPUP_COLLISION_AVOIDANCE;
	} else if (parent.type === "menubar") {
		computedSide = computedSide ?? (parent.context.orientation === "vertical" ? "inline-end" : "bottom");
		computedAlign = computedAlign ?? "start";
	}
	const contextMenu = parent.type === "context-menu";
	const positioner = useAnchorPositioning({
		anchor,
		floatingRootContext,
		positionMethod: contextMenuContext ? "fixed" : positionMethodProp,
		mounted,
		side: computedSide,
		sideOffset,
		align: computedAlign,
		alignOffset,
		arrowPadding: contextMenu ? 0 : arrowPadding,
		collisionBoundary,
		collisionPadding,
		sticky,
		nodeId: floatingNodeId,
		keepMounted,
		disableAnchorTracking,
		collisionAvoidance,
		shiftCrossAxis: contextMenu && !("side" in collisionAvoidance && collisionAvoidance.side === "flip"),
		externalTree: floatingTreeRoot,
		adaptiveOrigin: hasViewport ? adaptiveOrigin : void 0
	});
	import_react.useEffect(() => {
		function onMenuOpenChange(details) {
			if (details.open) {
				if (details.parentNodeId === floatingNodeId) store.set("hoverEnabled", false);
				if (details.nodeId !== floatingNodeId && details.parentNodeId === store.select("floatingParentNodeId")) store.setOpen(false, createChangeEventDetails(siblingOpen));
			}
		}
		floatingTreeRoot.events.on("menuopenchange", onMenuOpenChange);
		return () => {
			floatingTreeRoot.events.off("menuopenchange", onMenuOpenChange);
		};
	}, [
		store,
		floatingTreeRoot.events,
		floatingNodeId
	]);
	import_react.useEffect(() => {
		if (store.select("floatingParentNodeId") == null) return;
		function onParentClose(details) {
			if (details.open || details.nodeId !== store.select("floatingParentNodeId")) return;
			const reason = details.reason ?? "sibling-open";
			store.setOpen(false, createChangeEventDetails(reason));
		}
		floatingTreeRoot.events.on("menuopenchange", onParentClose);
		return () => {
			floatingTreeRoot.events.off("menuopenchange", onParentClose);
		};
	}, [floatingTreeRoot.events, store]);
	const closeTimeout = useTimeout();
	import_react.useEffect(() => {
		if (!open) closeTimeout.clear();
	}, [open, closeTimeout]);
	import_react.useEffect(() => {
		function onItemHover(event) {
			if (!open || event.nodeId !== store.select("floatingParentNodeId")) return;
			if (event.target && triggerElement && triggerElement !== event.target) {
				const delay = store.select("closeDelay");
				if (delay > 0) {
					if (!closeTimeout.isStarted()) closeTimeout.start(delay, () => {
						store.setOpen(false, createChangeEventDetails(siblingOpen));
					});
				} else store.setOpen(false, createChangeEventDetails(siblingOpen));
			} else closeTimeout.clear();
		}
		floatingTreeRoot.events.on("itemhover", onItemHover);
		return () => {
			floatingTreeRoot.events.off("itemhover", onItemHover);
		};
	}, [
		floatingTreeRoot.events,
		open,
		triggerElement,
		store,
		closeTimeout
	]);
	import_react.useEffect(() => {
		const eventDetails = {
			open,
			nodeId: floatingNodeId,
			parentNodeId: floatingParentNodeId,
			reason: store.select("lastOpenChangeReason")
		};
		floatingTreeRoot.events.emit("menuopenchange", eventDetails);
	}, [
		floatingTreeRoot.events,
		open,
		store,
		floatingNodeId,
		floatingParentNodeId
	]);
	useIsoLayoutEffect(() => {
		const currentTrigger = domReference;
		const previousTrigger = previousTriggerRef.current;
		if (currentTrigger) previousTriggerRef.current = currentTrigger;
		if (previousTrigger && currentTrigger && currentTrigger !== previousTrigger) {
			store.set("instantType", void 0);
			const abortController = new AbortController();
			runOnceAnimationsFinish(() => {
				store.set("instantType", "trigger-change");
			}, abortController.signal);
			return () => {
				abortController.abort();
			};
		}
	}, [
		domReference,
		runOnceAnimationsFinish,
		store
	]);
	const state = {
		open,
		side: positioner.side,
		align: positioner.align,
		anchorHidden: positioner.anchorHidden,
		nested: parent.type === "menu",
		instant: instantType
	};
	const menubarModal = parent.type === "menubar" && parent.context.modal;
	useAnchoredPopupScrollLock(open && (menubarModal || modal && lastOpenChangeReason !== "trigger-hover"), openMethod === "touch", positionerElement, triggerElement);
	const element = usePositioner(componentProps, state, {
		styles: positioner.positionerStyles,
		transitionStatus,
		props: elementProps,
		refs: [forwardedRef, store.useStateSetter("positionerElement")],
		hidden: !mounted,
		inert: !open
	});
	const shouldRenderBackdrop = mounted && parent.type !== "menu" && (parent.type !== "menubar" && modal && lastOpenChangeReason !== "trigger-hover" || parent.type === "menubar" && parent.context.modal);
	let backdropCutout = null;
	if (parent.type === "menubar") backdropCutout = parent.context.contentElement;
	else if (parent.type === void 0) backdropCutout = triggerElement;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(MenuPositionerContext.Provider, {
		value: positioner,
		children: [shouldRenderBackdrop && /*#__PURE__*/ (0, import_jsx_runtime.jsx)(InternalBackdrop, {
			ref: parent.type === "context-menu" || parent.type === "nested-context-menu" ? parent.context.internalBackdropRef : null,
			inert: inertValue(!open),
			cutout: backdropCutout
		}), /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingNode, {
			id: floatingNodeId,
			children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(CompositeList, {
				elementsRef: store.context.itemDomElements,
				labelsRef: store.context.itemLabels,
				children: element
			})
		})]
	});
});
MenuPositioner.displayName = "MenuPositioner";
//#endregion
//#region node_modules/@base-ui/react/menu/radio-group/MenuRadioGroupContext.mjs
var MenuRadioGroupContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuRadioGroupContext.displayName = "MenuRadioGroupContext";
function useMenuRadioGroupContext() {
	const context = import_react.useContext(MenuRadioGroupContext);
	if (context === void 0) throw new Error("Base UI: MenuRadioGroupContext is missing. MenuRadioGroup parts must be placed within <Menu.RadioGroup>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/radio-group/MenuRadioGroup.mjs
/**
* Groups related radio items.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuRadioGroup = /*#__PURE__*/ import_react.memo(/*#__PURE__*/ import_react.forwardRef(function MenuRadioGroup(componentProps, forwardedRef) {
	const { render, className, value: valueProp, defaultValue, onValueChange: onValueChangeProp, disabled = false, style, "aria-labelledby": ariaLabelledByProp, ...elementProps } = componentProps;
	const [labelId, setLabelId] = import_react.useState(void 0);
	const [value, setValueUnwrapped] = useControlled({
		controlled: valueProp,
		default: defaultValue,
		name: "MenuRadioGroup"
	});
	const setValue = useStableCallback((newValue, eventDetails) => {
		onValueChangeProp?.(newValue, eventDetails);
		if (eventDetails.isCanceled) return;
		setValueUnwrapped(newValue);
	});
	const element = useRenderElement("div", componentProps, {
		state: { disabled },
		ref: forwardedRef,
		props: {
			role: "group",
			"aria-labelledby": ariaLabelledByProp ?? labelId,
			"aria-disabled": disabled || void 0,
			...elementProps
		}
	});
	const context = import_react.useMemo(() => ({
		value,
		setValue,
		disabled
	}), [
		value,
		setValue,
		disabled
	]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuGroupContext.Provider, {
		value: setLabelId,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuRadioGroupContext.Provider, {
			value: context,
			children: element
		})
	});
}));
MenuRadioGroup.displayName = "MenuRadioGroup";
//#endregion
//#region node_modules/@base-ui/react/menu/radio-item/MenuRadioItemContext.mjs
var MenuRadioItemContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuRadioItemContext.displayName = "MenuRadioItemContext";
function useMenuRadioItemContext() {
	const context = import_react.useContext(MenuRadioItemContext);
	if (context === void 0) throw new Error("Base UI: MenuRadioItemContext is missing. MenuRadioItem parts must be placed within <Menu.RadioItem>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/radio-item/MenuRadioItem.mjs
/**
* A menu item that works like a radio button in a given group.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuRadioItem = /*#__PURE__*/ import_react.forwardRef(function MenuRadioItem(componentProps, forwardedRef) {
	const { render, className, id: idProp, label, nativeButton = false, disabled: disabledProp = false, closeOnClick = false, value, style, ...elementProps } = componentProps;
	const listItem = useCompositeListItem({ label });
	const menuPositionerContext = useMenuPositionerContext(true);
	const id = useBaseUiId(idProp);
	const { store } = useMenuRootContext();
	const highlighted = store.useState("isActive", listItem.index);
	const itemProps = store.useState("itemProps");
	const { value: selectedValue, setValue: setSelectedValue, disabled: groupDisabled } = useMenuRadioGroupContext();
	const disabled = groupDisabled || disabledProp;
	const checked = selectedValue === value;
	const { getItemProps, itemRef } = useMenuItem({
		closeOnClick,
		disabled,
		highlighted,
		id,
		store,
		nativeButton,
		nodeId: menuPositionerContext?.context.nodeId,
		itemMetadata: REGULAR_ITEM
	});
	const state = import_react.useMemo(() => ({
		disabled,
		highlighted,
		checked
	}), [
		disabled,
		highlighted,
		checked
	]);
	function handleClick(event) {
		const details = createChangeEventDetails(itemPress, event.nativeEvent, void 0, { preventUnmountOnClose() {} });
		setSelectedValue(value, details);
	}
	const element = useRenderElement("div", componentProps, {
		state,
		stateAttributesMapping: itemMapping,
		props: [
			itemProps,
			{
				role: "menuitemradio",
				"aria-checked": checked,
				onClick: handleClick
			},
			elementProps,
			getItemProps
		],
		ref: [
			itemRef,
			forwardedRef,
			listItem.ref
		]
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuRadioItemContext.Provider, {
		value: state,
		children: element
	});
});
MenuRadioItem.displayName = "MenuRadioItem";
//#endregion
//#region node_modules/@base-ui/react/menu/radio-item-indicator/MenuRadioItemIndicator.mjs
/**
* Indicates whether the radio item is selected.
* Renders a `<span>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuRadioItemIndicator = /*#__PURE__*/ import_react.forwardRef(function MenuRadioItemIndicator(componentProps, forwardedRef) {
	const { render, className, style, keepMounted = false, ...elementProps } = componentProps;
	const item = useMenuRadioItemContext();
	const indicatorRef = import_react.useRef(null);
	const { transitionStatus, setMounted } = useTransitionStatus(item.checked);
	useOpenChangeComplete({
		open: item.checked,
		ref: indicatorRef,
		onComplete() {
			if (!item.checked) setMounted(false);
		}
	});
	return useRenderElement("span", componentProps, {
		state: {
			checked: item.checked,
			disabled: item.disabled,
			highlighted: item.highlighted,
			transitionStatus
		},
		stateAttributesMapping: itemMapping,
		ref: [forwardedRef, indicatorRef],
		props: {
			"aria-hidden": true,
			...elementProps
		},
		enabled: keepMounted || item.checked
	});
});
MenuRadioItemIndicator.displayName = "MenuRadioItemIndicator";
//#endregion
//#region node_modules/@base-ui/react/menubar/MenubarContext.mjs
var MenubarContext = /*#__PURE__*/ import_react.createContext(null);
MenubarContext.displayName = "MenubarContext";
function useMenubarContext(optional) {
	const context = import_react.useContext(MenubarContext);
	if (context === null && !optional) throw new Error("Base UI: MenubarContext is missing. Menubar parts must be placed within <Menubar>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/menu/store/MenuStore.mjs
var selectors = {
	...popupStoreSelectors,
	disabled: createSelector((state) => state.parent.type === "menubar" ? state.parent.context.disabled || state.disabled : state.disabled),
	modal: createSelector((state) => (state.parent.type === void 0 || state.parent.type === "context-menu") && (state.modal ?? true)),
	openMethod: createSelector((state) => state.openMethod),
	allowMouseEnter: createSelector((state) => state.allowMouseEnter),
	highlightItemOnHover: createSelector((state) => state.highlightItemOnHover),
	stickIfOpen: createSelector((state) => state.stickIfOpen),
	parent: createSelector((state) => state.parent),
	rootId: createSelector((state) => {
		if (state.parent.type === "menu") return state.parent.store.select("rootId");
		return state.parent.type !== void 0 ? state.parent.context.rootId : state.rootId;
	}),
	activeIndex: createSelector((state) => state.activeIndex),
	isActive: createSelector((state, itemIndex) => state.activeIndex === itemIndex),
	hoverEnabled: createSelector((state) => state.hoverEnabled),
	instantType: createSelector((state) => state.instantType),
	lastOpenChangeReason: createSelector((state) => state.openChangeReason),
	floatingTreeRoot: createSelector((state) => {
		if (state.parent.type === "menu") return state.parent.store.select("floatingTreeRoot");
		return state.floatingTreeRoot;
	}),
	floatingNodeId: createSelector((state) => state.floatingNodeId),
	floatingParentNodeId: createSelector((state) => state.floatingParentNodeId),
	itemProps: createSelector((state) => state.itemProps),
	closeDelay: createSelector((state) => state.closeDelay),
	hasViewport: createSelector((state) => state.hasViewport),
	keyboardEventRelay: createSelector((state) => {
		if (state.keyboardEventRelay) return state.keyboardEventRelay;
		if (state.parent.type === "menu") return state.parent.store.select("keyboardEventRelay");
	})
};
var MenuStore = class MenuStore extends ReactStore {
	constructor(initialState) {
		super({
			...createInitialState(),
			...initialState
		}, {
			positionerRef: /*#__PURE__*/ import_react.createRef(),
			popupRef: /*#__PURE__*/ import_react.createRef(),
			typingRef: { current: false },
			itemDomElements: { current: [] },
			itemLabels: { current: [] },
			allowMouseUpTriggerRef: { current: false },
			triggerFocusTargetRef: /*#__PURE__*/ import_react.createRef(),
			beforeContentFocusGuardRef: /*#__PURE__*/ import_react.createRef(),
			onOpenChangeComplete: void 0,
			triggerElements: new PopupTriggerMap()
		}, selectors);
		this.unsubscribeParentListener = this.observe("parent", (parent) => {
			this.unsubscribeParentListener?.();
			if (parent.type === "menu") {
				let rootId = parent.store.select("rootId");
				let floatingTreeRoot = parent.store.select("floatingTreeRoot");
				let keyboardEventRelay = parent.store.select("keyboardEventRelay");
				this.unsubscribeParentListener = parent.store.subscribe(() => {
					const nextRootId = parent.store.select("rootId");
					const nextFloatingTreeRoot = parent.store.select("floatingTreeRoot");
					const nextKeyboardEventRelay = parent.store.select("keyboardEventRelay");
					if (rootId === nextRootId && floatingTreeRoot === nextFloatingTreeRoot && keyboardEventRelay === nextKeyboardEventRelay) return;
					rootId = nextRootId;
					floatingTreeRoot = nextFloatingTreeRoot;
					keyboardEventRelay = nextKeyboardEventRelay;
					this.notifyAll();
				});
				this.context.allowMouseUpTriggerRef = parent.store.context.allowMouseUpTriggerRef;
				return;
			}
			if (parent.type !== void 0) this.context.allowMouseUpTriggerRef = parent.context.allowMouseUpTriggerRef;
			this.unsubscribeParentListener = null;
		});
	}
	setOpen(open, eventDetails) {
		this.state.floatingRootContext.context.events.emit("setOpen", {
			open,
			eventDetails
		});
	}
	static useStore(externalStore, initialState) {
		const internalStore = useRefWithInit(() => {
			return new MenuStore(initialState);
		}).current;
		return externalStore ?? internalStore;
	}
	unsubscribeParentListener = null;
};
function createInitialState() {
	return {
		...createInitialPopupStoreState(),
		disabled: false,
		modal: true,
		openMethod: null,
		allowMouseEnter: false,
		highlightItemOnHover: true,
		stickIfOpen: true,
		parent: { type: void 0 },
		rootId: void 0,
		activeIndex: null,
		hoverEnabled: true,
		instantType: void 0,
		openChangeReason: null,
		floatingTreeRoot: new FloatingTreeStore(),
		floatingNodeId: void 0,
		floatingParentNodeId: null,
		itemProps: EMPTY_OBJECT,
		keyboardEventRelay: void 0,
		closeDelay: 0,
		hasViewport: false
	};
}
//#endregion
//#region node_modules/@base-ui/react/menu/submenu-root/MenuSubmenuRootContext.mjs
var MenuSubmenuRootContext = /*#__PURE__*/ import_react.createContext(void 0);
MenuSubmenuRootContext.displayName = "MenuSubmenuRootContext";
function useMenuSubmenuRootContext() {
	return import_react.useContext(MenuSubmenuRootContext);
}
//#endregion
//#region node_modules/@base-ui/react/menu/root/MenuRoot.mjs
/**
* Groups all parts of the menu.
* Doesn't render its own HTML element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuRoot = fastComponent(function MenuRoot(props) {
	const { children, open: openProp, onOpenChange, onOpenChangeComplete, defaultOpen = false, disabled: disabledProp = false, modal: modalProp, loopFocus = true, orientation = "vertical", actionsRef, closeParentOnEsc = false, handle, triggerId: triggerIdProp, defaultTriggerId: defaultTriggerIdProp = null, highlightItemOnHover = true } = props;
	const contextMenuContext = useContextMenuRootContext(true);
	const parentMenuRootContext = useMenuRootContext(true);
	const menubarContext = useMenubarContext(true);
	const isSubmenu = useMenuSubmenuRootContext();
	const parentFromContext = import_react.useMemo(() => {
		if (isSubmenu && parentMenuRootContext) return {
			type: "menu",
			store: parentMenuRootContext.store
		};
		if (menubarContext) return {
			type: "menubar",
			context: menubarContext
		};
		if (contextMenuContext && !parentMenuRootContext) return {
			type: "context-menu",
			context: contextMenuContext
		};
		return { type: void 0 };
	}, [
		contextMenuContext,
		parentMenuRootContext,
		menubarContext,
		isSubmenu
	]);
	const store = MenuStore.useStore(handle?.store, {
		open: defaultOpen,
		openProp,
		activeTriggerId: defaultTriggerIdProp,
		triggerIdProp,
		parent: parentFromContext
	});
	useInitialOpenSync(store, openProp, defaultOpen, defaultTriggerIdProp);
	store.useControlledProp("openProp", openProp);
	store.useControlledProp("triggerIdProp", triggerIdProp);
	store.useContextCallback("onOpenChangeComplete", onOpenChangeComplete);
	const rootId = useId();
	const floatingId = useId();
	const floatingTreeRoot = store.useState("floatingTreeRoot");
	const floatingNodeIdFromContext = useFloatingNodeId(floatingTreeRoot);
	const floatingParentNodeIdFromContext = useFloatingParentNodeId();
	const open = store.useState("open");
	const activeTriggerElement = store.useState("activeTriggerElement");
	const positionerElement = store.useState("positionerElement");
	const hoverEnabled = store.useState("hoverEnabled");
	const disabled = store.useState("disabled");
	const lastOpenChangeReason = store.useState("lastOpenChangeReason");
	const parent = store.useState("parent");
	const activeIndex = store.useState("activeIndex");
	const payload = store.useState("payload");
	const floatingParentNodeId = store.useState("floatingParentNodeId");
	const openEventRef = import_react.useRef(null);
	const allowOutsidePressDismissalRef = import_react.useRef(parent.type !== "context-menu");
	const allowOutsidePressDismissalTimeout = useTimeout();
	const allowTouchToCloseRef = import_react.useRef(true);
	const allowTouchToCloseTimeout = useTimeout();
	const nested = floatingParentNodeId != null;
	if (parent.type !== void 0 && modalProp !== void 0) console.warn("Base UI: The `modal` prop is not supported on nested menus. It will be ignored.");
	const { openMethod, triggerProps: interactionTypeProps } = useOpenInteractionType(open);
	store.useSyncedValues({
		disabled: disabledProp,
		highlightItemOnHover,
		modal: parent.type === void 0 ? modalProp : void 0,
		openMethod,
		rootId
	});
	useImplicitActiveTrigger(store);
	const { forceUnmount } = useOpenStateTransitions(open, store, () => {
		store.update({
			allowMouseEnter: false,
			stickIfOpen: true
		});
	});
	useIsoLayoutEffect(() => {
		if (contextMenuContext && !parentMenuRootContext) store.update({
			parent: {
				type: "context-menu",
				context: contextMenuContext
			},
			floatingNodeId: floatingNodeIdFromContext,
			floatingParentNodeId: floatingParentNodeIdFromContext
		});
		else if (parentMenuRootContext) store.update({
			floatingNodeId: floatingNodeIdFromContext,
			floatingParentNodeId: floatingParentNodeIdFromContext
		});
	}, [
		contextMenuContext,
		parentMenuRootContext,
		floatingNodeIdFromContext,
		floatingParentNodeIdFromContext,
		store
	]);
	import_react.useEffect(() => {
		if (!open) openEventRef.current = null;
		if (parent.type !== "context-menu") return;
		if (!open) {
			allowOutsidePressDismissalTimeout.clear();
			allowOutsidePressDismissalRef.current = false;
			return;
		}
		allowOutsidePressDismissalTimeout.start(500, () => {
			allowOutsidePressDismissalRef.current = true;
		});
	}, [
		allowOutsidePressDismissalTimeout,
		open,
		parent.type
	]);
	useIsoLayoutEffect(() => {
		if (!open && !hoverEnabled) store.set("hoverEnabled", true);
	}, [
		open,
		hoverEnabled,
		store
	]);
	const setOpen = useStableCallback((nextOpen, eventDetails) => {
		const reason = eventDetails.reason;
		if (open === nextOpen && eventDetails.trigger === activeTriggerElement && lastOpenChangeReason === reason) return;
		const shouldPreventUnmountOnClose = attachPreventUnmountOnClose(eventDetails);
		if (!nextOpen && eventDetails.trigger == null) eventDetails.trigger = activeTriggerElement ?? void 0;
		onOpenChange?.(nextOpen, eventDetails);
		if (eventDetails.isCanceled) return;
		store.state.floatingRootContext.dispatchOpenChange(nextOpen, eventDetails);
		const nativeEvent = eventDetails.event;
		if (nextOpen === false && nativeEvent?.type === "click" && nativeEvent.pointerType === "touch" && !allowTouchToCloseRef.current) return;
		if (nextOpen && reason === "trigger-focus") {
			allowTouchToCloseRef.current = false;
			allowTouchToCloseTimeout.start(300, () => {
				allowTouchToCloseRef.current = true;
			});
		} else {
			allowTouchToCloseRef.current = true;
			allowTouchToCloseTimeout.clear();
		}
		const isKeyboardClick = (reason === "trigger-press" || reason === "item-press") && nativeEvent.detail === 0 && nativeEvent?.isTrusted;
		const isDismissClose = !nextOpen && (reason === "escape-key" || reason == null);
		const updatedState = {
			open: nextOpen,
			openChangeReason: reason
		};
		openEventRef.current = eventDetails.event ?? null;
		setPopupOpenState(updatedState, nextOpen, eventDetails.trigger, shouldPreventUnmountOnClose());
		store.update(updatedState);
		if (parent.type === "menubar" && (reason === "trigger-focus" || reason === "focus-out" || reason === "trigger-hover" || reason === "list-navigation" || reason === "sibling-open")) store.set("instantType", "group");
		else if (isKeyboardClick || isDismissClose) store.set("instantType", isKeyboardClick ? "click" : "dismiss");
		else store.set("instantType", void 0);
	});
	const floatingRootContext = useSyncedFloatingRootContext({
		popupStore: store,
		floatingId,
		nested: floatingParentNodeIdFromContext != null,
		onOpenChange: setOpen
	});
	const floatingEvents = floatingRootContext.context.events;
	import_react.useEffect(() => {
		const handleSetOpenEvent = ({ open: nextOpen, eventDetails }) => setOpen(nextOpen, eventDetails);
		floatingEvents.on("setOpen", handleSetOpenEvent);
		return () => {
			floatingEvents?.off("setOpen", handleSetOpenEvent);
		};
	}, [floatingEvents, setOpen]);
	const handleImperativeClose = import_react.useCallback(() => {
		store.setOpen(false, createChangeEventDetails(imperativeAction));
	}, [store]);
	import_react.useImperativeHandle(actionsRef, () => ({
		unmount: forceUnmount,
		close: handleImperativeClose
	}), [forceUnmount, handleImperativeClose]);
	let ctx;
	if (parent.type === "context-menu") ctx = parent.context;
	import_react.useImperativeHandle(ctx?.positionerRef, () => positionerElement, [positionerElement]);
	import_react.useImperativeHandle(ctx?.actionsRef, () => ({ setOpen }), [setOpen]);
	const dismiss = useDismiss(floatingRootContext, {
		enabled: !disabled,
		bubbles: { escapeKey: closeParentOnEsc && parent.type === "menu" },
		outsidePress() {
			if (parent.type !== "context-menu" || openEventRef.current?.type === "contextmenu") return true;
			return allowOutsidePressDismissalRef.current;
		},
		externalTree: nested ? floatingTreeRoot : void 0
	});
	const direction = useDirection();
	const setActiveIndex = import_react.useCallback((index) => {
		if (store.select("activeIndex") === index) return;
		store.set("activeIndex", index);
	}, [store]);
	const listNavigation$1 = useListNavigation(floatingRootContext, {
		enabled: !disabled,
		listRef: store.context.itemDomElements,
		activeIndex,
		nested: parent.type !== void 0,
		loopFocus,
		orientation,
		parentOrientation: parent.type === "menubar" ? parent.context.orientation : void 0,
		rtl: direction === "rtl",
		disabledIndices: EMPTY_ARRAY,
		onNavigate: setActiveIndex,
		openOnArrowKeyDown: parent.type !== "context-menu",
		externalTree: nested ? floatingTreeRoot : void 0,
		focusItemOnHover: highlightItemOnHover
	});
	const onTyping = import_react.useCallback((nextTyping) => {
		store.context.typingRef.current = nextTyping;
	}, [store]);
	const typeahead = useTypeahead(floatingRootContext, {
		enabled: !disabled,
		listRef: store.context.itemLabels,
		elementsRef: store.context.itemDomElements,
		activeIndex,
		resetMs: 500,
		onMatch: (index) => {
			if (open && index !== activeIndex) store.set("activeIndex", index);
		},
		onTyping
	});
	usePopupInteractionProps(store, {
		floatingRootContext,
		activeTriggerProps: import_react.useMemo(() => {
			const mergedProps = mergeProps(typeahead.reference, listNavigation$1.reference, dismiss.reference, { onMouseMove() {
				store.set("allowMouseEnter", true);
			} }, interactionTypeProps);
			mergedProps["aria-haspopup"] = "menu";
			mergedProps["aria-expanded"] = open;
			return mergedProps;
		}, [
			store,
			typeahead.reference,
			listNavigation$1.reference,
			dismiss.reference,
			interactionTypeProps,
			open
		]),
		inactiveTriggerProps: import_react.useMemo(() => {
			const mergedProps = mergeProps(listNavigation$1.trigger, dismiss.trigger, interactionTypeProps);
			mergedProps["aria-haspopup"] = "menu";
			mergedProps["aria-expanded"] = false;
			return mergedProps;
		}, [
			listNavigation$1.trigger,
			dismiss.trigger,
			interactionTypeProps
		]),
		popupProps: import_react.useMemo(() => mergeProps(FOCUSABLE_POPUP_PROPS, {
			id: floatingId,
			role: "menu",
			"aria-labelledby": activeTriggerElement?.id,
			onMouseMove() {
				store.set("allowMouseEnter", true);
				if (parent.type === "menu") store.set("hoverEnabled", false);
			},
			onClick() {
				if (store.select("hoverEnabled")) store.set("hoverEnabled", false);
			},
			onKeyDown(event) {
				const relay = store.select("keyboardEventRelay");
				if (relay && !event.isPropagationStopped()) relay(event);
			}
		}, typeahead.floating, listNavigation$1.floating, dismiss.floating), [
			activeTriggerElement,
			floatingId,
			parent.type,
			store,
			typeahead.floating,
			listNavigation$1.floating,
			dismiss.floating
		]),
		itemProps: listNavigation$1.item ?? EMPTY_OBJECT
	});
	const context = import_react.useMemo(() => ({
		store,
		parent: parentFromContext
	}), [store, parentFromContext]);
	const content = /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuRootContext.Provider, {
		value: context,
		children: typeof children === "function" ? children({ payload }) : children
	});
	if (parent.type === void 0 || parent.type === "context-menu") return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingTree, {
		externalTree: floatingTreeRoot,
		children: content
	});
	return content;
});
MenuRoot.displayName = "MenuRoot";
//#endregion
//#region node_modules/@base-ui/react/menu/submenu-root/MenuSubmenuRoot.mjs
/**
* Groups all parts of a submenu.
* Doesn't render its own HTML element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
function MenuSubmenuRoot(props) {
	const parentMenu = useMenuRootContext().store;
	const contextValue = import_react.useMemo(() => ({ parentMenu }), [parentMenu]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuSubmenuRootContext.Provider, {
		value: contextValue,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(MenuRoot, { ...props })
	});
}
//#endregion
//#region node_modules/@base-ui/react/internals/composite/item/CompositeItem.mjs
/**
* @internal
*/
function CompositeItem(componentProps) {
	const { render, className, style, state = EMPTY_OBJECT, props = EMPTY_ARRAY, refs = EMPTY_ARRAY, metadata, stateAttributesMapping, tag = "div", ...elementProps } = componentProps;
	const { compositeProps, compositeRef } = useCompositeItem({ metadata });
	return useRenderElement(tag, componentProps, {
		state,
		ref: [...refs, compositeRef],
		props: [
			compositeProps,
			...props,
			elementProps
		],
		stateAttributesMapping
	});
}
//#endregion
//#region node_modules/@base-ui/react/menu/utils/findRootOwnerId.mjs
function findRootOwnerId(node) {
	if (isHTMLElement(node) && node.hasAttribute("data-rootownerid")) return node.getAttribute("data-rootownerid") ?? void 0;
	if (isLastTraversableNode(node)) return;
	return findRootOwnerId(getParentNode(node));
}
//#endregion
//#region node_modules/@base-ui/react/utils/useMixedToggleClickHandler.mjs
/**
* Returns `click` and `mousedown` handlers that fix the behavior of triggers of popups that are toggled by different events.
* For example, a button that opens a popup on mousedown and closes it on click.
* This hook prevents the popup from closing immediately after the mouse button is released.
*/
function useMixedToggleClickHandler(params) {
	const { enabled = true, mouseDownAction, open } = params;
	const ignoreClickRef = import_react.useRef(false);
	return import_react.useMemo(() => {
		if (!enabled) return EMPTY_OBJECT;
		return {
			onMouseDown: (event) => {
				if (mouseDownAction === "open" && !open || mouseDownAction === "close" && open) {
					ignoreClickRef.current = true;
					ownerDocument(event.currentTarget).addEventListener("click", () => {
						ignoreClickRef.current = false;
					}, { once: true });
				}
			},
			onClick: (event) => {
				if (ignoreClickRef.current) {
					ignoreClickRef.current = false;
					event.preventBaseUIHandler();
				}
			}
		};
	}, [
		enabled,
		mouseDownAction,
		open
	]);
}
//#endregion
//#region node_modules/@base-ui/react/menu/trigger/MenuTrigger.mjs
var BOUNDARY_OFFSET = 2;
/**
* A button that opens the menu.
* Renders a `<button>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuTrigger = fastComponentRef(function MenuTrigger(componentProps, forwardedRef) {
	const { render, className, style, disabled: disabledProp = false, nativeButton = true, id: idProp, openOnHover: openOnHoverProp, delay = 100, closeDelay = 0, handle, payload, ...elementProps } = componentProps;
	const rootContext = useMenuRootContext(true);
	const store = handle?.store ?? rootContext?.store;
	if (!store) throw new Error("Base UI: <Menu.Trigger> must be either used within a <Menu.Root> component or provided with a handle.");
	const thisTriggerId = useBaseUiId(idProp);
	const isTriggerActive = store.useState("isTriggerActive", thisTriggerId);
	const floatingRootContext = store.useState("floatingRootContext");
	const isOpenedByThisTrigger = store.useState("isOpenedByTrigger", thisTriggerId);
	const popupId = store.useState("triggerPopupId", thisTriggerId);
	const triggerElementRef = import_react.useRef(null);
	const parent = useMenuParent();
	const compositeRootContext = useCompositeRootContext(true);
	const floatingTreeRootFromContext = useFloatingTree();
	const floatingTreeRoot = import_react.useMemo(() => {
		return floatingTreeRootFromContext ?? new FloatingTreeStore();
	}, [floatingTreeRootFromContext]);
	const { registerTrigger, isMountedByThisTrigger } = useTriggerDataForwarding(thisTriggerId, triggerElementRef, store, {
		payload,
		closeDelay,
		parent,
		floatingTreeRoot,
		floatingNodeId: useFloatingNodeId(floatingTreeRoot),
		floatingParentNodeId: useFloatingParentNodeId(),
		keyboardEventRelay: compositeRootContext?.relayKeyboardEvent
	});
	const isInMenubar = parent.type === "menubar";
	const rootDisabled = store.useState("disabled");
	const disabled = disabledProp || rootDisabled || isInMenubar && parent.context.disabled;
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		native: nativeButton
	});
	import_react.useEffect(() => {
		if (!isOpenedByThisTrigger && parent.type === void 0) store.context.allowMouseUpTriggerRef.current = false;
	}, [
		store,
		isOpenedByThisTrigger,
		parent.type
	]);
	const triggerRef = import_react.useRef(null);
	const allowMouseUpTriggerTimeout = useTimeout();
	const handleDocumentMouseUp = useStableCallback((mouseEvent) => {
		if (!triggerRef.current) return;
		allowMouseUpTriggerTimeout.clear();
		store.context.allowMouseUpTriggerRef.current = false;
		const mouseUpTarget = mouseEvent.target;
		if (contains(triggerRef.current, mouseUpTarget) || contains(store.select("positionerElement"), mouseUpTarget) || mouseUpTarget === triggerRef.current) return;
		if (mouseUpTarget != null && findRootOwnerId(mouseUpTarget) === store.select("rootId")) return;
		const bounds = getPseudoElementBounds(triggerRef.current);
		if (mouseEvent.clientX >= bounds.left - BOUNDARY_OFFSET && mouseEvent.clientX <= bounds.right + BOUNDARY_OFFSET && mouseEvent.clientY >= bounds.top - BOUNDARY_OFFSET && mouseEvent.clientY <= bounds.bottom + BOUNDARY_OFFSET) return;
		floatingTreeRoot.events.emit("close", {
			domEvent: mouseEvent,
			reason: cancelOpen
		});
	});
	import_react.useEffect(() => {
		if (isOpenedByThisTrigger && store.select("lastOpenChangeReason") === "trigger-hover") ownerDocument(triggerRef.current).addEventListener("mouseup", handleDocumentMouseUp, { once: true });
	}, [
		isOpenedByThisTrigger,
		handleDocumentMouseUp,
		store
	]);
	const parentMenubarHasSubmenuOpen = isInMenubar && parent.context.hasSubmenuOpen;
	const hoverProps = useHoverReferenceInteraction(floatingRootContext, {
		enabled: (openOnHoverProp ?? parentMenubarHasSubmenuOpen) && !disabled && parent.type !== "context-menu" && (!isInMenubar || parentMenubarHasSubmenuOpen && !isMountedByThisTrigger),
		handleClose: safePolygon({ blockPointerEvents: !isInMenubar }),
		mouseOnly: true,
		move: false,
		restMs: parent.type === void 0 ? delay : void 0,
		delay: { close: closeDelay },
		triggerElementRef,
		externalTree: floatingTreeRoot,
		isActiveTrigger: isTriggerActive,
		isClosing: () => store.select("transitionStatus") === "ending"
	});
	const stickIfOpen = useStickIfOpen(isOpenedByThisTrigger, store.select("lastOpenChangeReason"));
	const click = useClick(floatingRootContext, {
		enabled: !disabled && parent.type !== "context-menu",
		event: isOpenedByThisTrigger && isInMenubar ? "click" : "mousedown",
		toggle: true,
		ignoreMouse: false,
		stickIfOpen: parent.type === void 0 ? stickIfOpen : false
	});
	const focus = useFocus(floatingRootContext, { enabled: !disabled && parentMenubarHasSubmenuOpen });
	const mixedToggleHandlers = useMixedToggleClickHandler({
		open: isOpenedByThisTrigger,
		enabled: isInMenubar,
		mouseDownAction: "open"
	});
	const localInteractionProps = import_react.useMemo(() => mergeProps(focus.reference, click.reference), [focus.reference, click.reference]);
	const rootTriggerProps = store.useState("triggerProps", isMountedByThisTrigger);
	const { preFocusGuardRef, handlePreFocusGuardFocus, handleFocusTargetFocus } = useTriggerFocusGuards(store, triggerElementRef);
	const state = {
		disabled,
		open: isOpenedByThisTrigger
	};
	const ref = [
		triggerRef,
		forwardedRef,
		buttonRef,
		registerTrigger,
		triggerElementRef
	];
	const props = [
		localInteractionProps,
		hoverProps ?? EMPTY_OBJECT,
		rootTriggerProps,
		{
			"aria-haspopup": "menu",
			"aria-controls": popupId,
			id: thisTriggerId,
			onMouseDown: (event) => {
				if (store.select("open")) return;
				allowMouseUpTriggerTimeout.start(200, () => {
					store.context.allowMouseUpTriggerRef.current = true;
				});
				ownerDocument(event.currentTarget).addEventListener("mouseup", handleDocumentMouseUp, { once: true });
			}
		},
		isInMenubar ? { role: "menuitem" } : {},
		mixedToggleHandlers,
		elementProps,
		getButtonProps
	];
	const element = useRenderElement("button", componentProps, {
		enabled: !isInMenubar,
		stateAttributesMapping: pressableTriggerOpenStateMapping,
		state,
		ref,
		props
	});
	if (isInMenubar) return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(CompositeItem, {
		tag: "button",
		render,
		className,
		style,
		state,
		refs: ref,
		props,
		stateAttributesMapping: pressableTriggerOpenStateMapping
	});
	if (isOpenedByThisTrigger) return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(import_react.Fragment, { children: [
		/*#__PURE__*/ (0, import_jsx_runtime.jsx)(FocusGuard, {
			ref: preFocusGuardRef,
			onFocus: handlePreFocusGuardFocus
		}, `${thisTriggerId}-pre-focus-guard`),
		/*#__PURE__*/ (0, import_jsx_runtime.jsx)(import_react.Fragment, { children: element }, thisTriggerId),
		/*#__PURE__*/ (0, import_jsx_runtime.jsx)(FocusGuard, {
			ref: store.context.triggerFocusTargetRef,
			onFocus: handleFocusTargetFocus
		}, `${thisTriggerId}-post-focus-guard`)
	] });
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(import_react.Fragment, { children: element }, thisTriggerId);
});
MenuTrigger.displayName = "MenuTrigger";
/**
* Determines whether to ignore clicks after a hover-open.
*/
function useStickIfOpen(open, openReason) {
	const stickIfOpenTimeout = useTimeout();
	const [stickIfOpen, setStickIfOpen] = import_react.useState(false);
	useIsoLayoutEffect(() => {
		if (open && openReason === "trigger-hover") {
			setStickIfOpen(true);
			stickIfOpenTimeout.start(500, () => {
				setStickIfOpen(false);
			});
		} else if (!open) {
			stickIfOpenTimeout.clear();
			setStickIfOpen(false);
		}
	}, [
		open,
		openReason,
		stickIfOpenTimeout
	]);
	return stickIfOpen;
}
function useMenuParent() {
	const contextMenuContext = useContextMenuRootContext(true);
	const parentContext = useMenuRootContext(true);
	const menubarContext = useMenubarContext(true);
	return import_react.useMemo(() => {
		if (menubarContext) return {
			type: "menubar",
			context: menubarContext
		};
		if (contextMenuContext && !parentContext) return {
			type: "context-menu",
			context: contextMenuContext
		};
		return { type: void 0 };
	}, [
		contextMenuContext,
		parentContext,
		menubarContext
	]);
}
//#endregion
//#region node_modules/@base-ui/react/menu/viewport/MenuViewportCssVars.mjs
var MenuViewportCssVars = /*#__PURE__*/ function(MenuViewportCssVars) {
	/**
	* The width of the parent popup.
	* This variable is placed on the 'previous' container and stores the width of the popup when the previous content was rendered.
	* It can be used to freeze the dimensions of the popup when animating between different content.
	*/
	MenuViewportCssVars["popupWidth"] = "--popup-width";
	/**
	* The height of the parent popup.
	* This variable is placed on the 'previous' container and stores the height of the popup when the previous content was rendered.
	* It can be used to freeze the dimensions of the popup when animating between different content.
	*/
	MenuViewportCssVars["popupHeight"] = "--popup-height";
	return MenuViewportCssVars;
}({});
//#endregion
//#region node_modules/@base-ui/react/menu/viewport/MenuViewport.mjs
var stateAttributesMapping = { activationDirection: (value) => value ? { "data-activation-direction": value } : null };
/**
* A viewport for displaying content transitions.
* This component is only required if one popup can be opened by multiple triggers, its content
* changes based on the trigger, and switching between them is animated.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuViewport = /*#__PURE__*/ import_react.forwardRef(function MenuViewport(componentProps, forwardedRef) {
	const { render, className, style, children, ...elementProps } = componentProps;
	const { store } = useMenuRootContext();
	const { side } = useMenuPositionerContext();
	const instantType = store.useState("instantType");
	const { children: childrenToRender, state: viewportState } = usePopupViewport({
		store,
		side,
		cssVars: MenuViewportCssVars,
		children
	});
	return useRenderElement("div", componentProps, {
		state: {
			activationDirection: viewportState.activationDirection,
			transitioning: viewportState.transitioning,
			instant: instantType
		},
		ref: forwardedRef,
		props: [elementProps, { children: childrenToRender }],
		stateAttributesMapping
	});
});
MenuViewport.displayName = "MenuViewport";
//#endregion
//#region node_modules/@base-ui/react/menu/submenu-trigger/MenuSubmenuTrigger.mjs
/**
* A menu item that opens a submenu.
* Renders a `<div>` element.
*
* Documentation: [Base UI Menu](https://base-ui.com/react/components/menu)
*/
var MenuSubmenuTrigger = /*#__PURE__*/ import_react.forwardRef(function MenuSubmenuTrigger(componentProps, forwardedRef) {
	const { render, className, style, label, id: idProp, nativeButton = false, openOnHover = true, delay = 100, closeDelay = 0, disabled: disabledProp = false, ...elementProps } = componentProps;
	const listItem = useCompositeListItem({ label });
	const menuPositionerContext = useMenuPositionerContext();
	const { store } = useMenuRootContext();
	const thisTriggerId = useBaseUiId(idProp);
	const open = store.useState("open");
	const floatingRootContext = store.useState("floatingRootContext");
	const floatingTreeRoot = store.useState("floatingTreeRoot");
	const popupId = store.useState("triggerPopupId", thisTriggerId);
	const baseRegisterTrigger = useTriggerRegistration(thisTriggerId, store);
	const registerTrigger = import_react.useCallback((element) => {
		const cleanup = baseRegisterTrigger(element);
		if (element !== null && store.select("open") && store.select("activeTriggerId") == null) store.update({
			activeTriggerId: thisTriggerId,
			activeTriggerElement: element,
			closeDelay
		});
		return cleanup;
	}, [
		baseRegisterTrigger,
		closeDelay,
		store,
		thisTriggerId
	]);
	const triggerElementRef = import_react.useRef(null);
	const handleTriggerElementRef = import_react.useCallback((el) => {
		triggerElementRef.current = el;
		store.set("activeTriggerElement", el);
	}, [store]);
	const submenuRootContext = useMenuSubmenuRootContext();
	if (!submenuRootContext?.parentMenu) throw new Error("Base UI: <Menu.SubmenuTrigger> must be placed in <Menu.SubmenuRoot>.");
	store.useSyncedValue("closeDelay", closeDelay);
	const parentMenuStore = submenuRootContext.parentMenu;
	const rootDisabled = store.useState("disabled");
	const parentDisabled = parentMenuStore.useState("disabled");
	const disabled = disabledProp || rootDisabled || parentDisabled;
	useIsoLayoutEffect(() => {
		const element = triggerElementRef.current;
		if (element && isElementDisabled(element) && !disabled) warn(`A disabled element was detected on <Menu.SubmenuTrigger>. To properly disable the trigger, use the \`disabled\` prop on the component instead of setting it on the rendered element.${SafeReact.captureOwnerStack?.() || ""}`);
	});
	const itemProps = parentMenuStore.useState("itemProps");
	const highlighted = parentMenuStore.useState("isActive", listItem.index);
	const itemMetadata = import_react.useMemo(() => ({
		type: "submenu-trigger",
		setActive() {
			if (parentMenuStore.select("highlightItemOnHover")) parentMenuStore.set("activeIndex", listItem.index);
		}
	}), [parentMenuStore, listItem.index]);
	const { getItemProps, itemRef } = useMenuItem({
		closeOnClick: false,
		disabled,
		highlighted,
		id: thisTriggerId,
		store,
		typingRef: parentMenuStore.context.typingRef,
		nativeButton,
		itemMetadata,
		nodeId: menuPositionerContext?.context.nodeId
	});
	const hoverProps = useHoverReferenceInteraction(floatingRootContext, {
		enabled: store.useState("hoverEnabled") && openOnHover && !disabled,
		handleClose: safePolygon({ blockPointerEvents: true }),
		mouseOnly: true,
		move: true,
		restMs: delay,
		delay: {
			open: delay,
			close: closeDelay
		},
		shouldOpen: delay > 0 ? () => parentMenuStore.select("allowMouseEnter") : void 0,
		triggerElementRef,
		externalTree: floatingTreeRoot,
		isClosing: () => store.select("transitionStatus") === "ending"
	});
	const localInteractionProps = useClick(floatingRootContext, {
		enabled: !disabled,
		event: "mousedown",
		toggle: !openOnHover,
		ignoreMouse: openOnHover,
		stickIfOpen: false
	}).reference ?? EMPTY_OBJECT;
	const rootTriggerProps = store.useState("triggerProps", true);
	delete rootTriggerProps.id;
	return useRenderElement("div", componentProps, {
		state: {
			disabled,
			highlighted,
			open
		},
		stateAttributesMapping: triggerOpenStateMapping,
		props: [
			localInteractionProps,
			hoverProps,
			rootTriggerProps,
			itemProps,
			{
				"aria-controls": popupId,
				tabIndex: open || highlighted ? 0 : -1,
				onBlur() {
					if (highlighted) parentMenuStore.set("activeIndex", null);
				}
			},
			elementProps,
			getItemProps
		],
		ref: [
			forwardedRef,
			listItem.ref,
			itemRef,
			registerTrigger,
			handleTriggerElementRef
		]
	});
});
MenuSubmenuTrigger.displayName = "MenuSubmenuTrigger";
//#endregion
//#region node_modules/@base-ui/react/menu/store/MenuHandle.mjs
var MenuHandle = class {
	/**
	* Internal store holding the menu's state.
	* @internal
	*/
	constructor() {
		this.store = new MenuStore();
	}
	/**
	* Opens the menu and associates it with the trigger with the given id.
	* The trigger must be a Menu.Trigger component with this handle passed as a prop.
	*
	* @param triggerId ID of the trigger to associate with the menu.
	*/
	open(triggerId) {
		const triggerElement = triggerId ? this.store.context.triggerElements.getById(triggerId) : void 0;
		if (triggerId && !triggerElement) throw new Error(`Base UI: MenuHandle.open: No trigger found with id "${triggerId}".`);
		this.store.setOpen(true, createChangeEventDetails("imperative-action", void 0, triggerElement));
	}
	/**
	* Closes the menu.
	*/
	close() {
		this.store.setOpen(false, createChangeEventDetails("imperative-action", void 0, void 0));
	}
	/**
	* Indicates whether the menu is currently open.
	*/
	get isOpen() {
		return this.store.select("open");
	}
};
/**
* Creates a new handle to connect a Menu.Root with detached Menu.Trigger components.
*/
function createMenuHandle() {
	return new MenuHandle();
}
//#endregion
//#region node_modules/@base-ui/react/menu/index.parts.mjs
var index_parts_exports = /* @__PURE__ */ __exportAll({
	Arrow: () => MenuArrow,
	Backdrop: () => MenuBackdrop,
	CheckboxItem: () => MenuCheckboxItem,
	CheckboxItemIndicator: () => MenuCheckboxItemIndicator,
	Group: () => MenuGroup,
	GroupLabel: () => MenuGroupLabel,
	Handle: () => MenuHandle,
	Item: () => MenuItem,
	LinkItem: () => MenuLinkItem,
	Popup: () => MenuPopup,
	Portal: () => MenuPortal,
	Positioner: () => MenuPositioner,
	RadioGroup: () => MenuRadioGroup,
	RadioItem: () => MenuRadioItem,
	RadioItemIndicator: () => MenuRadioItemIndicator,
	Root: () => MenuRoot,
	Separator: () => Separator,
	SubmenuRoot: () => MenuSubmenuRoot,
	SubmenuTrigger: () => MenuSubmenuTrigger,
	Trigger: () => MenuTrigger,
	Viewport: () => MenuViewport,
	createHandle: () => createMenuHandle
});
//#endregion
export { index_parts_exports as Menu };
