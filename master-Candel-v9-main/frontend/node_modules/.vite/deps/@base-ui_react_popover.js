import { n as __exportAll, r as __toESM } from "./rolldown-runtime-B-1-B7_t.js";
import { t as require_react } from "./react.js";
import { g as isHTMLElement, r as useStableCallback, t as useIsoLayoutEffect } from "./useIsoLayoutEffect-DrOR77jl.js";
import { r as EMPTY_OBJECT, t as useRenderElement } from "./useRenderElement-BiX6Dyza.js";
import { r as mergeProps } from "./merge-props-B1zstas5.js";
import { t as useButton } from "./useButton-DFSPkxH_.js";
import { g as triggerHover, r as closePress, s as imperativeAction, t as createChangeEventDetails, y as useBaseUiId } from "./createBaseUIEventDetails-BNfSv2gm.js";
import { t as require_jsx_runtime } from "./react_jsx-runtime.js";
import { t as require_react_dom } from "./react-dom.js";
import { a as transitionStatusMapping, n as useOpenChangeComplete, r as useAnimationsFinished } from "./useTransitionStatus-CDr8WmsC.js";
import { A as FloatingNode, B as POPUP_COLLISION_AVOIDANCE, D as useDismiss, I as FloatingPortal, J as FocusGuard, L as CLICK_TRIGGER_IDENTIFIER, M as useFloatingNodeId, N as useFloatingParentNodeId, O as useClick, T as createSelector, a as PopupTriggerMap, b as ReactStore, bt as triggerOpenStateMapping, c as createDefaultInitialFocus, d as useInitialOpenSync, f as useOpenStateTransitions, g as useTriggerDataForwarding, h as usePopupStore, ht as Timeout, i as InternalBackdrop, j as FloatingTree, k as FloatingFocusManager, l as setPopupOpenState, m as usePopupRootSync, n as useOpenMethodTriggerProps, o as FOCUSABLE_POPUP_PROPS, p as usePopupInteractionProps, s as attachPreventUnmountOnClose, u as useImplicitActiveTrigger, vt as popupStateMapping, yt as pressableTriggerOpenStateMapping } from "./useOpenInteractionType-fml9RCjU.js";
import { a as useHoverFloatingInteraction, i as useHoverReferenceInteraction, n as useTriggerFocusGuards, r as safePolygon, t as usePopupViewport } from "./usePopupViewport-9tQdVQKu.js";
import { s as COMPOSITE_KEYS, t as inertValue } from "./inertValue-J_gNalGy.js";
import { a as adaptiveOrigin, i as useAnchorPositioning, n as useAnchoredPopupScrollLock, o as getDisabledMountTransitionStyles, r as usePositioner, s as useToolbarRootContext } from "./usePreviousValue-D_tVHlXk.js";
import { n as createPopupFloatingRootContext, r as popupStoreSelectors, t as createInitialPopupStoreState } from "./store-DgHEBjVg.js";
//#region node_modules/@base-ui/react/popover/root/PopoverRootContext.mjs
var import_react = /* @__PURE__ */ __toESM(require_react(), 1);
var PopoverRootContext = /*#__PURE__*/ import_react.createContext(void 0);
PopoverRootContext.displayName = "PopoverRootContext";
function usePopoverRootContext(optional) {
	const context = import_react.useContext(PopoverRootContext);
	if (context === void 0 && !optional) throw new Error("Base UI: PopoverRootContext is missing. Popover parts must be placed within <Popover.Root>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/popover/store/PopoverStore.mjs
var import_react_dom = /* @__PURE__ */ __toESM(require_react_dom(), 1);
function createInitialState() {
	return {
		...createInitialPopupStoreState(),
		disabled: false,
		modal: false,
		focusManagerModal: false,
		instantType: void 0,
		openMethod: null,
		openChangeReason: null,
		titleElementId: void 0,
		descriptionElementId: void 0,
		stickIfOpen: true,
		nested: false,
		openOnHover: false,
		closeDelay: 0,
		hasViewport: false
	};
}
var selectors = {
	...popupStoreSelectors,
	disabled: createSelector((state) => state.disabled),
	instantType: createSelector((state) => state.instantType),
	openMethod: createSelector((state) => state.openMethod),
	openChangeReason: createSelector((state) => state.openChangeReason),
	modal: createSelector((state) => state.modal),
	focusManagerModal: createSelector((state) => state.focusManagerModal),
	stickIfOpen: createSelector((state) => state.stickIfOpen),
	titleElementId: createSelector((state) => state.titleElementId),
	descriptionElementId: createSelector((state) => state.descriptionElementId),
	openOnHover: createSelector((state) => state.openOnHover),
	closeDelay: createSelector((state) => state.closeDelay),
	hasViewport: createSelector((state) => state.hasViewport)
};
var PopoverStore = class PopoverStore extends ReactStore {
	constructor(initialState, floatingId, nested = false) {
		const initial = {
			...createInitialState(),
			...initialState
		};
		const triggerElements = new PopupTriggerMap();
		if (initial.open && initialState?.mounted === void 0) initial.mounted = true;
		initial.floatingRootContext = createPopupFloatingRootContext(triggerElements, floatingId, nested);
		super(initial, {
			popupRef: /*#__PURE__*/ import_react.createRef(),
			backdropRef: /*#__PURE__*/ import_react.createRef(),
			internalBackdropRef: /*#__PURE__*/ import_react.createRef(),
			onOpenChange: void 0,
			onOpenChangeComplete: void 0,
			triggerFocusTargetRef: /*#__PURE__*/ import_react.createRef(),
			beforeContentFocusGuardRef: /*#__PURE__*/ import_react.createRef(),
			stickIfOpenTimeout: new Timeout(),
			triggerElements
		}, selectors);
	}
	setOpen = (nextOpen, eventDetails) => {
		const isHover = eventDetails.reason === triggerHover;
		const isKeyboardClick = eventDetails.reason === "trigger-press" && eventDetails.event.detail === 0;
		const isDismissClose = !nextOpen && (eventDetails.reason === "escape-key" || eventDetails.reason == null);
		const shouldPreventUnmountOnClose = attachPreventUnmountOnClose(eventDetails);
		const activeTriggerId = this.select("activeTriggerId");
		if (!nextOpen && eventDetails.reason === "close-press" && eventDetails.trigger == null && activeTriggerId != null) eventDetails.trigger = this.context.triggerElements.getById(activeTriggerId) ?? this.select("activeTriggerElement") ?? void 0;
		this.context.onOpenChange?.(nextOpen, eventDetails);
		if (eventDetails.isCanceled) return;
		this.state.floatingRootContext.dispatchOpenChange(nextOpen, eventDetails);
		const changeState = () => {
			const updatedState = {
				open: nextOpen,
				openChangeReason: eventDetails.reason
			};
			setPopupOpenState(updatedState, nextOpen, eventDetails.trigger, shouldPreventUnmountOnClose());
			this.update(updatedState);
		};
		if (isHover) {
			this.set("stickIfOpen", true);
			this.context.stickIfOpenTimeout.start(500, () => {
				this.set("stickIfOpen", false);
			});
			import_react_dom.flushSync(changeState);
		} else changeState();
		if (isKeyboardClick || isDismissClose) this.set("instantType", isKeyboardClick ? "click" : "dismiss");
		else if (eventDetails.reason === "focus-out") this.set("instantType", "focus");
		else this.set("instantType", void 0);
	};
	static useStore(externalStore, initialState) {
		const { store, internalStore } = usePopupStore(externalStore, (floatingId, nested) => new PopoverStore(initialState, floatingId, nested));
		import_react.useEffect(() => internalStore?.disposeEffect(), [internalStore]);
		return store;
	}
	disposeEffect = () => {
		return this.context.stickIfOpenTimeout.disposeEffect();
	};
};
//#endregion
//#region node_modules/@base-ui/react/popover/root/PopoverRoot.mjs
var import_jsx_runtime = require_jsx_runtime();
function PopoverRootComponent({ props }) {
	const { children, open: openProp, defaultOpen = false, onOpenChange, onOpenChangeComplete, modal = false, handle, triggerId: triggerIdProp, defaultTriggerId: defaultTriggerIdProp = null } = props;
	const store = PopoverStore.useStore(handle?.store, {
		modal,
		open: defaultOpen,
		openProp,
		activeTriggerId: defaultTriggerIdProp,
		triggerIdProp
	});
	useInitialOpenSync(store, openProp, defaultOpen, defaultTriggerIdProp);
	store.useControlledProp("openProp", openProp);
	store.useControlledProp("triggerIdProp", triggerIdProp);
	const open = store.useState("open");
	const mounted = store.useState("mounted");
	const payload = store.useState("payload");
	const nested = useFloatingParentNodeId() != null;
	store.useContextCallback("onOpenChange", onOpenChange);
	store.useContextCallback("onOpenChangeComplete", onOpenChangeComplete);
	usePopupRootSync(store, open);
	useImplicitActiveTrigger(store);
	const { forceUnmount } = useOpenStateTransitions(open, store, () => {
		store.update({
			stickIfOpen: true,
			openChangeReason: null
		});
	});
	store.useSyncedValues({
		modal,
		nested
	});
	import_react.useEffect(() => {
		if (!open) store.context.stickIfOpenTimeout.clear();
	}, [store, open]);
	const handleImperativeClose = import_react.useCallback(() => {
		store.setOpen(false, createChangeEventDetails(imperativeAction));
	}, [store]);
	import_react.useImperativeHandle(props.actionsRef, () => ({
		unmount: forceUnmount,
		close: handleImperativeClose
	}), [forceUnmount, handleImperativeClose]);
	const shouldRenderInteractions = open || mounted;
	const popoverContext = import_react.useMemo(() => ({ store }), [store]);
	return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(PopoverRootContext.Provider, {
		value: popoverContext,
		children: [shouldRenderInteractions && /*#__PURE__*/ (0, import_jsx_runtime.jsx)(PopoverInteractions, {
			store,
			modal
		}), typeof children === "function" ? children({ payload }) : children]
	});
}
/**
* Groups all parts of the popover.
* Doesn't render its own HTML element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
function PopoverRoot(props) {
	if (usePopoverRootContext(true)) return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(PopoverRootComponent, { props });
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingTree, { children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(PopoverRootComponent, { props }) });
}
function PopoverInteractions({ store, modal }) {
	const dismiss = useDismiss(store.useState("floatingRootContext"), { outsidePressEvent: {
		mouse: modal === "trap-focus" ? "sloppy" : "intentional",
		touch: "sloppy"
	} });
	usePopupInteractionProps(store, {
		activeTriggerProps: dismiss.reference ?? EMPTY_OBJECT,
		inactiveTriggerProps: dismiss.trigger ?? EMPTY_OBJECT,
		popupProps: import_react.useMemo(() => mergeProps(FOCUSABLE_POPUP_PROPS, dismiss.floating), [dismiss.floating])
	});
	return null;
}
//#endregion
//#region node_modules/@base-ui/react/popover/trigger/PopoverTrigger.mjs
/**
* A button that opens the popover.
* Renders a `<button>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverTrigger = /*#__PURE__*/ import_react.forwardRef(function PopoverTrigger(componentProps, forwardedRef) {
	const { render, className, style, disabled = false, nativeButton = true, handle, payload, openOnHover = false, delay = 300, closeDelay = 0, id: idProp, ...elementProps } = componentProps;
	const rootContext = usePopoverRootContext(true);
	const store = handle?.store ?? rootContext?.store;
	if (!store) throw new Error("Base UI: <Popover.Trigger> must be either used within a <Popover.Root> component or provided with a handle.");
	const thisTriggerId = useBaseUiId(idProp);
	const isTriggerActive = store.useState("isTriggerActive", thisTriggerId);
	const floatingContext = store.useState("floatingRootContext");
	const isOpenedByThisTrigger = store.useState("isOpenedByTrigger", thisTriggerId);
	const popupId = store.useState("triggerPopupId", thisTriggerId);
	const triggerElementRef = import_react.useRef(null);
	const { registerTrigger, isMountedByThisTrigger } = useTriggerDataForwarding(thisTriggerId, triggerElementRef, store, {
		payload,
		disabled,
		openOnHover,
		closeDelay
	});
	const openReason = store.useState("openChangeReason");
	const stickIfOpen = store.useState("stickIfOpen");
	const openMethod = store.useState("openMethod");
	const focusManagerModal = store.useState("focusManagerModal");
	const hoverProps = useHoverReferenceInteraction(floatingContext, {
		enabled: !disabled && floatingContext != null && openOnHover && (openMethod !== "touch" || openReason !== "trigger-press"),
		mouseOnly: true,
		move: false,
		handleClose: safePolygon(),
		restMs: delay,
		delay: { close: closeDelay },
		triggerElementRef,
		isActiveTrigger: isTriggerActive,
		isClosing: () => store.select("transitionStatus") === "ending"
	});
	const click = useClick(floatingContext, {
		enabled: floatingContext != null,
		stickIfOpen
	});
	const interactionTypeProps = useOpenMethodTriggerProps(() => store.select("open"), (interactionType) => {
		store.set("openMethod", interactionType);
	});
	const rootTriggerProps = store.useState("triggerProps", isMountedByThisTrigger);
	const { getButtonProps, buttonRef } = useButton({
		disabled,
		native: nativeButton
	});
	const stateAttributesMapping = { open(value) {
		if (value && openReason === "trigger-press") return pressableTriggerOpenStateMapping.open(value);
		return triggerOpenStateMapping.open(value);
	} };
	const { preFocusGuardRef, handlePreFocusGuardFocus, handleFocusTargetFocus } = useTriggerFocusGuards(store, triggerElementRef);
	const element = useRenderElement("button", componentProps, {
		state: {
			disabled,
			open: isOpenedByThisTrigger
		},
		ref: [
			buttonRef,
			forwardedRef,
			registerTrigger,
			triggerElementRef
		],
		props: [
			click.reference,
			hoverProps,
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
		stateAttributesMapping
	});
	if (isMountedByThisTrigger && !focusManagerModal) return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(import_react.Fragment, { children: [
		/*#__PURE__*/ (0, import_jsx_runtime.jsx)(FocusGuard, {
			ref: preFocusGuardRef,
			onFocus: handlePreFocusGuardFocus
		}),
		/*#__PURE__*/ (0, import_jsx_runtime.jsx)(import_react.Fragment, { children: element }, thisTriggerId),
		/*#__PURE__*/ (0, import_jsx_runtime.jsx)(FocusGuard, {
			ref: store.context.triggerFocusTargetRef,
			onFocus: handleFocusTargetFocus
		})
	] });
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(import_react.Fragment, { children: element }, thisTriggerId);
});
PopoverTrigger.displayName = "PopoverTrigger";
//#endregion
//#region node_modules/@base-ui/react/popover/portal/PopoverPortalContext.mjs
var PopoverPortalContext = /*#__PURE__*/ import_react.createContext(void 0);
PopoverPortalContext.displayName = "PopoverPortalContext";
function usePopoverPortalContext() {
	const value = import_react.useContext(PopoverPortalContext);
	if (value === void 0) throw new Error("Base UI: <Popover.Portal> is missing.");
	return value;
}
//#endregion
//#region node_modules/@base-ui/react/popover/portal/PopoverPortal.mjs
/**
* A portal element that moves the popup to a different part of the DOM.
* By default, the portal element is appended to `<body>`.
* Renders a `<div>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverPortal = /*#__PURE__*/ import_react.forwardRef(function PopoverPortal(props, forwardedRef) {
	const { keepMounted = false, ...portalProps } = props;
	const { store } = usePopoverRootContext();
	if (!(store.useState("mounted") || keepMounted)) return null;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(PopoverPortalContext.Provider, {
		value: keepMounted,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingPortal, {
			ref: forwardedRef,
			...portalProps
		})
	});
});
PopoverPortal.displayName = "PopoverPortal";
//#endregion
//#region node_modules/@base-ui/react/popover/positioner/PopoverPositionerContext.mjs
var PopoverPositionerContext = /*#__PURE__*/ import_react.createContext(void 0);
PopoverPositionerContext.displayName = "PopoverPositionerContext";
function usePopoverPositionerContext() {
	const context = import_react.useContext(PopoverPositionerContext);
	if (!context) throw new Error("Base UI: PopoverPositionerContext is missing. PopoverPositioner parts must be placed within <Popover.Positioner>.");
	return context;
}
//#endregion
//#region node_modules/@base-ui/react/popover/positioner/PopoverPositioner.mjs
/**
* Positions the popover against the trigger.
* Renders a `<div>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverPositioner = /*#__PURE__*/ import_react.forwardRef(function PopoverPositioner(componentProps, forwardedRef) {
	const { render, className, style, anchor, positionMethod = "absolute", side = "bottom", align = "center", sideOffset = 0, alignOffset = 0, collisionBoundary = "clipping-ancestors", collisionPadding = 5, arrowPadding = 5, sticky = false, disableAnchorTracking = false, collisionAvoidance = POPUP_COLLISION_AVOIDANCE, ...elementProps } = componentProps;
	const { store } = usePopoverRootContext();
	const keepMounted = usePopoverPortalContext();
	const nodeId = useFloatingNodeId();
	const floatingRootContext = store.useState("floatingRootContext");
	const mounted = store.useState("mounted");
	const open = store.useState("open");
	const openReason = store.useState("openChangeReason");
	const triggerElement = store.useState("activeTriggerElement");
	const modal = store.useState("modal");
	const openMethod = store.useState("openMethod");
	const positionerElement = store.useState("positionerElement");
	const instantType = store.useState("instantType");
	const transitionStatus = store.useState("transitionStatus");
	const hasViewport = store.useState("hasViewport");
	const prevTriggerElementRef = import_react.useRef(null);
	const runOnceAnimationsFinish = useAnimationsFinished(positionerElement, false, false);
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
		disableAnchorTracking,
		keepMounted,
		nodeId,
		collisionAvoidance,
		adaptiveOrigin: hasViewport ? adaptiveOrigin : void 0
	});
	const domReference = floatingRootContext.useState("domReferenceElement");
	useIsoLayoutEffect(() => {
		const currentTriggerElement = domReference;
		const prevTriggerElement = prevTriggerElementRef.current;
		if (currentTriggerElement) prevTriggerElementRef.current = currentTriggerElement;
		if (prevTriggerElement && currentTriggerElement && currentTriggerElement !== prevTriggerElement) {
			store.set("instantType", void 0);
			const ac = new AbortController();
			runOnceAnimationsFinish(() => {
				store.set("instantType", "trigger-change");
			}, ac.signal);
			return () => {
				ac.abort();
			};
		}
	}, [
		domReference,
		runOnceAnimationsFinish,
		store
	]);
	useAnchoredPopupScrollLock(open && modal === true && openReason !== "trigger-hover", openMethod === "touch", positionerElement, triggerElement);
	const setPositionerElement = import_react.useCallback((element) => {
		store.set("positionerElement", element);
	}, [store]);
	const element = usePositioner(componentProps, {
		open,
		side: positioning.side,
		align: positioning.align,
		anchorHidden: positioning.anchorHidden,
		instant: instantType
	}, {
		styles: positioning.positionerStyles,
		transitionStatus,
		props: elementProps,
		refs: [forwardedRef, setPositionerElement],
		hidden: !mounted,
		inert: !open
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsxs)(PopoverPositionerContext.Provider, {
		value: positioning,
		children: [mounted && modal === true && openReason !== "trigger-hover" && /*#__PURE__*/ (0, import_jsx_runtime.jsx)(InternalBackdrop, {
			ref: store.context.internalBackdropRef,
			inert: inertValue(!open),
			cutout: triggerElement
		}), /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingNode, {
			id: nodeId,
			children: element
		})]
	});
});
PopoverPositioner.displayName = "PopoverPositioner";
//#endregion
//#region node_modules/@base-ui/react/utils/closePart.mjs
var ClosePartContext = /*#__PURE__*/ import_react.createContext(void 0);
ClosePartContext.displayName = "ClosePartContext";
function useClosePartCount() {
	const [closePartCount, setClosePartCount] = import_react.useState(0);
	const register = useStableCallback(() => {
		setClosePartCount((count) => count + 1);
		return () => {
			setClosePartCount((count) => Math.max(0, count - 1));
		};
	});
	return {
		context: import_react.useMemo(() => ({ register }), [register]),
		hasClosePart: closePartCount > 0
	};
}
function ClosePartProvider(props) {
	const { value, children } = props;
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(ClosePartContext.Provider, {
		value,
		children
	});
}
function useClosePartRegistration() {
	const context = import_react.useContext(ClosePartContext);
	useIsoLayoutEffect(() => {
		return context?.register();
	}, [context]);
}
//#endregion
//#region node_modules/@base-ui/react/popover/popup/PopoverPopup.mjs
var stateAttributesMapping$2 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* A container for the popover contents.
* Renders a `<div>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverPopup = /*#__PURE__*/ import_react.forwardRef(function PopoverPopup(componentProps, forwardedRef) {
	const { render, className, style, initialFocus, finalFocus, ...elementProps } = componentProps;
	const { store } = usePopoverRootContext();
	const positioner = usePopoverPositionerContext();
	const insideToolbar = useToolbarRootContext(true) != null;
	const { context: closePartContext, hasClosePart } = useClosePartCount();
	const open = store.useState("open");
	const openMethod = store.useState("openMethod");
	const instantType = store.useState("instantType");
	const transitionStatus = store.useState("transitionStatus");
	const popupProps = store.useState("popupProps");
	const titleId = store.useState("titleElementId");
	const descriptionId = store.useState("descriptionElementId");
	const modal = store.useState("modal");
	const mounted = store.useState("mounted");
	const openReason = store.useState("openChangeReason");
	const activeTriggerElement = store.useState("activeTriggerElement");
	const floatingContext = store.useState("floatingRootContext");
	const floatingId = floatingContext.useState("floatingId");
	const disabled = store.useState("disabled");
	const openOnHover = store.useState("openOnHover");
	const closeDelay = store.useState("closeDelay");
	const popupId = elementProps.id ?? floatingId;
	useOpenChangeComplete({
		open,
		ref: store.context.popupRef,
		onComplete() {
			if (open) store.context.onOpenChangeComplete?.(true);
		}
	});
	useHoverFloatingInteraction(floatingContext, {
		enabled: openOnHover && !disabled,
		closeDelay
	});
	const resolvedInitialFocus = initialFocus === void 0 ? createDefaultInitialFocus(store.context.popupRef) : initialFocus;
	const focusManagerModal = modal !== false && hasClosePart;
	store.useSyncedValue("focusManagerModal", focusManagerModal);
	const setPopupElement = import_react.useCallback((element) => {
		store.set("popupElement", element);
	}, [store]);
	const element = useRenderElement("div", componentProps, {
		state: {
			open,
			side: positioner.side,
			align: positioner.align,
			instant: instantType,
			transitionStatus
		},
		ref: [
			forwardedRef,
			store.context.popupRef,
			setPopupElement
		],
		props: [
			popupProps,
			{
				id: popupId,
				role: "dialog",
				...FOCUSABLE_POPUP_PROPS,
				"aria-labelledby": titleId,
				"aria-describedby": descriptionId,
				onKeyDown(event) {
					if (insideToolbar && COMPOSITE_KEYS.has(event.key)) event.stopPropagation();
				}
			},
			getDisabledMountTransitionStyles(transitionStatus),
			elementProps
		],
		stateAttributesMapping: stateAttributesMapping$2
	});
	return /*#__PURE__*/ (0, import_jsx_runtime.jsx)(FloatingFocusManager, {
		context: floatingContext,
		openInteractionType: openMethod,
		modal: focusManagerModal,
		disabled: !mounted || openReason === "trigger-hover",
		initialFocus: resolvedInitialFocus,
		returnFocus: finalFocus,
		restoreFocus: "popup",
		previousFocusableElement: isHTMLElement(activeTriggerElement) ? activeTriggerElement : void 0,
		nextFocusableElement: store.context.triggerFocusTargetRef,
		beforeContentFocusGuardRef: store.context.beforeContentFocusGuardRef,
		children: /*#__PURE__*/ (0, import_jsx_runtime.jsx)(ClosePartProvider, {
			value: closePartContext,
			children: element
		})
	});
});
PopoverPopup.displayName = "PopoverPopup";
//#endregion
//#region node_modules/@base-ui/react/popover/arrow/PopoverArrow.mjs
/**
* Displays an element positioned against the popover anchor.
* Renders a `<div>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverArrow = /*#__PURE__*/ import_react.forwardRef(function PopoverArrow(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = usePopoverRootContext();
	const open = store.useState("open");
	const { arrowRef, side, align, arrowUncentered, arrowStyles } = usePopoverPositionerContext();
	return useRenderElement("div", componentProps, {
		state: {
			open,
			side,
			align,
			uncentered: arrowUncentered
		},
		ref: [forwardedRef, arrowRef],
		props: [{
			style: arrowStyles,
			"aria-hidden": true
		}, elementProps],
		stateAttributesMapping: popupStateMapping
	});
});
PopoverArrow.displayName = "PopoverArrow";
//#endregion
//#region node_modules/@base-ui/react/popover/backdrop/PopoverBackdrop.mjs
var stateAttributesMapping$1 = {
	...popupStateMapping,
	...transitionStatusMapping
};
/**
* An overlay displayed beneath the popover.
* Renders a `<div>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverBackdrop = /*#__PURE__*/ import_react.forwardRef(function PopoverBackdrop(props, forwardedRef) {
	const { render, className, style, ...elementProps } = props;
	const { store } = usePopoverRootContext();
	const open = store.useState("open");
	const mounted = store.useState("mounted");
	const transitionStatus = store.useState("transitionStatus");
	const openReason = store.useState("openChangeReason");
	return useRenderElement("div", props, {
		state: {
			open,
			transitionStatus
		},
		ref: [store.context.backdropRef, forwardedRef],
		props: [{
			role: "presentation",
			hidden: !mounted,
			style: {
				pointerEvents: openReason === "trigger-hover" ? "none" : void 0,
				userSelect: "none",
				WebkitUserSelect: "none"
			}
		}, elementProps],
		stateAttributesMapping: stateAttributesMapping$1
	});
});
PopoverBackdrop.displayName = "PopoverBackdrop";
//#endregion
//#region node_modules/@base-ui/react/popover/title/PopoverTitle.mjs
/**
* A heading that labels the popover.
* Renders an `<h2>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverTitle = /*#__PURE__*/ import_react.forwardRef(function PopoverTitle(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = usePopoverRootContext();
	const id = useBaseUiId(elementProps.id);
	store.useSyncedValueWithCleanup("titleElementId", id);
	return useRenderElement("h2", componentProps, {
		ref: forwardedRef,
		props: [{ id }, elementProps]
	});
});
PopoverTitle.displayName = "PopoverTitle";
//#endregion
//#region node_modules/@base-ui/react/popover/description/PopoverDescription.mjs
/**
* A paragraph with additional information about the popover.
* Renders a `<p>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverDescription = /*#__PURE__*/ import_react.forwardRef(function PopoverDescription(componentProps, forwardedRef) {
	const { render, className, style, ...elementProps } = componentProps;
	const { store } = usePopoverRootContext();
	const id = useBaseUiId(elementProps.id);
	store.useSyncedValueWithCleanup("descriptionElementId", id);
	return useRenderElement("p", componentProps, {
		ref: forwardedRef,
		props: [{ id }, elementProps]
	});
});
PopoverDescription.displayName = "PopoverDescription";
//#endregion
//#region node_modules/@base-ui/react/popover/close/PopoverClose.mjs
/**
* A button that closes the popover.
* Renders a `<button>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverClose = /*#__PURE__*/ import_react.forwardRef(function PopoverClose(componentProps, forwardedRef) {
	const { render, className, style, disabled = false, nativeButton = true, ...elementProps } = componentProps;
	const { buttonRef, getButtonProps } = useButton({
		disabled,
		focusableWhenDisabled: false,
		native: nativeButton
	});
	const { store } = usePopoverRootContext();
	useClosePartRegistration();
	return useRenderElement("button", componentProps, {
		ref: [forwardedRef, buttonRef],
		props: [
			{ onClick(event) {
				store.setOpen(false, createChangeEventDetails(closePress, event.nativeEvent));
			} },
			elementProps,
			getButtonProps
		]
	});
});
PopoverClose.displayName = "PopoverClose";
//#endregion
//#region node_modules/@base-ui/react/popover/viewport/PopoverViewportCssVars.mjs
var PopoverViewportCssVars = /*#__PURE__*/ function(PopoverViewportCssVars) {
	/**
	* The width of the parent popup.
	* This variable is placed on the 'previous' container and stores the width of the popup when the previous content was rendered.
	* It can be used to freeze the dimensions of the popup when animating between different content.
	*/
	PopoverViewportCssVars["popupWidth"] = "--popup-width";
	/**
	* The height of the parent popup.
	* This variable is placed on the 'previous' container and stores the height of the popup when the previous content was rendered.
	* It can be used to freeze the dimensions of the popup when animating between different content.
	*/
	PopoverViewportCssVars["popupHeight"] = "--popup-height";
	return PopoverViewportCssVars;
}({});
//#endregion
//#region node_modules/@base-ui/react/popover/viewport/PopoverViewport.mjs
var stateAttributesMapping = { activationDirection: (value) => value ? { "data-activation-direction": value } : null };
/**
* A viewport for displaying content transitions.
* This component is only required if one popup can be opened by multiple triggers, its content
* changes based on the trigger, and switching between them is animated.
* Renders a `<div>` element.
*
* Documentation: [Base UI Popover](https://base-ui.com/react/components/popover)
*/
var PopoverViewport = /*#__PURE__*/ import_react.forwardRef(function PopoverViewport(componentProps, forwardedRef) {
	const { render, className, style, children, ...elementProps } = componentProps;
	const { store } = usePopoverRootContext();
	const { side } = usePopoverPositionerContext();
	const instantType = store.useState("instantType");
	const { children: childrenToRender, state: viewportState } = usePopupViewport({
		store,
		side,
		cssVars: PopoverViewportCssVars,
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
PopoverViewport.displayName = "PopoverViewport";
//#endregion
//#region node_modules/@base-ui/react/popover/store/PopoverHandle.mjs
var PopoverHandle = class {
	/**
	* Internal store holding the popover's state.
	* @internal
	*/
	constructor() {
		this.store = new PopoverStore();
	}
	/**
	* Opens the popover and associates it with the trigger with the given id.
	* The trigger must be a Popover.Trigger component with this handle passed as a prop.
	*
	* @param triggerId ID of the trigger to associate with the popover.
	*/
	open(triggerId) {
		const triggerElement = triggerId ? this.store.context.triggerElements.getById(triggerId) ?? void 0 : void 0;
		if (triggerId && !triggerElement) throw new Error(`Base UI: PopoverHandle.open: No trigger found with id "${triggerId}".`);
		this.store.setOpen(true, createChangeEventDetails(imperativeAction, void 0, triggerElement));
	}
	/**
	* Closes the popover.
	*/
	close() {
		this.store.setOpen(false, createChangeEventDetails(imperativeAction, void 0, void 0));
	}
	/**
	* Indicates whether the popover is currently open.
	*/
	get isOpen() {
		return this.store.select("open");
	}
};
/**
* Creates a new handle to connect a Popover.Root with detached Popover.Trigger components.
*/
function createPopoverHandle() {
	return new PopoverHandle();
}
//#endregion
//#region node_modules/@base-ui/react/popover/index.parts.mjs
var index_parts_exports = /* @__PURE__ */ __exportAll({
	Arrow: () => PopoverArrow,
	Backdrop: () => PopoverBackdrop,
	Close: () => PopoverClose,
	Description: () => PopoverDescription,
	Handle: () => PopoverHandle,
	Popup: () => PopoverPopup,
	Portal: () => PopoverPortal,
	Positioner: () => PopoverPositioner,
	Root: () => PopoverRoot,
	Title: () => PopoverTitle,
	Trigger: () => PopoverTrigger,
	Viewport: () => PopoverViewport,
	createHandle: () => createPopoverHandle
});
//#endregion
export { index_parts_exports as Popover };
