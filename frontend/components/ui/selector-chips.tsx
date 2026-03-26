"use client";

import { motion, AnimatePresence } from "motion/react";

export interface SelectorChipsProps {
  options: string[];
  value: string[];
  onChange: (selected: string[]) => void;
  labels?: Record<string, string>;
  descriptions?: Record<string, string>;
}

function SelectorChips({
  options,
  value,
  onChange,
  labels,
  descriptions,
}: SelectorChipsProps) {
  const toggleChip = (option: string) => {
    const updated = value.includes(option)
      ? value.filter((o) => o !== option)
      : [...value, option];
    onChange(updated);
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const isSelected = value.includes(option);
        const label = labels?.[option] ?? option;
        return (
          <motion.button
            type="button"
            key={option}
            onClick={() => toggleChip(option)}
            initial={false}
            aria-pressed={isSelected}
            className={`
              flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium
              border transition-colors cursor-pointer select-none
              ${
                isSelected
                  ? "bg-foreground text-background border-foreground"
                  : "bg-transparent text-muted-foreground border-border hover:border-foreground/30 hover:text-foreground"
              }
            `}
            title={descriptions?.[option]}
          >
            <span>{label}</span>
            <AnimatePresence>
              {isSelected && (
                <motion.span
                  key="tick"
                  initial={{ scale: 0, opacity: 0, width: 0 }}
                  animate={{ scale: 1, opacity: 1, width: 14 }}
                  exit={{ scale: 0, opacity: 0, width: 0 }}
                  transition={{
                    type: "spring",
                    stiffness: 500,
                    damping: 20,
                  }}
                  className="flex items-center overflow-hidden"
                >
                  <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <motion.path
                      d="M5 10.5L9 14.5L15 7.5"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      initial={{ pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ duration: 0.25 }}
                    />
                  </svg>
                </motion.span>
              )}
            </AnimatePresence>
          </motion.button>
        );
      })}
    </div>
  );
}

export { SelectorChips };
