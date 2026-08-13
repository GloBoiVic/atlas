import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Home from '../app/page';

describe('home page', () => {
  it('renders the foundation page', () => {
    render(<Home />);
    expect(
      screen.getByRole('heading', { name: 'Atlas', level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('The project foundation is running.'),
    ).toBeVisible();
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });
});
