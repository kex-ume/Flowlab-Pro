# FlowLab Pro Development Philosophy

## Vision

FlowLab Pro is not a CRUD application. It is a professional desktop platform
for managing an ISO/IEC 17025 accredited calibration laboratory.

The software should feel like an engineering application rather than a typical
business application. Every design decision must reflect precision,
professionalism, trust, simplicity, and efficiency.

The target users are laboratory engineers, calibration technicians, quality
managers, and laboratory administrators.

## Design Philosophy

The interface communicates **professional laboratory software**, not a generic
business dashboard. It should resemble software from Keysight, Fluke, Emerson,
Yokogawa, NI, Siemens, and ABB rather than consumer or collaboration apps.

## UI Principles

### Minimal

Show only what matters. Avoid visual clutter; every widget must have a purpose.

### Information hierarchy

Present primary information first and secondary information smaller. Avoid
multiple competing focal points.

### Consistency

Every page uses the same spacing, typography, cards, buttons, colours, icons,
and margins. No page should feel like it belongs to another application.

### Navigation

Navigation should be effortless. Users should never need to wonder where a
feature is located.

### White space

White space is intentional. Do not fill empty areas unnecessarily.

### Colour philosophy

Colours communicate status, never decoration:

- Blue: information
- Green: ready or calibrated
- Amber: warning
- Red: overdue or action required
- Grey: inactive

## Dashboard Philosophy

The dashboard is neither a report nor a data dump. It answers only these
questions:

1. What requires my attention?
2. Is the laboratory ready?
3. What is happening today?
4. What should I do next?

Everything else belongs in its module.

## Shell Philosophy

The sidebar is permanent, stable, predictable, and professional. Avoid moving
widgets, collapsing cards, and unnecessary animations.

The top bar is a workspace containing only search, notifications, the current
user, database status, and the current page.

## Performance Philosophy

The application must feel fast and immediate. Avoid unnecessary repaints,
database calls, and animations.

## Architecture Philosophy

Never rewrite working code. Improve incrementally; preserve the existing
architecture, modules, database, authentication, and permissions. Refactor
instead of replacing.

## Coding Philosophy

Code must be modular, readable, maintainable, production quality, PEP 8
compliant, and well documented. Avoid duplicated logic, giant classes, magic
numbers, hard-coded colours or fonts, and unnecessary inheritance.

## Responsiveness and Themes

The application must work on 13-, 14-, 15-, and 16-inch displays as well as
external monitors. Layouts must resize gracefully; avoid fixed widths unless
they are essential.

Light theme is the default. Dark theme remains fully supported. Theme changes
must flow through `ThemeManager`, without page-specific code changes.

## Development Strategy

Never redesign the entire application. Complete modules in this order:

1. Shell
2. Dashboard
3. Projects
4. Laboratory
5. Tools
6. Documents
7. Reports
8. Settings

Finish one module before starting the next.

## Golden Rule

Every improvement must answer this question:

> Does this make FlowLab Pro feel more like professional engineering software?

If the answer is no, do not implement it.
