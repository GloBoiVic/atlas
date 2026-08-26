import * as React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const weekdays = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

export function Calendar({
  selected,
  onSelect,
}: {
  selected?: Date;
  onSelect: (date: Date) => void;
}) {
  const [month, setMonth] = React.useState(() => {
    if (selected) return selected;
    const now = new Date();
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  });
  const year = month.getUTCFullYear();
  const monthIndex = month.getUTCMonth();
  const firstDay = new Date(Date.UTC(year, monthIndex, 1)).getUTCDay();
  const days = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate();
  const selectedKey = selected ? selected.toISOString().slice(0, 10) : '';
  const cells = Array.from({ length: firstDay + days }, (_, index) =>
    index < firstDay ? null : index - firstDay + 1,
  );
  return (
    <div role="application" aria-label="Choose UTC date" className="w-64">
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          aria-label="Previous month"
          className="rounded p-1 hover:bg-atlas-surface-hover"
          onClick={() => setMonth(new Date(Date.UTC(year, monthIndex - 1, 1)))}
        >
          <ChevronLeft className="size-4" aria-hidden />
        </button>
        <span className="text-sm font-medium">
          {new Intl.DateTimeFormat('en-US', {
            timeZone: 'UTC',
            month: 'long',
            year: 'numeric',
          }).format(month)}
        </span>
        <button
          type="button"
          aria-label="Next month"
          className="rounded p-1 hover:bg-atlas-surface-hover"
          onClick={() => setMonth(new Date(Date.UTC(year, monthIndex + 1, 1)))}
        >
          <ChevronRight className="size-4" aria-hidden />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-atlas-foreground-muted">
        {weekdays.map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1 text-center text-sm">
        {cells.map((day, index) => {
          if (!day) return <span key={`empty-${index}`} />;
          const date = new Date(Date.UTC(year, monthIndex, day));
          const key = date.toISOString().slice(0, 10);
          return (
            <button
              type="button"
              key={key}
              aria-label={key}
              aria-pressed={key === selectedKey}
              className={`rounded p-1.5 hover:bg-atlas-primary-muted ${key === selectedKey ? 'bg-atlas-primary text-atlas-primary-foreground hover:bg-atlas-primary-hover' : ''}`}
              onClick={() => onSelect(date)}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}
