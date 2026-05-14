import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode, RefObject } from "react";
import { createPortal } from "react-dom";

interface ComboboxPopupProps {
  /** Element the popup anchors to (the input). */
  triggerRef: RefObject<HTMLElement | null>;
  /** Whether the popup is currently visible. */
  open: boolean;
  /** Called when an outside click should dismiss the popup. */
  onRequestClose: () => void;
  /** Listbox id (matches the trigger's aria-controls). */
  id: string;
  className?: string;
  children: ReactNode;
}

/**
 * Floating combobox listbox rendered into document.body so it never gets
 * clipped by ancestor `overflow: hidden` (e.g. inside a Card). Position is
 * pinned to the trigger and recomputed on scroll/resize. Outside-click is
 * handled here so consumers don't need to thread popup refs through their
 * own document listeners.
 */
export function ComboboxPopup({
  triggerRef,
  open,
  onRequestClose,
  id,
  className,
  children,
}: ComboboxPopupProps) {
  const popupRef = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<CSSProperties | null>(null);

  // Position: track the trigger's viewport rect. Flip above the trigger when
  // there's not enough room below (e.g. Sunday's slot near the bottom of the
  // schedule page). Always cap maxHeight to whatever space is actually free
  // so the listbox never clips off the bottom of the viewport.
  useEffect(() => {
    if (!open || !triggerRef.current) {
      setStyle(null);
      return;
    }
    const MARGIN = 8; // breathing room from the viewport edge
    const MIN_HEIGHT = 120; // require at least this much room before preferring below

    const update = () => {
      const el = triggerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const spaceBelow = vh - rect.bottom - MARGIN;
      const spaceAbove = rect.top - MARGIN;

      // Prefer below when there's room; otherwise pick whichever side has more.
      const placeBelow = spaceBelow >= MIN_HEIGHT || spaceBelow >= spaceAbove;
      const next: CSSProperties = {
        position: "fixed",
        left: rect.left,
        width: rect.width,
        zIndex: 50,
        maxHeight: Math.max(80, placeBelow ? spaceBelow : spaceAbove),
      };
      if (placeBelow) {
        next.top = rect.bottom + 4;
      } else {
        next.bottom = vh - rect.top + 4;
      }
      setStyle(next);
    };
    update();
    // Capture-phase scroll listener catches scrolls on any ancestor.
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open, triggerRef]);

  // Outside-click → close. Lives here because the portal node isn't a
  // descendant of the trigger, so a parent ref-contains check wouldn't see it.
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (triggerRef.current?.contains(target)) return;
      if (popupRef.current?.contains(target)) return;
      onRequestClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, triggerRef, onRequestClose]);

  if (!open || !style) return null;

  return createPortal(
    <div
      ref={popupRef}
      id={id}
      role="listbox"
      style={style}
      className={className}
    >
      {children}
    </div>,
    document.body
  );
}
