# Quick UI Reference Guide

## Color Palette

```
🎨 Primary Colors
- Background:     #0A0A0F  (use bg-[#0A0A0F])
- Surface:        #111118  (use bg-[#111118])
- Sidebar:        #0D0D14  (use bg-[#0D0D14])
- Primary/Accent: #6366F1  (use text/bg-indigo-500/600)

📊 Status Colors
- Success:   #10B981  (bg-emerald-500, text-emerald-400)
- Warning:   #F59E0B  (bg-amber-500, text-amber-400)
- Danger:    #EF4444  (bg-red-500, text-red-400)
- Info:      #6366F1  (bg-indigo-500, text-indigo-400)

📝 Text Colors
- Primary:   #F1F5F9  (text-white)
- Secondary: #94A3B8  (text-slate-400)
- Muted:     #475569  (text-slate-600)
```

## Common Components & Their Styling

### Cards
```jsx
<div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6">
  {content}
</div>
```

### Buttons
```jsx
{/* Primary Button */}
<button className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors">
  Action
</button>

{/* Icon Button */}
<button className="p-2.5 rounded-xl hover:bg-white/5 transition-all">
  <Icon size={18} />
</button>
```

### Input Fields
```jsx
<input className="bg-[#1A1A24] border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm placeholder-slate-600 focus:border-indigo-500 focus:outline-none transition-colors" />

<textarea className="bg-[#1A1A24] border border-white/10 text-slate-200 rounded-lg px-4 py-3 text-sm placeholder-slate-600 focus:border-indigo-500 focus:outline-none resize-none w-full transition-colors" />
```

### Status Badges
```jsx
<span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
  PASS
</span>
```

### Section Headers
```jsx
<h3 className="text-sm font-semibold text-white mb-5 flex items-center gap-2">
  <IconComponent size={16} className="text-indigo-400" />
  Section Title
</h3>

{/* Or with labels */}
<label className="section-title">Label Text</label>
```

### Dividers
```jsx
<div className="border-t border-white/5 mx-3 my-2"></div>
```

## Layout Patterns

### Two-Column Layout
```jsx
<div className="grid grid-cols-2 gap-6">
  <div>{/* Left column */}</div>
  <div>{/* Right column */}</div>
</div>
```

### Three-Column Grid
```jsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* KPI Cards, etc */}
</div>
```

### Chat Bubble (User)
```jsx
<div className="flex justify-end">
  <div className="bg-indigo-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm max-w-[80%]">
    User message
  </div>
</div>
```

### Chat Bubble (AI)
```jsx
<div className="flex justify-start">
  <div className="bg-[#1A1A24] border border-white/5 text-slate-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm max-w-[85%]">
    AI message
  </div>
</div>
```

### Hover Effects
```jsx
{/* Card hover */}
<div className="hover:border-white/10 transition-all hover:bg-white/[0.02]">

{/* Text hover */}
<a className="text-indigo-400 hover:text-indigo-300">Link</a>

{/* Button hover */}
<button className="hover:bg-indigo-500 transition-colors">Button</button>
```

## Typography Hierarchy

```
Page Title:        text-2xl font-bold text-white
Card Title:        text-sm font-semibold text-white
Section Label:     text-xs font-semibold text-slate-500 uppercase tracking-wider
Body Text:         text-sm text-slate-300
Small Text:        text-xs text-slate-600
Muted Text:        text-xs text-slate-600
```

## Spacing Guide

```
Gaps:       gap-2 (8px), gap-3 (12px), gap-4 (16px), gap-6 (24px)
Padding:    p-2 (8px), p-3 (12px), p-4 (16px), p-5 (20px), p-6 (24px)
Margin:     m-1, m-2, m-3, m-4
Mb/Mt:      mb-2, mb-3, mb-4, mb-6 (bottom), mt-1, mt-2
```

## Border Radius Guide

```
Buttons/Inputs:    rounded-lg   (12px)
Most containers:   rounded-xl   (16px)
Major cards:       rounded-2xl  (20px)
Dots/Badges:       rounded-full (100%)
```

## Animation/Transition Classes

```
Smooth transition:     transition-all duration-150
Color transition:      transition-colors
Specific property:     transition-transform duration-200
Hover scale:          hover:scale-105 transition-transform
Loading spinner:      animate-spin
Pulse animation:      animate-pulse
```

## Border & Shadow Guide

```
Subtle border:       border border-white/[0.06]
Input border:        border border-white/10
Focus border:        focus:border-indigo-500
Card shadow:         shadow-xl shadow-black/20
Hover shadow:        hover:shadow-lg
No shadow:           shadow-none
```

## Utility Classes (from index.css)

```jsx
// Card
<div className="card">...</div>

// Buttons
<button className="btn-primary">Primary</button>
<button className="btn-secondary">Secondary</button>
<button className="btn-icon">Icon</button>

// Input fields
<input className="input-field" />
<textarea className="textarea-field" />

// Section title
<label className="section-title">Label</label>

// Badges
<span className="badge badge-success">Success</span>
<span className="badge badge-warning">Warning</span>
<span className="badge badge-danger">Danger</span>
<span className="badge badge-info">Info</span>

// Text utilities
<p className="text-primary">Primary text</p>
<p className="text-secondary">Secondary text</p>
<p className="text-muted">Muted text</p>

// Transitions
<div className="transition-smooth">...</div>
```

## Color Replacement Cheat Sheet

| If you see... | Replace with... |
|---|---|
| bg-gray-800 | bg-[#111118] |
| bg-gray-900 | bg-[#0A0A0F] |
| border-gray-700 | border-white/[0.06] |
| border-gray-600 | border-white/10 |
| text-gray-300 | text-slate-300 |
| text-gray-400 | text-slate-600 |
| text-gray-500 | text-slate-600 |
| bg-blue-600 | bg-indigo-600 |
| bg-blue-700 | bg-indigo-700 |
| text-blue-400 | text-indigo-400 |
| rounded-lg | rounded-xl |

## Common Patterns

### Loading State
```jsx
<div className="flex items-center gap-3">
  <div className="w-4 h-4 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin"></div>
  <span className="text-slate-400 text-sm">Loading...</span>
</div>
```

### Empty State
```jsx
<div className="flex items-center justify-center h-full text-center">
  <div>
    <Icon size={48} className="mx-auto mb-3 text-slate-700" />
    <p className="text-slate-600 text-sm">No data available</p>
  </div>
</div>
```

### KPI Card
```jsx
<div className="bg-[#111118] border border-white/[0.06] rounded-2xl p-5 hover:border-white/10 transition-all">
  <div className="inline-flex p-2 rounded-xl bg-indigo-500/10">
    <Icon size={20} className="text-indigo-400" />
  </div>
  <div className="mt-3">
    <div className="text-3xl font-bold text-white">42</div>
    <div className="text-slate-400 text-sm font-medium mt-1">Label</div>
  </div>
</div>
```

### List Item with Hover
```jsx
<div className="flex items-center gap-2 p-2.5 rounded-lg hover:bg-white/5 transition-colors group cursor-pointer">
  <Icon size={16} className="text-slate-500 flex-shrink-0 group-hover:text-indigo-400" />
  <span className="flex-1 text-slate-300 text-sm">Item</span>
  <Badge status="PASS" className="flex-shrink-0" />
</div>
```

---

## Key Takeaways

✅ Always use `#0A0A0F`, `#111118`, and `#6366F1` instead of gray/blue tones  
✅ Use `rounded-2xl` on major containers, `rounded-xl` on inputs/buttons  
✅ Add `transition-all duration-150` to all interactive elements  
✅ Use `border-white/[0.06]` for subtle card borders  
✅ Add hover states with `hover:` classes  
✅ Use `text-slate-*` instead of `text-gray-*`  
✅ Replace all `bg-blue-*` with `bg-indigo-*`  
✅ Use proper spacing (p-5, p-6, gap-4, gap-6)  

