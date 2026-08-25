import type { ButtonHTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({
  className = '',
  variant,
  type = 'submit',
  ...props
}: ButtonProps) {
  const resolvedVariant =
    variant ?? (type === 'button' ? 'secondary' : 'primary');
  return (
    <button
      type={type}
      className={`action-${resolvedVariant} ${className}`}
      {...props}
    />
  );
}
