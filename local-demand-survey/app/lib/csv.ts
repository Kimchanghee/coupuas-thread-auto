export function neutralizeSpreadsheetFormula(value: string): string {
  return /^[=+\-@\t\r\n]/u.test(value) ? `'${value}` : value;
}

export function csvEscape(value: unknown): string {
  const text = Array.isArray(value) ? value.join(" | ") : String(value ?? "");
  return `"${neutralizeSpreadsheetFormula(text).replaceAll('"', '""')}"`;
}
