export function formatDecimal(value: string | null | undefined): string {
  return value ?? "—";
}

export function formatPercentRatio(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const [whole = "0", fraction = ""] = value.split(".");
  const negative = whole.startsWith("-");
  const absoluteWhole = negative ? whole.slice(1) : whole;
  const digits = `${absoluteWhole}${fraction}` || "0";
  const decimalIndex = absoluteWhole.length + 2;
  // Shift the decimal point two places right without converting the API
  // Decimal string to a floating-point number at the display boundary.
  const padded = digits.padEnd(decimalIndex, "0");
  const percent = `${padded.slice(0, decimalIndex)}.${padded.slice(decimalIndex)}`
    .replace(/\.$/, "")
    .replace(/\.0+$/, "")
    .replace(/^0+(?=\d)/, "");
  return `${negative ? "-" : ""}${percent}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }).format(date) + " UTC";
}
