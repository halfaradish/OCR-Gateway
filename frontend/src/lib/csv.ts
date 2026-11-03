const FORMULA_PREFIX = /^[=+\-@]/;
const NEEDS_QUOTES = /[",\r\n]/;

function escapeCell(value: string): string {
  let cell = value;
  if (FORMULA_PREFIX.test(cell)) {
    cell = `'${cell}`;
  }
  if (NEEDS_QUOTES.test(cell)) {
    cell = `"${cell.replace(/"/g, '""')}"`;
  }
  return cell;
}

/** RFC 4180 with a UTF-8 BOM and CRLF line endings so Excel reads Chinese correctly. */
export function downloadCsv(filename: string, header: string[], rows: string[][]): void {
  const lines = [header, ...rows].map((row) => row.map(escapeCell).join(","));
  const blob = new Blob([`\uFEFF${lines.join("\r\n")}`], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
