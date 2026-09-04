# -*- coding: utf-8 -*-
"""Purge all revision clouds/tags and remove all deletable revisions.

Keeps the first revision in the project as a blank placeholder because Revit
requires at least one revision to remain in the document.
"""

from pyrevit import revit, DB, forms, script

__title__ = "Purge All\nRevisions"
__author__ = "YSU"
__doc__ = (
    "Deletes all Revision Cloud Tags and Revision Clouds across the active "
    "project, removes all revisions except the first one, and clears the "
    "remaining revision so it can act as a blank placeholder."
)

logger = script.get_logger()
doc = revit.doc


def _collect_category(bic):
    """Return non-type elements in a built-in category as a Python list."""
    return list(
        DB.FilteredElementCollector(doc)
        .OfCategory(bic)
        .WhereElementIsNotElementType()
    )


def _revision_ids():
    return list(DB.Revision.GetAllRevisionIds(doc))


def _safe_clear_revision(revision):
    """Clear user-editable fields on the retained placeholder revision."""
    revision.Issued = False

    # These properties are normally writable, but keep the cleanup resilient
    # across Revit versions / project states by clearing each independently.
    for prop_name in ("Description", "RevisionDate", "IssuedBy", "IssuedTo"):
        try:
            setattr(revision, prop_name, "")
        except Exception as ex:
            logger.warning("Could not clear Revision.%s: %s", prop_name, ex)

    # Make the placeholder behave normally if it is reused later.
    try:
        revision.Visibility = DB.RevisionVisibility.CloudAndTagVisible
    except Exception as ex:
        logger.warning("Could not reset revision visibility: %s", ex)


def _delete_elements(elements, label, failures):
    """Delete elements individually so one bad element does not stop the run."""
    deleted = 0
    for element in elements:
        try:
            if element is not None and element.IsValidObject:
                doc.Delete(element.Id)
                deleted += 1
        except Exception as ex:
            failures.append((label, element.Id.IntegerValue, str(ex)))
            logger.error("Could not delete %s %s: %s", label, element.Id, ex)
    return deleted


def main():
    if doc is None:
        forms.alert(
            "Open a Revit project before running this tool.",
            title="Purge All Revisions",
            warn_icon=True,
        )
        return

    if doc.IsReadOnly:
        forms.alert(
            "The active document is read-only. Revisions cannot be purged.",
            title="Purge All Revisions",
            warn_icon=True,
        )
        return

    revisions = _revision_ids()

    if not revisions:
        forms.alert(
            "No revisions were found in this project.",
            title="Purge All Revisions",
        )
        return

    revision_clouds = _collect_category(DB.BuiltInCategory.OST_RevisionClouds)

    # Revision cloud tags are collected separately so the tool can report what
    # it found and explicitly remove tags before their host clouds.
    try:
        revision_tags = _collect_category(DB.BuiltInCategory.OST_RevisionCloudTags)
    except Exception as ex:
        revision_tags = []
        logger.warning("Could not collect Revision Cloud Tags: %s", ex)

    delete_revision_count = max(0, len(revisions) - 1)

    message = (
        "This will permanently purge revision graphics from the ENTIRE project.\n\n"
        "Found:\n"
        "  Revision Cloud Tags: {0}\n"
        "  Revision Clouds: {1}\n"
        "  Revision Definitions: {2}\n\n"
        "The tool will:\n"
        "  1. Delete all Revision Cloud Tags\n"
        "  2. Delete all Revision Clouds\n"
        "  3. Delete {3} Revision Definition(s)\n"
        "  4. Keep the first Revision as a blank placeholder\n\n"
        "This action can be undone with Revit Undo immediately after running."
    ).format(
        len(revision_tags),
        len(revision_clouds),
        len(revisions),
        delete_revision_count,
    )

    confirmed = forms.alert(
        message,
        title="Purge All Revisions",
        yes=True,
        no=True,
        warn_icon=True,
    )

    if not confirmed:
        return

    failures = []
    deleted_tags = 0
    deleted_clouds = 0
    deleted_revisions = 0

    tx = DB.Transaction(doc, "YSU - Purge All Revisions")
    tx.Start()

    try:
        # 1) Tags first
        deleted_tags = _delete_elements(revision_tags, "Revision Cloud Tag", failures)

        # 2) Then revision clouds
        deleted_clouds = _delete_elements(revision_clouds, "Revision Cloud", failures)

        # 3) Keep the FIRST revision in revision sequence as the placeholder.
        keep_id = revisions[0]

        # Unissue all revisions first so deletion is allowed where possible.
        for rev_id in revisions:
            rev = doc.GetElement(rev_id)
            if rev is not None:
                try:
                    rev.Issued = False
                except Exception as ex:
                    failures.append(("Revision (unissue)", rev_id.IntegerValue, str(ex)))
                    logger.error("Could not unissue Revision %s: %s", rev_id, ex)

        # 4) Delete every revision except the retained placeholder.
        for rev_id in revisions[1:]:
            try:
                rev = doc.GetElement(rev_id)
                if rev is not None and rev.IsValidObject:
                    doc.Delete(rev_id)
                    deleted_revisions += 1
            except Exception as ex:
                failures.append(("Revision", rev_id.IntegerValue, str(ex)))
                logger.error("Could not delete Revision %s: %s", rev_id, ex)

        # 5) Clean the retained revision.
        keep_revision = doc.GetElement(keep_id)
        if keep_revision is not None:
            _safe_clear_revision(keep_revision)

        tx.Commit()

    except Exception:
        if tx.HasStarted():
            tx.RollBack()
        logger.exception("Unexpected error while purging revisions.")
        forms.alert(
            "The purge failed and the transaction was rolled back.\n\n"
            "Open the pyRevit output window for error details.",
            title="Purge All Revisions",
            warn_icon=True,
        )
        return

    # Summary
    if failures:
        summary = (
            "Purge completed with some items that could not be removed.\n\n"
            "Deleted:\n"
            "  Revision Cloud Tags: {0}\n"
            "  Revision Clouds: {1}\n"
            "  Revision Definitions: {2}\n\n"
            "Failed items: {3}\n\n"
            "Common causes are element ownership/worksharing or protected project state.\n"
            "See the pyRevit output window for details."
        ).format(deleted_tags, deleted_clouds, deleted_revisions, len(failures))

        forms.alert(
            summary,
            title="Purge All Revisions",
            warn_icon=True,
        )

        print("PURGE ALL REVISIONS - FAILED ITEMS")
        print("----------------------------------")
        for label, element_id, error_text in failures:
            print("{0} | ElementId {1} | {2}".format(label, element_id, error_text))
    else:
        forms.alert(
            (
                "Revision cleanup complete.\n\n"
                "Deleted:\n"
                "  Revision Cloud Tags: {0}\n"
                "  Revision Clouds: {1}\n"
                "  Revision Definitions: {2}\n\n"
                "1 blank Revision remains as the project placeholder."
            ).format(deleted_tags, deleted_clouds, deleted_revisions),
            title="Purge All Revisions",
        )


if __name__ == "__main__":
    main()
