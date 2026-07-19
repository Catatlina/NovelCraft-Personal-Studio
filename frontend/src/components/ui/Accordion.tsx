import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

export interface AccordionItem {
  key: string;
  title: string;
  content: React.ReactNode;
  defaultOpen?: boolean;
}

export interface AccordionProps {
  items: AccordionItem[];
}

/**
 * Vertically stacked, independently collapsible panels. Each item's open state
 * is controlled internally via useState, seeded from `defaultOpen`. The chevron
 * rotates through the `.accordion-item.open` class.
 */
export function Accordion({ items }: AccordionProps): React.ReactElement {
  const [openKeys, setOpenKeys] = useState<Set<string>>(
    () => new Set(items.filter((it) => it.defaultOpen).map((it) => it.key)),
  );

  const toggle = (key: string): void => {
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="accordion">
      {items.map((item) => {
        const isOpen = openKeys.has(item.key);
        return (
          <div key={item.key} className={`accordion-item${isOpen ? " open" : ""}`}>
            <button
              type="button"
              className="accordion-header"
              onClick={() => toggle(item.key)}
              aria-expanded={isOpen}
            >
              <span>{item.title}</span>
              <ChevronDown className="chevron" />
            </button>
            <div className={`accordion-body${isOpen ? "" : " collapsed"}`}>
              {item.content}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default Accordion;
