# -*- coding: utf-8 -*-
"""Read one selected schedule and open the existing browser calculator."""
from __future__ import unicode_literals
from pyrevit import forms, revit
from handoff import encode_url
from revit_adapter import available_schedules, read_schedule, element_id_value
from browser_launcher import open_default_browser

__title__ = 'Plumbing\nCalculation'
__author__ = 'YSU'


def main():
    doc = revit.doc
    if doc is None or doc.IsFamilyDocument:
        forms.alert('Open a Revit project before selecting a schedule.', title='Plumbing Calculation')
        return
    try:
        schedules = available_schedules(doc)
    except Exception:
        forms.alert('Could not list schedules in this project.', title='Plumbing Calculation')
        return
    if not schedules:
        forms.alert('No selectable schedules were found.', title='Plumbing Calculation')
        return
    choices = {'{0} [ID {1}]'.format(s.Name, element_id_value(s.Id)): s for s in schedules}
    selected = forms.SelectFromList.show(sorted(choices, key=lambda name: name.lower()),
                                         title='Select Revit Schedule', multiselect=False,
                                         button_name='Open in Plumbing Tool')
    if not selected:
        return
    try:
        url = encode_url(read_schedule(doc, choices[selected]))
    except ValueError as error:
        forms.alert(str(error), title='Plumbing Calculation')
        return
    except Exception:
        forms.alert('Could not reliably read this schedule. No model changes were made. Use the Web PDF/Image workflow.', title='Plumbing Calculation')
        return
    try:
        open_default_browser(url)
    except Exception:
        forms.alert('Could not open the default browser. Check the Windows default HTTPS browser setting and try again.', title='Plumbing Calculation')


main()
