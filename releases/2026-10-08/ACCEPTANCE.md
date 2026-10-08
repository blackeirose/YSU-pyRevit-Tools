# pyRevit four-tool publication — 2026-10-08

Scope: Revision Cleanup, Pick Face Material, Delete Sheets + Views, and candidate Create Color Legend. Core revision: 57a69136b7473718dfcf26311ae801f033696f05 (AGENTS1.7 / AI_CORE1.4). YSU Gate Full; source/package preparation and independent review precede Release publication.

## Package result

Three v1.0.1 documentation patches retain executable bytes from the original v1.0.0 Release assets. Bilingual install/update/uninstall instructions now preserve the shared extension and neighboring tools, compare duplicate libraries before replacing, and remove only the target pushbutton. SHA-256 and package size:

| Tool | bytes | SHA-256 |
|---|---:|---|
| Revision Cleanup | 7562 | 48df7d99448e7d41470565aca5a414815d33cccacceba5bcefcf4edbba9f27a0 |
| Pick Face Material | 6779 | 9f4df29a5d10b5300b8536b21d2707d862d6bf654fab764e9dc3d666588ded11 |
| Delete Sheets + Views | 13025 | eb99b3bf73549b66df9eed1db88848691dd70766ff7796ddc1b8355f18ada0bb |

Builder and independent reviewer separately verified CRC, extraction, path safety, manifest completeness and every hash. Original executable/config/icon files are byte-identical (4/4/8 non-README files). Python AST checks passed; they are not native Revit/IronPython acceptance. No new Revit runtime test, compatibility matrix or model modification is claimed. Legacy compatibility ranges remain explicitly unverified per-version declarations. The Sheet/View package contains Delete only, with its required ysu_sheets library.

The three historical tools.ycsu.cc/pyrevit landing pages were independently requested on 2026-10-08 and still returned404. The authorized publication uses fixed-version GitHub Release assets instead; it does not modify the shared router. v1.0.0 Releases/assets remain unchanged.

## Candidate source

Create Color Legend 0.2.0-candidate comes from local branch feature/color-legend-category-filter at43906e98b14c8c34b3e19954d22b3bd5b8214a43. All nine original pushbutton files were independently matched with the configured loaded extension and retained installation receipt. SOURCE_MANIFEST.json records each size/hash. Only this allowlist plus sanitized documentation is imported; excluded Workset ancestry, private journals, full conversations, company view/element identifiers and machine paths are not carried over.

The candidate's own README and bundle disclose pending Revit2026 runtime acceptance. Historical102 simulated tests/compile/WPF26 do not qualify this candidate as a production download. **Formal Color Legend ZIP/Release: HOLD.** See its VALIDATION.md for the minimal remaining native acceptance.

## Publication evidence boundary

At preparation time: local packages/reviewer PASS; GitHub public download and HUB/Tracker/MAIN readbacks PENDING. Following publication, append actual download and content results here. HTTP bytes, browser actual download, native Revit execution and role/UI verification are distinct evidence classes.

## Recovery

Old immutable v1.0.0 packages remain the download fallback. Restore only each tool's old link when needed; do not overwrite or remove Release assets. Source recovery reverts this bounded source/documentation commit, without reverting unrelated changes. Never remove the shared installed extension.

HUB/Tracker/MAIN pre-change records, exact changed-field patches, post-write verification and content recovery reside in the private HUB publication record. Those systems' metadata changes do not require frontend deployment. Their Auth, RLS, schema, write gates, existing media/order and unrelated records are outside scope.
