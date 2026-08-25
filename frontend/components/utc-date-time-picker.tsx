'use client';

import { CalendarDays } from 'lucide-react';
import { useState } from 'react';
import { Calendar } from './ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Select } from './ui/select';
import { formatUtcWallClock, parseUtcInput } from '../lib/time';

const pad = (value: number) => String(value).padStart(2, '0');
const times = Array.from({ length: 96 }, (_, index) => `${pad(Math.floor(index / 4))}:${pad((index % 4) * 15)}`);

export function UtcDateTimePicker({ label, value, onChange, disabled }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [year, month, day, hour, minute] = /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2})$/.exec(value)?.slice(1).map(Number) ?? [];
  const valid = Boolean(parseUtcInput(value));
  const selected = valid ? new Date(Date.UTC(year, month - 1, day)) : undefined;
  const time = valid ? `${pad(hour)}:${pad(minute)}` : '00:00';
  const update = (nextDate: Date | undefined, nextTime = time) => {
    if (!nextDate) return;
    const next = `${nextDate.getUTCFullYear()}-${pad(nextDate.getUTCMonth() + 1)}-${pad(nextDate.getUTCDate())}T${nextTime}`;
    onChange(parseUtcInput(next) ? next : '');
  };
  return (
    <div className="space-y-2 text-sm font-medium">
      <span className="block">{label} (UTC)</span>
      <div className="flex flex-wrap gap-2">
        <Popover>
          <PopoverTrigger onClick={() => setOpen((current) => !current)} aria-label={`${label} date${valid ? `, ${formatUtcWallClock(`${value}:00Z`)}` : ''}`} aria-expanded={open} disabled={disabled} className="form-control inline-flex min-h-10 items-center gap-2 text-left font-normal">
            <CalendarDays className="size-4 text-slate-500" aria-hidden />
            {valid ? `${year}-${pad(month)}-${pad(day)}` : 'Choose date'}
          </PopoverTrigger>
          {open && <PopoverContent><Calendar selected={selected} onSelect={(date) => { update(date); setOpen(false); }} /></PopoverContent>}
        </Popover>
        <Select aria-label={`${label} time in UTC`} disabled={disabled || !valid} value={time} onChange={(event) => update(selected, event.target.value)} className="min-w-28">
          {times.map((option) => <option key={option} value={option}>{option}</option>)}
        </Select>
      </div>
      <p className="text-xs font-normal text-slate-500">UTC wall-clock entry. Display timezone only changes labels.</p>
    </div>
  );
}
