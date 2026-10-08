# -*- coding: utf-8 -*-
"""Native WPF dialogs for Create Color Legend (IronPython 2.7).

Rows are built in code (no WPF data binding to Python objects), so check state lives in
plain Python objects and survives search filtering. Revit-independent: the same module is
driven outside Revit by tests/ui_harness.py with real WPF and synthetic data.
Applies YSU Small Project UI Standard v1.0 (see DESIGN.md).
"""
import clr
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')
from System.Windows import (WindowStartupLocation, Thickness, GridLength, GridUnitType, Visibility, FontStyles, FontWeights,
                            TextWrapping, VerticalAlignment, SystemParameters)
from System.Windows.Controls import Grid, ColumnDefinition, CheckBox, TextBlock, Border, ListBoxItem
from System.Windows.Documents import Run
from System.Windows.Markup import XamlReader
from System.Windows.Media import SolidColorBrush, Color, ColorConverter
from System.Windows.Input import Key
from System.Windows.Interop import WindowInteropHelper
from System.Windows.Automation import AutomationProperties
from legend_core import CATEGORY_KEYS, CATEGORY_LABELS, MISSING_DESCRIPTION

# YSU Small Project UI Standard v1.0 baseline tokens (recorded in DESIGN.md).
TOKENS = {'canvas': '#F7F6F3', 'surface': '#FFFFFF', 'text': '#202421', 'secondary': '#5C635F',
          'boundary': '#7C847E', 'accent': '#315C4B', 'focus': '#245BDB', 'warning': '#805B16'}
COLUMNS = [36, 56, None, 210, 170, 84]  # check, swatch, Description (*), Name, Category, Material ID

WINDOW_HEAD = (u'<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
               u'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
               u'WindowStartupLocation="CenterScreen" ShowInTaskbar="False" '
               u'FontFamily="Segoe UI, Microsoft JhengHei UI" FontSize="14" '
               u'Foreground="{text}" Background="{canvas}" ').format(**TOKENS)
BUTTON_STYLE = (u'<Window.Resources><Style TargetType="Button"><Setter Property="MinWidth" Value="96"/>'
                u'<Setter Property="MinHeight" Value="32"/><Setter Property="Padding" Value="12,4"/>'
                u'<Setter Property="Margin" Value="8,0,0,0"/></Style></Window.Resources>')

MATERIAL_XAML = WINDOW_HEAD + (
    u'Title="Create Color Legend — 選擇圖例材質" Width="940" Height="640" MinWidth="640" MinHeight="420" '
    u'ResizeMode="CanResizeWithGrip">' + BUTTON_STYLE +
    u'<Grid Margin="16"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/>'
    u'<RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="*"/>'
    u'<RowDefinition Height="Auto"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>'
    u'<TextBlock x:Name="Intro" TextWrapping="Wrap" Margin="0,0,0,12"/>'
    u'<Grid Grid.Row="1" Margin="0,0,0,8"><Grid.ColumnDefinitions><ColumnDefinition Width="Auto"/>'
    u'<ColumnDefinition Width="*"/></Grid.ColumnDefinitions>'
    u'<Label Content="搜尋(_S)" Target="{{Binding ElementName=SearchBox}}" VerticalAlignment="Center" Padding="0,0,8,0"/>'
    u'<TextBox x:Name="SearchBox" Grid.Column="1" MinHeight="30" Padding="4,3" BorderBrush="{boundary}" '
    u'AutomationProperties.Name="搜尋材質（Description、Name、Category、ID）" '
    u'ToolTip="比對 Description、Material Name、Category 與 Material ID；不影響勾選狀態"/></Grid>'
    u'<Grid Grid.Row="2" Margin="0,0,0,8"><Grid.ColumnDefinitions><ColumnDefinition Width="Auto"/>'
    u'<ColumnDefinition Width="Auto"/><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/>'
    u'</Grid.ColumnDefinitions>'
    u'<Button x:Name="SelectVisible" Content="全選目前顯示(_A)" Margin="0"/>'
    u'<Button x:Name="ClearVisible" Grid.Column="1" Content="全不選目前顯示(_N)"/>'
    u'<TextBlock Grid.Column="2" Margin="12,0" VerticalAlignment="Center" TextWrapping="Wrap" Foreground="{secondary}" '
    u'FontSize="13" Text="只作用於目前搜尋顯示的項目；隱藏的項目維持原勾選。"/>'
    u'<TextBlock x:Name="Counter" Grid.Column="3" VerticalAlignment="Center" FontWeight="SemiBold" '
    u'/></Grid>'
    u'<Grid x:Name="Header" Grid.Row="3" Margin="0,0,0,4"/>'
    u'<ListBox x:Name="Rows" Grid.Row="4" BorderBrush="{boundary}" Background="{surface}" '
    u'HorizontalContentAlignment="Stretch" ScrollViewer.VerticalScrollBarVisibility="Visible" '
    u'ScrollViewer.HorizontalScrollBarVisibility="Disabled" KeyboardNavigation.TabNavigation="Once" '
    u'VirtualizingStackPanel.IsVirtualizing="False" AutomationProperties.Name="材質清單；空白鍵切換勾選"/>'
    u'<TextBlock x:Name="Status" Grid.Row="5" Margin="0,8,0,0" TextWrapping="Wrap" Foreground="{warning}"/>'
    u'<StackPanel Grid.Row="6" Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,12,0,0">'
    u'<Button x:Name="OkButton" Content="確認(_O)" IsDefault="True" Background="{accent}" Foreground="White"/>'
    u'<Button x:Name="CancelButton" Content="取消" IsCancel="True"/></StackPanel>'
    u'</Grid></Window>').format(**TOKENS)

CATEGORY_XAML = WINDOW_HEAD + (
    u'Title="Create Color Legend — 選擇 Category" SizeToContent="Height" Width="560" ResizeMode="NoResize">'
    + BUTTON_STYLE +
    u'<StackPanel Margin="16"><TextBlock x:Name="Intro" TextWrapping="Wrap" Margin="0,0,0,12"/>'
    u'<Border BorderBrush="{boundary}" BorderThickness="1" Background="{surface}" Padding="12,8">'
    u'<StackPanel x:Name="Choices" KeyboardNavigation.TabNavigation="Continue"/></Border>'
    u'<TextBlock x:Name="Status" Margin="0,8,0,0" TextWrapping="Wrap" Foreground="{warning}"/>'
    u'<StackPanel Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,12,0,0">'
    u'<Button x:Name="OkButton" Content="下一步(_O)" IsDefault="True" Background="{accent}" Foreground="White"/>'
    u'<Button x:Name="CancelButton" Content="取消" IsCancel="True"/></StackPanel></StackPanel></Window>').format(**TOKENS)

RULE_HELP = {
    'OST_Casework': u'依範圍內每個 solid 的面材質（含 In-Place 多個 solid）',
    'OST_GenericModel': u'依範圍內每個 solid 的面材質（In-Place 與一般 Family）',
    'OST_Walls': u'只取牆 Exterior 側最外層構造層',
    'OST_Floors': u'只取最上層構造層',
    'OST_Ceilings': u'只取最下層構造層',
}


def brush(value):
    if isinstance(value, (list, tuple)):
        return SolidColorBrush(Color.FromRgb(value[0], value[1], value[2]))
    return SolidColorBrush(ColorConverter.ConvertFromString(value))


def _set_owner(window, owner_handle):
    if owner_handle is not None:
        try:
            WindowInteropHelper(window).Owner = owner_handle
            window.WindowStartupLocation = WindowStartupLocation.CenterOwner
        except Exception:
            pass  # ownership is cosmetic; never block the dialog


class MaterialItem(object):
    """One scanned Material. Check state is kept here, independent of row visibility."""

    def __init__(self, row, checked=True, new=False):
        self.uid = row['uid']
        self.description = row.get('description') or u''
        self.name = row.get('name') or u''
        self.material_id = row.get('id')
        self.rgb = list(row['rgb'])
        self.categories = [CATEGORY_LABELS.get(k, k) for k in row.get('categories', [])]
        self.checked = bool(checked)
        self.new = bool(new)
        self.search_text = u' '.join([self.description or MISSING_DESCRIPTION, self.name,
                                      u' '.join(self.categories), u'{0}'.format(self.material_id)]).lower()


class MaterialDialog(object):
    """Checkbox list: RGB swatch, Description, Material Name, Categories, Material ID.

    mode 'create': confirming requires at least one checked material.
    mode 'update': confirming with nothing checked is allowed; the caller must confirm removal.
    """

    def __init__(self, items, mode='create', owner_handle=None):
        self.items = list(items)
        self.mode = mode
        self.accepted = False
        self.window = XamlReader.Parse(MATERIAL_XAML)
        _set_owner(self.window, owner_handle)
        find = self.window.FindName
        self.search_box, self.list_box = find('SearchBox'), find('Rows')
        self.counter, self.status, self.ok = find('Counter'), find('Status'), find('OkButton')
        intro = (u'勾選要顯示在圖例的材質。圖例只顯示 Description 與 Material Graphics Shading 色塊；'
                 u'Material Name 與 ID 僅供辨認。')
        if mode == 'update':
            intro += u'\n先前排除的材質維持未勾選；標示「新」的是上次更新後才出現的材質（預設勾選）。'
        find('Intro').Text = intro
        self._header(find('Header'))
        self.rows = []
        for item in self.items:
            row = self._row(item)
            self.rows.append((item, row))
            self.list_box.Items.Add(row)
        self.search_box.TextChanged += lambda s, e: self.search(self.search_box.Text)
        find('SelectVisible').Click += lambda s, e: self.set_visible(True)
        find('ClearVisible').Click += lambda s, e: self.set_visible(False)
        self.ok.Click += self._on_ok
        self.list_box.PreviewKeyDown += self._on_key
        self.window.Loaded += lambda s, e: self.search_box.Focus()
        self._refresh()

    def _grid(self):
        grid = Grid()
        for width in COLUMNS:
            column = ColumnDefinition()
            column.Width = GridLength(1, GridUnitType.Star) if width is None else GridLength(width)
            grid.ColumnDefinitions.Add(column)
        return grid

    def _cell(self, grid, element, column):
        Grid.SetColumn(element, column)
        grid.Children.Add(element)
        return element

    def _text(self, text, secondary=False, italic=False, wrap=True):
        block = TextBlock()
        block.Text = text
        block.Margin = Thickness(4, 2, 8, 2)
        block.VerticalAlignment = VerticalAlignment.Top
        if wrap:
            block.TextWrapping = TextWrapping.Wrap
        if secondary:
            block.Foreground = brush(TOKENS['secondary'])
        if italic:
            block.FontStyle = FontStyles.Italic
        return block

    def _header(self, header):
        grid = self._grid()
        grid.Margin = Thickness(4, 0, SystemParameters.VerticalScrollBarWidth + 4, 0)
        for column, text in enumerate([u'', u'色塊', u'Description（圖例文字）', u'Material Name', u'Category', u'ID']):
            block = self._cell(grid, self._text(text), column)
            block.FontWeight = FontWeights.SemiBold
        header.Children.Add(grid)

    def _row(self, item):
        grid = self._grid()
        box = CheckBox()
        box.IsChecked = item.checked
        box.Margin = Thickness(4, 4, 4, 2)
        box.VerticalAlignment = VerticalAlignment.Top
        AutomationProperties.SetName(box, u'包含 {0}（{1}）'.format(item.description or MISSING_DESCRIPTION, item.name))

        def changed(sender, args, item=item):
            item.checked = bool(sender.IsChecked)
            self._refresh()
        box.Checked += changed
        box.Unchecked += changed
        self._cell(grid, box, 0)
        swatch = Border()
        swatch.Width, swatch.Height = 40, 20
        swatch.Margin = Thickness(4, 3, 8, 3)
        swatch.VerticalAlignment = VerticalAlignment.Top
        swatch.Background = brush(item.rgb)
        swatch.BorderBrush = brush(TOKENS['boundary'])
        swatch.BorderThickness = Thickness(1)
        swatch.ToolTip = u'Shading RGB {0}, {1}, {2}'.format(*item.rgb)
        AutomationProperties.SetName(swatch, swatch.ToolTip)
        self._cell(grid, swatch, 1)
        description = self._text(u'')
        if item.new:
            badge = Run(u'新  ')
            badge.FontWeight = FontWeights.Bold
            badge.Foreground = brush(TOKENS['accent'])
            description.Inlines.Add(badge)
        text = Run(item.description or MISSING_DESCRIPTION)
        if not item.description:
            text.FontStyle = FontStyles.Italic
            text.Foreground = brush(TOKENS['secondary'])
        description.Inlines.Add(text)
        description.ToolTip = item.description or MISSING_DESCRIPTION
        self._cell(grid, description, 2)
        name = self._cell(grid, self._text(item.name), 3)
        name.ToolTip = item.name
        self._cell(grid, self._text(u', '.join(item.categories), secondary=True), 4)
        self._cell(grid, self._text(u'{0}'.format(item.material_id), secondary=True, wrap=False), 5)
        row = ListBoxItem()
        row.Content = grid
        row.Tag = item.uid
        AutomationProperties.SetName(row, box.GetValue(AutomationProperties.NameProperty))
        return row

    def checkbox(self, uid):
        for item, row in self.rows:
            if item.uid == uid:
                return row.Content.Children[0]
        raise KeyError(uid)

    def visible_items(self):
        return [item for item, row in self.rows if row.Visibility == Visibility.Visible]

    def search(self, text):
        query = (text or u'').strip().lower()
        for item, row in self.rows:
            row.Visibility = Visibility.Visible if not query or query in item.search_text else Visibility.Collapsed
        self._refresh()

    def set_visible(self, checked):
        for item, row in self.rows:
            if row.Visibility == Visibility.Visible:
                row.Content.Children[0].IsChecked = checked  # raises Checked/Unchecked -> item state
        self._refresh()

    def toggle(self, uid):
        box = self.checkbox(uid)
        box.IsChecked = not bool(box.IsChecked)

    def checked_uids(self):
        return [item.uid for item in self.items if item.checked]

    def _refresh(self):
        checked = len(self.checked_uids())
        shown = len(self.visible_items())
        self.counter.Text = u'已選 {0} / 共 {1}（顯示 {2}）'.format(checked, len(self.items), shown)
        if not checked and self.mode == 'create':
            self.status.Text = u'至少勾選一個材質才能建立圖例。'
        elif not checked:
            self.status.Text = u'未勾選任何材質：確認後會先詢問是否移除此圖例的所有工具列（保留設定，可再次更新恢復）。'
        elif not shown:
            self.status.Text = u'沒有符合搜尋的材質；清除搜尋即可看到全部項目（勾選狀態不會改變）。'
        else:
            self.status.Text = u''
        self.ok.IsEnabled = bool(checked) or self.mode == 'update'

    def _on_key(self, sender, args):
        if args.Key != Key.Space or isinstance(args.OriginalSource, CheckBox):
            return
        row = self.list_box.SelectedItem
        if row is not None and row.Visibility == Visibility.Visible:
            self.toggle(row.Tag)
            args.Handled = True

    def _on_ok(self, sender, args):
        if not self.ok.IsEnabled:
            return
        self.accepted = True
        try:
            self.window.DialogResult = True
        except Exception:
            self.window.Close()  # not shown modally (test harness)

    def result(self):
        return self.checked_uids() if self.accepted else None

    def show(self):
        self.window.ShowDialog()
        return self.result()


class CategoryDialog(object):
    """Only implemented categories are listed; keys are stable BuiltInCategory names."""

    def __init__(self, selected, owner_handle=None, intro=None):
        self.accepted = False
        self.window = XamlReader.Parse(CATEGORY_XAML)
        _set_owner(self.window, owner_handle)
        find = self.window.FindName
        self.status, self.ok = find('Status'), find('OkButton')
        find('Intro').Text = intro or (u'選擇要掃描的 Category（可複選）。只列出此工具已實作規則的類別；'
                                       u'同一 Material 出現在多個 Category 只列一次。')
        self.boxes = []
        panel = find('Choices')
        for index, key in enumerate(CATEGORY_KEYS):
            box = CheckBox()
            box.IsChecked = key in selected
            box.Margin = Thickness(0, 4, 0, 4)
            label = TextBlock()
            label.TextWrapping = TextWrapping.Wrap
            title = Run(u'{0}  '.format(CATEGORY_LABELS[key]))
            title.FontWeight = FontWeights.SemiBold
            label.Inlines.Add(title)
            hint = Run(RULE_HELP[key])
            hint.Foreground = brush(TOKENS['secondary'])
            label.Inlines.Add(hint)
            box.Content = label
            AutomationProperties.SetName(box, u'{0}：{1}'.format(CATEGORY_LABELS[key], RULE_HELP[key]))
            box.Checked += lambda s, e: self._refresh()
            box.Unchecked += lambda s, e: self._refresh()
            panel.Children.Add(box)
            self.boxes.append((key, box))
        self.ok.Click += self._on_ok
        self.window.Loaded += lambda s, e: self.boxes[0][1].Focus()
        self._refresh()

    def selected(self):
        return [key for key, box in self.boxes if box.IsChecked]

    def set(self, key, checked):
        dict(self.boxes)[key].IsChecked = checked

    def _refresh(self):
        count = len(self.selected())
        self.ok.IsEnabled = bool(count)
        self.status.Text = u'' if count else u'至少選擇一個 Category。'

    def _on_ok(self, sender, args):
        if not self.ok.IsEnabled:
            return
        self.accepted = True
        try:
            self.window.DialogResult = True
        except Exception:
            self.window.Close()

    def result(self):
        return self.selected() if self.accepted else None

    def show(self):
        self.window.ShowDialog()
        return self.result()


def choose_categories(selected, owner_handle=None):
    return CategoryDialog(selected, owner_handle).show()


def choose_materials(rows, registry_rows=None, excluded=(), mode='create', owner_handle=None):
    """Returns the checked Material UniqueIds, or None when cancelled."""
    from legend_core import initial_selection
    state = initial_selection([r['uid'] for r in rows], registry_rows or {}, excluded)
    items = [MaterialItem(r, state[r['uid']]['checked'], mode == 'update' and state[r['uid']]['new'])
             for r in rows]
    return MaterialDialog(items, mode, owner_handle).show()
