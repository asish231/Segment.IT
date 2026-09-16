import React from 'react';

// Renders any JSON object generically — no hardcoded field names — so it stays correct
// as the extraction schema evolves: objects become key:value grids, arrays of objects
// become tables (columns = the union of keys across rows), arrays of primitives become
// pill lists, and bare primitives become a labeled row.

function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function isEmpty(v: unknown): boolean {
  return v === null || v === undefined || v === '';
}

export const DynamicDataView: React.FC<{ data: Record<string, unknown>; skipKeys?: string[] }> = ({
  data,
  skipKeys = [],
}) => {
  const skip = new Set(['validation', 'classification', 'schema_version', ...skipKeys]);
  const entries = Object.entries(data).filter(([k, v]) => !skip.has(k) && !isEmpty(v));

  if (entries.length === 0) {
    return <p className="text-xs text-[#A89F97] italic">No structured data extracted.</p>;
  }

  return (
    <div className="space-y-5">
      {entries.map(([key, value]) => (
        <DynamicSection key={key} label={humanizeKey(key)} value={value} />
      ))}
    </div>
  );
};

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="text-[11px] font-bold uppercase tracking-wider text-[#A89F97]">{children}</div>
);

const DynamicSection: React.FC<{ label: string; value: unknown }> = ({ label, value }) => {
  if (Array.isArray(value)) {
    const items = value.filter((v) => !isEmpty(v));
    if (items.length === 0) return null;
    if (items.every(isPlainObject)) {
      return <DynamicTable label={label} rows={items as Record<string, unknown>[]} />;
    }
    return (
      <div>
        <SectionLabel>{label}</SectionLabel>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {items.map((v, i) => (
            <span key={i} className="text-xs bg-[#F5F1E9] border border-[#E8E2D9] rounded-full px-2.5 py-1 text-[#2B2320]">
              {String(v)}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value).filter(([, v]) => !isEmpty(v));
    if (entries.length === 0) return null;
    return (
      <div>
        <SectionLabel>{label}</SectionLabel>
        <div className="mt-1.5 grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2.5 p-3 rounded-xl bg-[#FBF9F5] border border-[#E8E2D9]">
          {entries.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <div className="text-[10px] uppercase tracking-wide text-[#A89F97]">{humanizeKey(k)}</div>
              <div className="text-sm text-[#2B2320] font-medium truncate">{String(v)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 border-b border-[#F0ECE6] last:border-0">
      <span className="text-xs text-[#756C65]">{label}</span>
      <span className="text-sm font-medium text-[#2B2320] text-right">{String(value)}</span>
    </div>
  );
};

const DynamicTable: React.FC<{ label: string; rows: Record<string, unknown>[] }> = ({ label, rows }) => {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r)))).filter(
    (c) => c !== 'validation' && !rows.every((r) => isEmpty(r[c]))
  );

  return (
    <div>
      <SectionLabel>
        {label} ({rows.length})
      </SectionLabel>
      <div className="mt-1.5 overflow-x-auto rounded-xl border border-[#E8E2D9]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#FBF9F5]">
              {columns.map((c) => (
                <th key={c} className="text-left font-semibold text-[#5A524C] px-3 py-2 border-b border-[#E8E2D9] whitespace-nowrap">
                  {humanizeKey(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-[#F0ECE6] last:border-0">
                {columns.map((c) => (
                  <td key={c} className="px-3 py-2 text-[#2B2320] whitespace-nowrap">
                    {isEmpty(r[c]) ? <span className="text-[#D5CDC2]">—</span> : String(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
