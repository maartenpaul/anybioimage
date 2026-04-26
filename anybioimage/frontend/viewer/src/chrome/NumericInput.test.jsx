/** @vitest-environment jsdom */
// anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx
import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, fireEvent, cleanup } from '@testing-library/react';
import { NumericInput } from './NumericInput.jsx';

const baseProps = {
  value: 0.5, min: 0, max: 1, step: 0.01,
  format: (n) => n.toFixed(2),
};

afterEach(cleanup);

describe('NumericInput', () => {
  it('renders the passed-in value formatted', () => {
    const { container } = render(<NumericInput {...baseProps} onCommit={() => {}} />);
    expect(container.querySelector('input').value).toBe('0.50');
  });

  it('commits a valid value on Enter', () => {
    const onCommit = vi.fn();
    const { container } = render(<NumericInput {...baseProps} onCommit={onCommit} />);
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '0.75' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenCalledWith(0.75);
  });

  it('commits a valid value on blur', () => {
    const onCommit = vi.fn();
    const { container } = render(<NumericInput {...baseProps} onCommit={onCommit} />);
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '0.8' } });
    fireEvent.blur(input);
    expect(onCommit).toHaveBeenCalledWith(0.8);
  });

  it('reverts on invalid input', () => {
    const onCommit = vi.fn();
    const { container } = render(<NumericInput {...baseProps} onCommit={onCommit} />);
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.blur(input);
    expect(onCommit).not.toHaveBeenCalled();
    expect(input.value).toBe('0.50');
  });

  it('clamps out-of-range to min/max', () => {
    const onCommit = vi.fn();
    const { container } = render(<NumericInput {...baseProps} onCommit={onCommit} />);
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.blur(input);
    expect(onCommit).toHaveBeenCalledWith(1);
  });

  it('reverts on Escape without committing', () => {
    const onCommit = vi.fn();
    const { container } = render(<NumericInput {...baseProps} onCommit={onCommit} />);
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '0.9' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(onCommit).not.toHaveBeenCalled();
    expect(input.value).toBe('0.50');
  });

  it('reflects prop changes when not editing', () => {
    const { container, rerender } = render(<NumericInput {...baseProps} onCommit={() => {}} />);
    const input = container.querySelector('input');
    expect(input.value).toBe('0.50');
    rerender(<NumericInput {...baseProps} value={0.75} onCommit={() => {}} />);
    expect(input.value).toBe('0.75');
  });
});
