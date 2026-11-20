import { useEffect, useMemo, useRef, useState } from 'react';
import { Language, languageLocales } from '../i18n';

function isoDate(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function isoMonth(date: Date): string {
  return isoDate(date).slice(0, 7);
}

export function LocalizedDateInput({
  value,
  max,
  onChange,
  language,
  label,
  type = 'date',
}: {
  value: string;
  max: string;
  onChange: (value: string) => void;
  language: Language;
  label: string;
  type?: 'date' | 'month';
}) {
  const selected =
    type === 'month'
      ? new Date(Number(value.slice(0, 4)), Number(value.slice(5, 7)) - 1, 1)
      : new Date(`${value}T12:00:00`);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => new Date(selected));
  const root = useRef<HTMLDivElement>(null);
  const locale = languageLocales[language];
  const normalizedDisplay = new Intl.DateTimeFormat(locale, {
    day: type === 'date' ? 'numeric' : undefined,
    month: 'long',
    year: 'numeric',
  }).format(selected);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', escape);
    };
  }, []);

  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, month) =>
        new Intl.DateTimeFormat(locale, { month: 'long' }).format(
          new Date(view.getFullYear(), month, 1),
        ),
      ),
    [locale, view],
  );
  const weekdays = useMemo(
    () =>
      Array.from({ length: 7 }, (_, day) =>
        new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(
          new Date(2024, 0, 1 + day),
        ),
      ),
    [locale],
  );

  const maximum = type === 'month' ? new Date(`${max}-01T12:00:00`) : new Date(`${max}T12:00:00`);
  const firstDay = new Date(view.getFullYear(), view.getMonth(), 1);
  const mondayOffset = (firstDay.getDay() + 6) % 7;
  const days = Array.from({ length: 42 }, (_, index) => {
    return new Date(view.getFullYear(), view.getMonth(), 1 - mondayOffset + index);
  });
  const sameMonth = (date: Date) => date.getMonth() === view.getMonth();
  const disabled = (date: Date) => date > maximum;
  const selectedDate = isoDate(selected);

  const select = (next: Date) => {
    onChange(type === 'month' ? isoMonth(next) : isoDate(next));
    setOpen(false);
  };

  return (
    <div className="localized-date" ref={root}>
      <span>{label}</span>
      <button
        className="localized-date-display"
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setView(new Date(selected));
          setOpen((current) => !current);
        }}
      >
        <span>{normalizedDisplay}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="date-popover" role="dialog" aria-label={label}>
          <div className="date-nav">
            <button
              type="button"
              aria-label="Previous"
              onClick={() =>
                setView(
                  new Date(
                    view.getFullYear() - (type === 'month' ? 1 : 0),
                    view.getMonth() - (type === 'date' ? 1 : 0),
                    1,
                  ),
                )
              }
            >
              ‹
            </button>
            <strong>
              {new Intl.DateTimeFormat(locale, {
                month: type === 'date' ? 'long' : undefined,
                year: 'numeric',
              }).format(view)}
            </strong>
            <button
              type="button"
              aria-label="Next"
              disabled={
                type === 'month'
                  ? view.getFullYear() >= maximum.getFullYear()
                  : new Date(view.getFullYear(), view.getMonth() + 1, 1) > maximum
              }
              onClick={() =>
                setView(
                  new Date(
                    view.getFullYear() + (type === 'month' ? 1 : 0),
                    view.getMonth() + (type === 'date' ? 1 : 0),
                    1,
                  ),
                )
              }
            >
              ›
            </button>
          </div>

          {type === 'month' ? (
            <div className="month-grid">
              {months.map((month, index) => {
                const candidate = new Date(view.getFullYear(), index, 1);
                const selectedMonth =
                  selected.getFullYear() === candidate.getFullYear() &&
                  selected.getMonth() === candidate.getMonth();
                return (
                  <button
                    className={selectedMonth ? 'selected' : ''}
                    type="button"
                    key={month}
                    disabled={candidate > maximum}
                    onClick={() => select(candidate)}
                  >
                    {month}
                  </button>
                );
              })}
            </div>
          ) : (
            <>
              <div className="weekday-grid" aria-hidden="true">
                {weekdays.map((weekday) => (
                  <span key={weekday}>{weekday.slice(0, 2)}</span>
                ))}
              </div>
              <div className="day-grid">
                {days.map((date) => {
                  const currentDate = isoDate(date);
                  return (
                    <button
                      className={[
                        !sameMonth(date) ? 'outside' : '',
                        currentDate === selectedDate ? 'selected' : '',
                      ].join(' ')}
                      type="button"
                      key={currentDate}
                      disabled={disabled(date)}
                      onClick={() => select(date)}
                    >
                      {date.getDate()}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
