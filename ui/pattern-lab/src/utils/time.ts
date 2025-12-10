const tehranFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Tehran",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export const formatTehran = (iso?: string | null) => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return tehranFormatter.format(d).replace(",", "");
};

export const formatTehranWithLabel = (iso?: string | null) => {
  const base = formatTehran(iso);
  if (base === "-") return base;
  return `${base} (Tehran)`;
};
