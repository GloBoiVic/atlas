# Atlas Styling Convention

## Rule: Use Tailwind Utility Classes with Atlas Prefix

Atlas tokens generate Tailwind utilities with the `atlas-` prefix.

### Colors

```tsx
// Backgrounds
<div className="bg-atlas-surface">
<div className="bg-atlas-bg-elevated">
<div className="bg-atlas-accent">

// Text
<span className="text-atlas-fg">
<span className="text-atlas-fg-secondary">
<span className="text-atlas-positive">
<span className="text-atlas-negative">

// Borders
<div className="border border-atlas-border">
<div className="border-atlas-border-strong">

// Status with dim backgrounds
<span className="bg-atlas-positive-dim text-atlas-positive">
<span className="bg-atlas-negative-dim text-atlas-negative">
```

### Spacing

```tsx
<div className="p-atlas-4">        {/* 16px */}
<div className="m-atlas-2">        {/* 8px */}
<div className="gap-atlas-6">      {/* 24px */}
<div className="px-atlas-8">       {/* 32px horizontal */}
```

### Typography

```tsx
<span className="font-atlas-mono">           {/* JetBrains Mono */}
<span className="font-atlas-sans">           {/* Inter */}
<span className="text-atlas-lg">             {/* 15px */}
<span className="font-fw-atlas-semibold">    {/* 600 */}
<span className="tracking-atlas-wide">       {/* 0.04em */}
```

### Radius

```tsx
<div className="rounded-atlas">      {/* 6px */}
<div className="rounded-atlas-md">   {/* 8px */}
<div className="rounded-atlas-pill"> {/* 100px */}
```

### Motion

```tsx
<div className="transition-all duration-atlas-base ease-atlas-out">
```

### Shadcn/ui Components

Shadcn/ui components work automatically via the bridge layer.
Use standard Shadcn classes (`bg-primary`, `text-muted-foreground`).

### P&L Example

```tsx
<span className={`
  font-atlas-mono 
  ${pnl >= 0 ? 'text-atlas-positive' : 'text-atlas-negative'}
`}>
  {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
</span>
```

### Status Badge Example

```tsx
<span className="
  bg-atlas-positive-dim 
  text-atlas-positive 
  rounded-atlas-pill 
  px-atlas-3 
  py-atlas-1 
  text-atlas-xs
">
  Running
</span>
```

### Token Reference

| Category | Prefix | Example Utilities |
|----------|--------|-------------------|
| Colors | `atlas-*` | `bg-atlas-*`, `text-atlas-*`, `border-atlas-*` |
| Spacing | `atlas-*` | `p-atlas-*`, `m-atlas-*`, `gap-atlas-*` |
| Typography | `atlas-*` | `font-atlas-*`, `text-atlas-*` |
| Radius | `atlas-*` | `rounded-atlas-*` |
| Motion | `atlas-*` | `duration-atlas-*`, `ease-atlas-*` |
