// anybioimage/frontend/viewer/src/chrome/icons.js
//
// Inline SVG icons for the toolbar + chrome. Heroicons-style stroke, 24×24
// viewBox, currentColor-driven so hover/active/disabled state on the parent
// button just works.
//
// Tools that aren't implemented yet (line, areaMeasure, lineProfile) are not
// listed — adding them here is the trigger for adding them to the toolbar.
import React from 'react';

function Icon({ children, fill = 'none' }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg"
         viewBox="0 0 24 24"
         fill={fill}
         stroke="currentColor"
         strokeWidth={2}
         strokeLinecap="round"
         strokeLinejoin="round"
         aria-hidden="true"
         focusable="false">
      {children}
    </svg>
  );
}

export const ICONS = {
  pan: (
    <Icon>
      <path d="M12 3v18M3 12h18M7 7l5-4 5 4M7 17l5 4 5-4M7 7l-4 5 4 5M17 7l4 5-4 5" />
    </Icon>
  ),
  select: (
    <Icon fill="currentColor">
      <path d="M4 3l16 9-7 2-2 7z" />
    </Icon>
  ),
  rect: (
    <Icon>
      <rect x="4" y="4" width="16" height="16" rx="1" />
    </Icon>
  ),
  polygon: (
    <Icon>
      <path d="M12 3l9 6-3 11H6L3 9z" />
    </Icon>
  ),
  point: (
    <Icon>
      <circle cx="12" cy="12" r="3" fill="currentColor" />
      <circle cx="12" cy="12" r="8" />
    </Icon>
  ),
  reset: (
    <Icon>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </Icon>
  ),
  layers: (
    <Icon>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
      <path d="M3 18l9 5 9-5" />
    </Icon>
  ),
  play: (
    <Icon fill="currentColor">
      <path d="M7 4l13 8-13 8z" />
    </Icon>
  ),
  pause: (
    <Icon fill="currentColor">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </Icon>
  ),
};

// Aria labels keyed by tool mode id.
export const TOOL_ARIA = {
  pan: 'Pan',
  select: 'Select',
  rect: 'Rectangle',
  polygon: 'Polygon',
  point: 'Point',
};

// Keyboard shortcut letter keyed by tool mode id; appended to button title as "(X)".
export const TOOL_SHORTCUT = {
  pan: 'P',
  select: 'V',
  rect: 'R',
  polygon: 'G',
  point: 'O',
};
