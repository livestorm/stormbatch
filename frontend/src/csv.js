// CSV files the user downloads: templates and failed rows to fix and re-upload.

// Spreadsheet apps run cells starting with these characters as formulas, and
// exported values can come from other people (registrants of a session).
const FORMULA_START = /^[=+\-@\t\r]/;
// Phone numbers and amounts start with + or - legitimately; keep them as typed.
const PLAIN_NUMBER = /^[+-]?[\d\s().,-]+$/;

function safeCell(value) {
  const text = String(value ?? "");
  return FORMULA_START.test(text) && !PLAIN_NUMBER.test(text) ? `'${text}` : text;
}

function quoteCell(text) {
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(headers, rows) {
  return [headers, ...rows]
    .map((row) => row.map((cell) => quoteCell(safeCell(cell))).join(","))
    .join("\r\n") + "\r\n";
}

export function downloadCsv(filename, headers, rows) {
  // The byte-order mark makes Excel read accented characters correctly.
  const blob = new Blob(["﻿", toCsv(headers, rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function fileSlug(text) {
  return (
    String(text)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "session"
  );
}
