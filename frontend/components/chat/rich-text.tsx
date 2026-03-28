"use client";

import { Fragment, type ReactNode } from "react";

const RUNTIME_WARNING_PREFIX_RE = /^(?:MCP issues detected\. Run \/mcp list for status\.\s*)+/i;
const INLINE_TOKEN_RE = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;

export function sanitizeAgentText(text?: string | null): string {
  return String(text ?? "").replace(RUNTIME_WARNING_PREFIX_RE, "").trim();
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(INLINE_TOKEN_RE)) {
    const token = match[0];
    const index = match.index ?? 0;

    if (index > lastIndex) {
      nodes.push(text.slice(lastIndex, index));
    }

    if (token.startsWith("`") && token.endsWith("`")) {
      nodes.push(
        <code
          key={`${index}-code`}
          className="rounded bg-[#eef2ff] px-1.5 py-0.5 font-mono text-[0.92em] text-[#273142] dark:bg-slate-900 dark:text-slate-200"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("**") && token.endsWith("**")) {
      nodes.push(
        <strong key={`${index}-strong`} className="font-semibold text-[#111111] dark:text-slate-100">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("[") && token.includes("](") && token.endsWith(")")) {
      const label = token.slice(1, token.indexOf("]("));
      nodes.push(
        <span key={`${index}-link`} className="font-medium text-[#111111] dark:text-slate-100">
          {label}
        </span>
      );
    } else {
      nodes.push(token);
    }

    lastIndex = index + token.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function renderList(lines: string[], ordered: boolean, key: string) {
  const Tag = ordered ? "ol" : "ul";
  const className = ordered ? "list-decimal pl-5" : "list-disc pl-5";

  return (
    <Tag key={key} className={`${className} space-y-2`}>
      {lines.map((line, index) => {
        const content = ordered
          ? line.replace(/^\d+\.\s+/, "")
          : line.replace(/^[-*]\s+/, "");
        return <li key={`${key}-${index}`}>{renderInline(content)}</li>;
      })}
    </Tag>
  );
}

function renderBlock(block: string, index: number) {
  const lines = block
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return null;
  }

  if (lines.length === 1 && /^#{1,6}\s+/.test(lines[0])) {
    const heading = lines[0].replace(/^#{1,6}\s+/, "");
    return (
      <h3 key={`block-${index}`} className="text-[16px] font-semibold tracking-[-0.02em] text-[#111111] dark:text-slate-100">
        {renderInline(heading)}
      </h3>
    );
  }

  if (lines.every((line) => /^[-*]\s+/.test(line))) {
    return renderList(lines, false, `block-${index}`);
  }

  if (lines.every((line) => /^\d+\.\s+/.test(line))) {
    return renderList(lines, true, `block-${index}`);
  }

  return (
    <p key={`block-${index}`} className="whitespace-pre-line">
      {lines.map((line, lineIndex) => (
        <Fragment key={`block-${index}-line-${lineIndex}`}>
          {lineIndex > 0 ? "\n" : null}
          {renderInline(line)}
        </Fragment>
      ))}
    </p>
  );
}

interface RichTextProps {
  text?: string | null;
  className?: string;
}

export function RichText({ text, className = "" }: RichTextProps) {
  const normalized = sanitizeAgentText(text);
  if (!normalized) {
    return null;
  }

  const blocks = normalized
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return <div className={`space-y-4 text-[14px] leading-7 text-[#273142] dark:text-slate-300 ${className}`}>{blocks.map(renderBlock)}</div>;
}
