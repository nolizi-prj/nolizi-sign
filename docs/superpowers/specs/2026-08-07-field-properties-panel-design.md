# DocuSign-style field properties panel

Date: 2026-08-07. Driven by user feedback: a small field box crushed its
inline controls (label, font-size input, Required/Optional pill, delete)
into an unreadable jumble; the user asked for a DocuSign-like interface.

## Design

Split display from editing:

- **FieldBox** (shared by the template builder and the send wizard's
  Place-fields step) becomes display-only: colored box, truncated name
  label (label fields show their own text), a `*` marker when required,
  drag/resize, click-to-select (visible outline; Delete/Backspace deletes
  when focused). No interactive controls inside the box.
- **FieldPropertiesPanel** (new, shared): edits the selected field —
  Required switch, font size (6–72, empty = automatic), prefill / label
  text for text/label fields, Delete button. Only properties the backend
  supports; DocuSign's font family/bold/color and pixel-location inputs
  are deliberately out of scope.
- Selection is owned by each parent view: `selectedFieldId`, cleared on
  page change (a selected field on another page would be edited
  invisibly), on delete, and on clicking the page background (field boxes
  stop pointerdown propagation, so only background clicks bubble).
- Placement flow (arm a type, drag to place) is unchanged. The send wizard
  shows the panel in a right column next to the page (hint card when
  nothing is selected); the builder shows it in its existing left column
  under "Add field".

## Testing

`vue-tsc --noEmit` + `npm run build`; CI e2e covers placement and the
`.field-label` visibility assertion. Panel interactions verified manually.
