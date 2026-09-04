# YSU pyRevit Tools

Downloadable pyRevit extensions for Revit, published as GitHub Releases and
linked from the [YSU Tools](https://tools.ycsu.cc/) site.

## Tools

- [Revision Cleanup](tools/revision-cleanup/) — purges revision clouds,
  tags, and revision definitions from the active project, keeping a single
  blank placeholder revision. Landing page:
  https://tools.ycsu.cc/pyrevit/revisioncleanup/
- [Pick Face Material](tools/pick-face-material/) — picks a model face,
  copies its actual (paint-aware) material name to the clipboard, and
  opens Revit's Materials browser. Landing page:
  https://tools.ycsu.cc/pyrevit/pickfacematerial/
- [Sheet / View Tools](tools/sheet-view-tools/) — deletes the sheets
  selected in the Project Browser plus any views placed only on those
  sheets, retaining views/legends/schedules shared with other sheets.
  Landing page: https://tools.ycsu.cc/pyrevit/sheetviewtools/

## Structure

```
tools/
  <tool-name>/           source of the packaged pyRevit extension + README
releases/                notes on published releases (assets live on the
                          GitHub Releases page, not committed here)
```

Each tool is released as a standalone `.zip` containing a valid pyRevit
`.extension` folder plus an installation README, attached to a tagged
GitHub Release (e.g. `revisioncleanup-v1.0.0`).
