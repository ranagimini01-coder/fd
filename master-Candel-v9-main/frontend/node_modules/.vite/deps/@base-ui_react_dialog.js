import { n as __exportAll, r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
import { r as EMPTY_OBJECT, t as useRenderElement } from "./useRenderElement-BiX6Dyza.js";
import { t as useButton } from "./useButton-DFSPkxH_.js";
import { n as contains, r as getTarget } from "./shadowDom-BbNDe3Dh.js";
import { r as closePress, s as imperativeAction, t as createChangeEventDetails, y as useBaseUiId } from "./createBaseUIEventDetails-BNfSv2gm.js";
import { t as require_jsx_runtime } from "./react_jsx-runtime.js";
import { a as transitionStatusMapping, n as useOpenChangeComplete } from "./useTransitionStatus-CDr8WmsC.js";
import { D as useDismiss, E as useOnFirstRender, I as FloatingPortal, L as CLICK_TRIGGER_IDENTIFIER, O as useClick, T as createSelector, _t as CommonPopupDataAttributes, a as PopupTriggerMap, b as ReactStore, bt as triggerOpenStateMapping, c as createDefaultInitialFocus, f as useOpenStateTransitions, g as useTriggerDataForwarding, h as usePopupStore, i as InternalBackdrop, k as FloatingFocusManager, l as setPopupOpenState, m as usePopupRootSync, n as useOpenMethodTriggerProps, o as FOCUSABLE_POPUP_PROPS, p as usePopupInteractionProps, r as useScrollLock, u as useImplicitActiveTrigger, vt as popupStateMapping } from "./useOpenInteractionType-fml9RCjU.js";
import { s as COMPOSITE_KEYS, t as inertValue } from "./inertValue-J_gNalGy.js";
import { n as createPopupFloatingRootContext, r as popupStoreSelectors, t as createInitialPopupStoreState } from "./store-DgHEBjVg.js";
//#region node_modules/@base-ui/react/dialog/root/DialogRootContext.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
var IsDrawerContext = /*#__PURE__*/ import_react.createContext(false);
IsDrawerContext.displayName = "IsDrawerContext";
var DialogRootContext = /*#__PURE__*/ import_react.createContext(void 0);
DialogRootContext.displayName = "DialogRootContext";
function useDialogRootContext(optional) {
	const dialogRootContext = import_react.useContext(DialogRootContext);
	if (optional === false && dialogRootContext === void 0) throw new Error("Base UI: DialogRootContext is missing. Dialog parts must be placed within <Dialog.Root>.");
	return dialogRootContext;
}
//#endregion
//#region node_modules/@base-ui/react/dialog/backdrop/DialogBackdrop.mjs
var stateAttributesMapping$2 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* An overlay displayed beneath the popup.
* Renders a `<div>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogBackdrop = /*#__PURE__*/ import_react.forwardRef(function DialogBackdrop(componentProps, forwardedRef) {
	const { render, className, style, forceRender = false, ...elementProps } = componentProps;
	const { store } = useDialogRootContext();
	const open = store.useState("open");
	const nested = store.useState("nested");
	const mounted = store.useState("mounted");
	return useRenderElement("div", componentProps, {
		state: {
			open,
			transitionStatus: store.useState("transitionStatus")
		},
		ref: [store.context.backdropRef, forwardedRef],
		stateAttributesMapping: stateAttributesMapping$2,
		props: [{
			role: "presentation",
			hidden: !mounted,
			style: {
				userSelect: "none",
				WebkitUserSelect: "none"
			}
		}, elementProps],
		enabled: forceRender || !nested
	});
});
DialogBackdrop.displayName = "DialogBackdrop";
//#endregion
//#region node_modules/@base-ui/react/dialog/close/DialogClose.mjs
/**
* A button that closes the dialog.
* Renders a `<button>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogClose = /*#__PURE__*/ import_react.forwardRef(function DialogClose(componentProps, forwardedRef) {
	const { render, className, style, disabled = false, nativeButton = true, ...elementProps } = componentProps;
	const { store } = useDialogRootContext();
	const open = store.useState("open");
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		native: nativeButton
	});
	const state = { disabled };
	function handleClick(event) {
		if (open) store.setOpen(false, createChangeEventDetails(closePress, event.nativeEvent));
	}
	return useRenderElement("button", componentProps, {
		state,
		ref: [forwardedRef, buttonRef],
		props: [
			{ onClick: handleClick },
			elementProps,
			getButtonProps
		]
	});
});
DialogClose.displayName = "DialogClose";
//#endregion
//#region node_modules/@base-ui/react/dialog/description/DialogDescription.mjs
/**
* A paragraph with additional information about the dialog.
* Renders a `<p>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogDescription = /*#__PURE__*/ import_react.forwardRef(function DialogDescription(componentProps, forwardedRef) {
	const { render, className, style, id: idProp, ...elementProps } = componentProps;
	const { store } = useDialogRootContext();
	const id = useBaseUiId(idProp);
	store.useSyncedValueWithCleanup("descriptionElementId", id);
	return useRenderElement("p", componentProps, {
		ref: forwardedRef,
		props: [{ id }, elementProps]
	});
});
DialogDescription.displayName = "DialogDescription";
//#endregion
//#region node_modules/@base-ui/react/dialog/popup/DialogPopupCssVars.mjs
var DialogPopupCssVars = /*#__PURE__*/ function(DialogPopupCssVars) {
	/**
	* Indicates how many dialogs are nested within.
	* @type {number}
	*/
	DialogPopupCssVars["nestedDialogs"] = "--nested-dialogs";
	return DialogPopupCssVars;
}({});
//#endregion
//#region node_modules/@base-ui/react/dialog/popup/DialogPopupDataAttributes.mjs
var DialogPopupDataAttributes = function(DialogPopupDataAttributes) {
	/**
	* Present when the dialog is open.
	*/
	DialogPopupDataAttributes[DialogPopupDataAttributes["open"] = CommonPopupDataAttributes.open] = "open";
	/**
	* Present when the dialog is closed.
	*/
	DialogPopupDataAttributes[DialogPopupDataAttributes["closed"] = CommonPopupDataAttributes.closed] = "closed";
	/**
	* Present when the dialog is animating in.
	*/
	DialogPopupDataAttributes[DialogPopupDataAttributes["startingStyle"] = CommonPopupDataAttributes.startingStyle] = "startingStyle";
	/**
	* Present when the dialog is animating out.
	*/
	DialogPopupDataAttributes[DialogPopupDataAttributes["endingStyle"] = CommonPopupDataAttributes.endingStyle] = "endingStyle";
	/**
	* Present when the dialog is nested within another dialog.
	*/
	DialogPopupDataAttributes["nested"] = "data-nested";
	/**
	* Present when the dialog has other open dialogs nested within it.
	*/
	DialogPopupDataAttributes["nestedDialogOpen"] = "data-nested-dialog-open";
	return DialogPopupDataAttributes;
}({});
//#endregion
//#region node_modules/@base-ui/react/dialog/portal/DialogPortalContext.mjs
var DialogPortalContext = /*#__PURE__*/ import_react.createContext(void 0);
DialogPortalContext.displayName = "DialogPortalContext";
function useDialogPortalContext() {
	const value = import_react.useContext(DialogPortalContext);
	if (value === void 0) throw new Error("Base UI: <Dialog.Portal> is missing.");
	return value;
}
//#endregion
//#region node_modules/@base-ui/react/dialog/popup/DialogPopup.mjs
var import_jsx_runtime = require_jsx_runtime();
var stateAttributesMapping$1 = {
	...popupStateMapping,
	...transitionStatusMapping,
	nestedDialogOpen(value) {
		return value ? { [DialogPopupDataAttributes.nestedDialogOpen]: "" } : null;
	}
};
/**
* A container for the dialog contents.
* Renders a `<div>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogPopup = /*#__PURE__*/ import_react.forwardRef(function DialogPopup(componentProps, forwardedRef) {
	const { render, className, style, finalFocus, initialFocus, ...elementProps } = componentProps;
	const { store } = useDialogRootContext();
	const descriptionElementId = store.useState("descriptionElementId");
	const disablePointerDismissal = store.useState("disablePointerDismissal");
	const floatingRootContext = store.useState("floatingRootContext");
	const rootPopupProps = store.useState("popupProps");
	const modal = store.useState("modal");
	const mounted = store.useState("mounted");
	const nested = store.useState("nested");
	const nestedOpenDialogCount = store.useState("nestedOpenDialogCount");
	const open = store.useState("open");
	const openMethod = store.useState("openMethod");
	const titleElementId = store.useState("titleElementId");
	const transitionStatus = store.useState("transitionStatus");
	const role = store.useState("role");
	const floatingId = floatingRootContext.useState("floatingId");
	const popupId = elementProps.id ?? floatingId;
	useDialogPortalContext();
	useOpenChangeComplete({
		open,
		ref: store.context.popupRef,
		onComplete() {
			if (open) store.context.onOpenChangeComplete?.(true);
		}
	});
	const resolvedInitialFocus = initialFocus === void 0 ? createDefaultInitialFocus(store.context.popupRef) : initialFocus;
	const nestedDialogOpen = nestedOpenDialogCount > 0;
	const setPopupElement = store.useStateSetter("popupElement");
	const element = useRenderElement("div", componentProps, {
		state: {
			open,
			nested,
			transitionStatus,
			nestedDialogOpen
		},
		props: [
			rootPopupProps,
			{
				id: popupId,
				"aria-labelledby": titleElementId ?? void 0,
				"aria-describedby": descriptionElementId ?? void 0,
				role,
				...FOCUSABLE_POPUP_PROPS,
				hidden: !mounted,
				onKeyDown(event) {
					if (COMPOSITE_KEYS.has(event.key)) event.stopPropagation();
				},
				style: { [DialogPopupCssVars.nestedDialogs]: nestedOpenDialogCount }
			},
			elementProps
		],
		ref: [
			forwardedRef,
			store.context.popupRef,
			setPopupElement
		],
		stateAttributesMapping: stateAttributesMapping$1
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingFocusManager, {
		context: floatingRootContext,
		openInteractionType: openMethod,
		disabled: !mounted,
		closeOnFocusOut: !disablePointerDismissal,
		initialFocus: resolvedInitialFocus,
		returnFocus: finalFocus,
		modal: modal !== false,
		restoreFocus: "popup",
		children: element
	});
});
DialogPopup.displayName = "DialogPopup";
//#endregion
//#region node_modules/@base-ui/react/dialog/portal/DialogPortal.mjs
/**
* A portal element that moves the popup to a different part of the DOM.
* By default, the portal element is appended to `<body>`.
* Renders a `<div>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogPortal = /*#__PURE__*/ import_react.forwardRef(function DialogPortal(props, forwardedRef) {
	const { keepMounted = false, ...portalProps } = props;
	const { store } = useDialogRootContext();
	const mounted = store.useState("mounted");
	const modal = store.useState("modal");
	const open = store.useState("open");
	if (!(mounted || keepMounted)) return null;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(DialogPortalContext.Provider, {
		value: keepMounted,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(FloatingPortal, {
			ref: forwardedRef,
			...portalProps,
			children: [mounted && modal === true && /*#__PURE__*/ (0, import_jsx_runtime.jsx)(InternalBackdrop, {
				ref: store.context.internalBackdropRef,
				inert: inertValue(!open)
			}), props.children]
		})
	});
});
DialogPortal.displayName = "DialogPortal";
//#endregion
//#region node_modules/@base-ui/react/dialog/root/useDialogRoot.mjs
function useDialogRoot(params) {
	const { store, actionsRef } = params;
	const open = store.useState("open");
	usePopupRootSync(store, open);
	useImplicitActiveTrigger(store);
	const { forceUnmount } = useOpenStateTransitions(open, store);
	const handleImperativeClose = import_react.useCallback(() => {
		store.setOpen(false, createChangeEventDetails(imperativeAction));
	}, [store]);
	import_react.useImperativeHandle(actionsRef, () => ({
		unmount: forceUnmount,
		close: handleImperativeClose
	}), [forceUnmount, handleImperativeClose]);
}
function DialogInteractions({ store, parentContext, isDrawer }) {
	const open = store.useState("open");
	const disablePointerDismissal = store.useState("disablePointerDismissal");
	const modal = store.useState("modal");
	const popupElement = store.useState("popupElement");
	const floatingRootContext = store.useState("floatingRootContext");
	const [ownNestedOpenDialogs, setOwnNestedOpenDialogs] = import_react.useState(0);
	const [ownNestedOpenDrawers, setOwnNestedOpenDrawers] = import_react.useState(0);
	const isTopmost = ownNestedOpenDialogs === 0;
	const dismiss = useDismiss(floatingRootContext, {
		outsidePressEvent() {
			if (store.context.internalBackdropRef.current || store.context.backdropRef.current) return "intentional";
			return {
				mouse: modal === "trap-focus" ? "sloppy" : "intentional",
				touch: "sloppy"
			};
		},
		outsidePress(event) {
			if (!store.context.outsidePressEnabledRef.current) return false;
			if ("button" in event && event.button !== 0) return false;
			if ("touches" in event && event.touches.length !== 1) return false;
			const target = getTarget(event);
			if (isTopmost && !disablePointerDismissal) {
				if (modal) return store.context.internalBackdropRef.current || store.context.backdropRef.current ? store.context.internalBackdropRef.current === target || store.context.backdropRef.current === target || contains(target, popupElement) && !target?.hasAttribute("data-base-ui-portal") : true;
				return true;
			}
			return false;
		},
		escapeKey: isTopmost
	});
	useScrollLock(open && modal === true, popupElement);
	store.useContextCallback("onNestedDialogOpen", (dialogCount, drawerCount) => {
		setOwnNestedOpenDialogs(dialogCount);
		setOwnNestedOpenDrawers(drawerCount);
	});
	store.useContextCallback("onNestedDialogClose", () => {
		setOwnNestedOpenDialogs(0);
		setOwnNestedOpenDrawers(0);
	});
	import_react.useEffect(() => {
		if (parentContext?.onNestedDialogOpen && open) parentContext.onNestedDialogOpen(ownNestedOpenDialogs + 1, ownNestedOpenDrawers + (isDrawer ? 1 : 0));
		if (parentContext?.onNestedDialogClose && !open) parentContext.onNestedDialogClose();
		return () => {
			if (parentContext?.onNestedDialogClose && open) parentContext.onNestedDialogClose();
		};
	}, [
		isDrawer,
		open,
		ownNestedOpenDialogs,
		ownNestedOpenDrawers,
		parentContext
	]);
	usePopupInteractionProps(store, {
		activeTriggerProps: dismiss.reference ?? EMPTY_OBJECT,
		inactiveTriggerProps: dismiss.trigger ?? EMPTY_OBJECT,
		popupProps: dismiss.floating ?? EMPTY_OBJECT,
		nestedOpenDialogCount: ownNestedOpenDialogs,
		nestedOpenDrawerCount: ownNestedOpenDrawers
	});
	return null;
}
//#endregion
//#region node_modules/@base-ui/react/dialog/store/DialogStore.mjs
var selectors = {
	...popupStoreSelectors,
	modal: createSelector((state) => state.modal),
	nested: createSelector((state) => state.nested),
	nestedOpenDialogCount: createSelector((state) => state.nestedOpenDialogCount),
	nestedOpenDrawerCount: createSelector((state) => state.nestedOpenDrawerCount),
	disablePointerDismissal: createSelector((state) => state.disablePointerDismissal),
	openMethod: createSelector((state) => state.openMethod),
	descriptionElementId: createSelector((state) => state.descriptionElementId),
	titleElementId: createSelector((state) => state.titleElementId),
	viewportElement: createSelector((state) => state.viewportElement),
	role: createSelector((state) => state.role)
};
var DialogStore = class DialogStore extends ReactStore {
	constructor(initialState, floatingId, nested = false) {
		const triggerElements = new PopupTriggerMap();
		const state = createInitialState(initialState);
		state.floatingRootContext = createPopupFloatingRootContext(triggerElements, floatingId, nested);
		super(state, {
			popupRef: /*#__PURE__*/ import_react.createRef(),
			backdropRef: /*#__PURE__*/ import_react.createRef(),
			internalBackdropRef: /*#__PURE__*/ import_react.createRef(),
			outsidePressEnabledRef: { current: true },
			triggerElements,
			onOpenChange: void 0,
			onOpenChangeComplete: void 0
		}, selectors);
	}
	setOpen = (nextOpen, eventDetails) => {
		eventDetails.preventUnmountOnClose = () => {
			this.set("preventUnmountingOnClose", true);
		};
		if (!nextOpen && eventDetails.trigger == null && this.state.activeTriggerId != null) eventDetails.trigger = this.state.activeTriggerElement ?? void 0;
		this.context.onOpenChange?.(nextOpen, eventDetails);
		if (eventDetails.isCanceled) return;
		this.state.floatingRootContext.dispatchOpenChange(nextOpen, eventDetails);
		const updatedState = { open: nextOpen };
		setPopupOpenState(updatedState, nextOpen, eventDetails.trigger);
		this.update(updatedState);
	};
	static useStore(externalStore, initialState) {
		return usePopupStore(externalStore, (floatingId, nested) => new DialogStore(initialState, floatingId, nested), true).store;
	}
};
function createInitialState(initialState = {}) {
	return {
		...createInitialPopupStoreState(),
		modal: true,
		disablePointerDismissal: false,
		popupElement: null,
		viewportElement: null,
		descriptionElementId: void 0,
		titleElementId: void 0,
		openMethod: null,
		nested: false,
		nestedOpenDialogCount: 0,
		nestedOpenDrawerCount: 0,
		role: "dialog",
		...initialState
	};
}
//#endregion
//#region node_modules/@base-ui/react/dialog/root/useRenderDialogRoot.mjs
function useRenderDialogRoot(props, mode = "dialog") {
	const { children, open: openProp, defaultOpen = false, onOpenChange, onOpenChangeComplete, disablePointerDismissal: disablePointerDismissalProp = false, modal: modalProp = true, actionsRef, handle, triggerId: triggerIdProp, defaultTriggerId: defaultTriggerIdProp = null } = props;
	const isDrawer = mode === "drawer";
	const isAlertDialog = mode === "alert-dialog";
	const modal = isAlertDialog ? true : modalProp;
	const disablePointerDismissal = isAlertDialog || disablePointerDismissalProp;
	const role = isAlertDialog ? "alertdialog" : "dialog";
	const parentDialogRootContext = useDialogRootContext(true);
	const rootState = {
		modal,
		disablePointerDismissal,
		nested: Boolean(parentDialogRootContext),
		role
	};
	const store = DialogStore.useStore(handle?.store, {
		open: defaultOpen,
		openProp,
		activeTriggerId: defaultTriggerIdProp,
		triggerIdProp,
		...rootState
	});
	useOnFirstRender(() => {
		const nextState = openProp === void 0 && store.state.open === false && defaultOpen === true ? {
			open: true,
			activeTriggerId: defaultTriggerIdProp
		} : null;
		if (isAlertDialog) store.update(nextState ? {
			...rootState,
			...nextState
		} : rootState);
		else if (nextState) store.update(nextState);
	});
	store.useControlledProp("openProp", openProp);
	store.useControlledProp("triggerIdProp", triggerIdProp);
	store.useSyncedValues(rootState);
	store.useContextCallback("onOpenChange", onOpenChange);
	store.useContextCallback("onOpenChangeComplete", onOpenChangeComplete);
	const open = store.useState("open");
	const mounted = store.useState("mounted");
	const payload = store.useState("payload");
	useDialogRoot({
		store,
		actionsRef
	});
	const shouldRenderInteractions = open || mounted;
	const contextValue = import_react.useMemo(() => ({ store }), [store]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(IsDrawerContext.Provider, {
		value: false,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(DialogRootContext.Provider, {
			value: contextValue,
			children: [shouldRenderInteractions && /*#__PURE__*/ (0, import_jsx_runtime.jsx)(DialogInteractions, {
				store,
				parentContext: parentDialogRootContext?.store.context,
				isDrawer
			}), typeof children === "function" ? children({ payload }) : children]
		})
	});
}
//#endregion
//#region node_modules/@base-ui/react/dialog/root/DialogRoot.mjs
/**
* Groups all parts of the dialog.
* Doesn't render its own HTML element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
function DialogRoot(props) {
	return useRenderDialogRoot(props, import_react.useContext(IsDrawerContext) ? "drawer" : "dialog");
}
//#endregion
//#region node_modules/@base-ui/react/dialog/viewport/DialogViewportDataAttributes.mjs
var DialogViewportDataAttributes = function(DialogViewportDataAttributes) {
	/**
	* Present when the dialog is open.
	*/
	DialogViewportDataAttributes[DialogViewportDataAttributes["open"] = CommonPopupDataAttributes.open] = "open";
	/**
	* Present when the dialog is closed.
	*/
	DialogViewportDataAttributes[DialogViewportDataAttributes["closed"] = CommonPopupDataAttributes.closed] = "closed";
	/**
	* Present when the dialog is animating in.
	*/
	DialogViewportDataAttributes[DialogViewportDataAttributes["startingStyle"] = CommonPopupDataAttributes.startingStyle] = "startingStyle";
	/**
	* Present when the dialog is animating out.
	*/
	DialogViewportDataAttributes[DialogViewportDataAttributes["endingStyle"] = CommonPopupDataAttributes.endingStyle] = "endingStyle";
	/**
	* Present when the dialog is nested within another dialog.
	*/
	DialogViewportDataAttributes["nested"] = "data-nested";
	/**
	* Present when the dialog has other open dialogs nested within it.
	*/
	DialogViewportDataAttributes["nestedDialogOpen"] = "data-nested-dialog-open";
	return DialogViewportDataAttributes;
}({});
//#endregion
//#region node_modules/@base-ui/react/dialog/viewport/DialogViewport.mjs
var stateAttributesMapping = {
	...popupStateMapping,
	...transitionStatusMapping,
	nested(value) {
		return value ? { [DialogViewportDataAttributes.nested]: "" } : null;
	},
	nestedDialogOpen(value) {
		return value ? { [DialogViewportDataAttributes.nestedDialogOpen]: "" } : null;
	}
};
/**
* A positioning container for the dialog popup that can be made scrollable.
* Renders a `<div>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogViewport = /*#__PURE__*/ import_react.forwardRef(function DialogViewport(componentProps, forwardedRef) {
	const { render, className, style, children, ...elementProps } = componentProps;
	const keepMounted = useDialogPortalContext();
	const { store } = useDialogRootContext();
	const open = store.useState("open");
	const nested = store.useState("nested");
	const transitionStatus = store.useState("transitionStatus");
	const nestedOpenDialogCount = store.useState("nestedOpenDialogCount");
	const mounted = store.useState("mounted");
	const setViewportElement = store.useStateSetter("viewportElement");
	return useRenderElement("div", componentProps, {
		enabled: keepMounted || mounted,
		state: {
			open,
			nested,
			transitionStatus,
			nestedDialogOpen: nestedOpenDialogCount > 0
		},
		ref: [forwardedRef, setViewportElement],
		stateAttributesMapping,
		props: [{
			role: "presentation",
			hidden: !mounted,
			style: { pointerEvents: !open ? "none" : void 0 },
			children
		}, elementProps]
	});
});
DialogViewport.displayName = "DialogViewport";
//#endregion
//#region node_modules/@base-ui/react/dialog/title/DialogTitle.mjs
/**
* A heading that labels the dialog.
* Renders an `<h2>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogTitle = /*#__PURE__*/ import_react.forwardRef(function DialogTitle(componentProps, forwardedRef) {
	const { render, className, style, id: idProp, ...elementProps } = componentProps;
	const { store } = useDialogRootContext();
	const id = useBaseUiId(idProp);
	store.useSyncedValueWithCleanup("titleElementId", id);
	return useRenderElement("h2", componentProps, {
		ref: forwardedRef,
		props: [{ id }, elementProps]
	});
});
DialogTitle.displayName = "DialogTitle";
//#endregion
//#region node_modules/@base-ui/react/dialog/trigger/DialogTrigger.mjs
/**
* A button that opens the dialog.
* Renders a `<button>` element.
*
* Documentation: [Base UI Dialog](https://base-ui.com/react/components/dialog)
*/
var DialogTrigger = /*#__PURE__*/ import_react.forwardRef(function DialogTrigger(componentProps, forwardedRef) {
	const { render, className, style, disabled = false, nativeButton = true, id: idProp, payload, handle, ...elementProps } = componentProps;
	const dialogRootContext = useDialogRootContext(true);
	const store = handle?.store ?? dialogRootContext?.store;
	if (!store) throw new Error("Base UI: <Dialog.Trigger> must be used within <Dialog.Root> or provided with a handle.");
	const thisTriggerId = useBaseUiId(idProp);
	const floatingContext = store.useState("floatingRootContext");
	const isOpenedByThisTrigger = store.useState("isOpenedByTrigger", thisTriggerId);
	const popupId = store.useState("triggerPopupId", thisTriggerId);
	const triggerElementRef = import_react.useRef(null);
	const { registerTrigger, isMountedByThisTrigger } = useTriggerDataForwarding(thisTriggerId, triggerElementRef, store, { payload });
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		native: nativeButton
	});
	const click = useClick(floatingContext, { enabled: floatingContext != null });
	const interactionTypeProps = useOpenMethodTriggerProps(() => store.select("open"), (interactionType) => {
		store.set("openMethod", interactionType);
	});
	const state = {
		disabled,
		open: isOpenedByThisTrigger
	};
	const rootTriggerProps = store.useState("triggerProps", isMountedByThisTrigger);
	return useRenderElement("button", componentProps, {
		state,
		ref: [
			buttonRef,
			forwardedRef,
			registerTrigger,
			triggerElementRef
		],
		props: [
			click.reference,
			rootTriggerProps,
			interactionTypeProps,
			{
				[CLICK_TRIGGER_IDENTIFIER]: "",
				id: thisTriggerId,
				"aria-haspopup": "dialog",
				"aria-expanded": isOpenedByThisTrigger,
				"aria-controls": popupId
			},
			elementProps,
			getButtonProps
		],
		stateAttributesMapping: triggerOpenStateMapping
	});
});
DialogTrigger.displayName = "DialogTrigger";
//#endregion
//#region node_modules/@base-ui/react/dialog/store/DialogHandle.mjs
/**
* A handle to control a Dialog imperatively and to associate detached triggers with it.
*/
var DialogHandle = class {
	/**
	* Internal store holding the dialog state.
	* @internal
	*/
	constructor(store) {
		this.store = store ?? new DialogStore();
	}
	/**
	* Opens the dialog and associates it with the trigger with the given id.
	* The trigger, if provided, must be a matching Trigger component with this handle passed as a prop.
	*
	* This method should only be called in an event handler or an effect (not during rendering).
	*
	* @param triggerId ID of the trigger to associate with the dialog. If null, the dialog will open without a trigger association.
	*/
	open(triggerId) {
		const triggerElement = triggerId ? this.store.context.triggerElements.getById(triggerId) : void 0;
		if (triggerId && !triggerElement) console.warn(`Base UI: DialogHandle.open: No trigger found with id "${triggerId}". The dialog will open, but the trigger will not be associated with the dialog.`);
		this.store.setOpen(true, createChangeEventDetails(imperativeAction, void 0, triggerElement));
	}
	/**
	* Opens the dialog and sets the payload.
	* Does not associate the dialog with any trigger.
	*
	* @param payload Payload to set when opening the dialog.
	*/
	openWithPayload(payload) {
		this.store.set("payload", payload);
		this.store.setOpen(true, createChangeEventDetails(imperativeAction, void 0, void 0));
	}
	/**
	* Closes the dialog.
	*/
	close() {
		this.store.setOpen(false, createChangeEventDetails(imperativeAction, void 0, void 0));
	}
	/**
	* Indicates whether the dialog is currently open.
	*/
	get isOpen() {
		return this.store.select("open");
	}
};
/**
* Creates a new handle to connect a Dialog.Root with detached Dialog.Trigger components.
*/
function createDialogHandle() {
	return new DialogHandle();
}
//#endregion
//#region node_modules/@base-ui/react/dialog/index.parts.mjs
var index_parts_exports = /* @__PURE__ */ __exportAll({
	Backdrop: () => DialogBackdrop,
	Close: () => DialogClose,
	Description: () => DialogDescription,
	Handle: () => DialogHandle,
	Popup: () => DialogPopup,
	Portal: () => DialogPortal,
	Root: () => DialogRoot,
	Title: () => DialogTitle,
	Trigger: () => DialogTrigger,
	Viewport: () => DialogViewport,
	createHandle: () => createDialogHandle
});
//#endregion
export { index_parts_exports as Dialog };
