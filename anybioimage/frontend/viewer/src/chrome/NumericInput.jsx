// anybioimage/frontend/viewer/src/chrome/NumericInput.jsx
//
// Numeric entry paired with a slider.
//
// Props:
//   value     — canonical value from the parent (single source of truth).
//   min, max  — inclusive bounds; commits clamp.
//   format    — (n) => string to render the displayed value when not editing.
//   onCommit  — (n) => void, called with the parsed + clamped number.
//   plus the usual disabled / style / className / aria-label passthroughs.
//
// Behaviour:
//   - Not focused: shows format(value).
//   - Focused: tracks user's raw text. Enter or blur commits.
//   - Escape reverts and blurs.
//   - Invalid parse → revert; no onCommit.
//   - External value updates only sync to the input when the user isn't editing.
import React, { useEffect, useRef, useState } from 'react';

function parseNumber(raw) {
  const s = String(raw).trim();
  if (s === '') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export function NumericInput({
  value, min, max, step = 'any',
  format = (n) => String(n),
  onCommit, disabled, style, className,
  ...rest
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => format(value));
  const inputRef = useRef(null);

  useEffect(() => {
    if (!editing) setDraft(format(value));
  }, [value, format, editing]);

  function commit() {
    const n = parseNumber(draft);
    if (n === null) {
      setDraft(format(value));
      return;
    }
    const clamped = Math.max(min, Math.min(max, n));
    onCommit(clamped);
    setDraft(format(clamped));
  }

  function onKeyDown(e) {
    if (e.key === 'Enter') {
      commit();
      inputRef.current?.blur();
    } else if (e.key === 'Escape') {
      setDraft(format(value));
      setEditing(false);
      inputRef.current?.blur();
    }
  }

  return (
    <input
      ref={inputRef}
      type="text"
      inputMode="decimal"
      className={className}
      style={style}
      value={draft}
      disabled={disabled}
      step={step}
      onFocus={() => setEditing(true)}
      onChange={(e) => { setEditing(true); setDraft(e.target.value); }}
      onBlur={() => { commit(); setEditing(false); }}
      onKeyDown={onKeyDown}
      {...rest}
    />
  );
}
