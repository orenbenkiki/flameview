#!/usr/bin/env python3

"""
Generate a flame graph view.
"""

import re
import sys
from argparse import ArgumentParser
from argparse import Namespace
from argparse import RawDescriptionHelpFormatter
from random import random
from random import seed
from textwrap import dedent
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import TextIO
from typing import Tuple


VERSION = "0.1-b5"


# pylint: disable=too-many-lines
# pylint: disable=missing-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes


class Entry:
    def __init__(self, size: float, tooltip_html: str) -> None:
        self.size = size
        self.tooltip_html = tooltip_html


class Node:
    _next_index = 0

    def __init__(self, name: str) -> None:
        self.index = Node._next_index
        Node._next_index += 1
        self.total_size = 0.0
        self.name = name
        self.label = name
        self.klass = 'sum'
        self.column = 0
        self.columns_span = 0
        self.group: Optional[str] = None
        self.entry: Optional[Entry] = None
        self.nodes: Dict[str, 'Node'] = {}


def _main() -> None:  # pylint: disable=too-many-locals
    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter,
                            description='Generate a flamegraph view.', epilog=dedent("""
        INPUT: A flamegraph file. Each line must be in the format:

            name;...;name size [difference] [#tooltip_html]

        OUTPUT: An HTML file visualizing the flame graph.
    """))
    parser.add_argument('--minpercent', metavar='PERCENT', default='0.1', type=float,
                        help='The minimal percent of the entries to display; '
                        'default: 0.1 (1/1000 of the total)')

    parser.add_argument('--sortby', metavar='SORT_KEY',
                        default='name', choices=['name', 'size', 'input'],
                        help='How to sort nodes:\n'
                        'name (default) - lexicographically, '
                        'size - by the size data, '
                        'input - by input order')

    parser.add_argument('--inverted', action='store_true',
                        help='If specified, generate an inverted (icicles) graph.')

    parser.add_argument('--title', metavar='TITLE',
                        help='An optional title for the HTML document; '
                        'default: "Flame Graph" or "Icicle Graph"')

    parser.add_argument('--sizename', metavar='NAME', default="samples",
                        help='The name of the size data; default: "samples".')

    parser.add_argument('--nodefaultcss', action='store_true',
                        help='If specified, the default appearance CSS is omitted, '
                        'probably to avoid interfering with --addcss')

    parser.add_argument('--addcss', metavar='CSS', action='append',
                        help='The name of a CSS file to embed into the output HTML')

    parser.add_argument('--colors', metavar='PALETTE', default='hot',
                        choices=['hot', 'mem', 'io', 'red', 'green', 'blue',
                                 'aqua', 'yellow', 'purple', 'orange'],
                        help='The color palette to use, subset of flamegraph.pl; '
                             'default: "hot", other choices: '
                             'mem, io, red, green, blue, aqua, yellow, purple, orange')

    parser.add_argument('--seed', metavar='SEED', default=None, type=int,
                        help='An optional seed for repeatable random color generation; '
                        'default: None')

    parser.add_argument('--strict', action='store_true',
                        help='If specified, abort with an error on invalid input lines.')

    parser.add_argument('--output', metavar='HTML',
                        help='The HTML file to write; default: "-", write to standard output')

    parser.add_argument('--version', action='store_true',
                        help='Print the version information (%s) and exit' % VERSION)

    parser.add_argument('input', metavar='FLAMEGRAPH', nargs='?',
                        help='The flamegraph data file to read; '
                        'default: "-", read from standard input')

    args = parser.parse_args()

    if args.version:
        print('flameview.py: version %s' % VERSION)
        sys.exit(0)

    seed(args.seed)

    root = _load_input_data(args.input, args.strict)
    _add_self_nodes(root)
    _compute_sizes(root)
    _prune_small_nodes(root, args.minpercent)
    sizes = _size_tree_names(root)
    groups = _compute_tree_groups(root, sizes)

    sort_key = {'name': _by_name, 'size': _by_size, 'input': _by_input}[args.sortby]
    column_sizes = _compute_tree_column_sizes(root, sort_key)
    rows = _compute_tree_rows(root)

    _print_output_data(args, groups, column_sizes, rows)


def _load_input_data(path: Optional[str], is_strict: bool) -> Node:
    if path is None or path == '-':
        return _load_data_file('stdin', is_strict, sys.stdin)
    with open(path, 'r') as file:
        return _load_data_file(path, is_strict, file)


def _load_data_file(path: str, is_strict: bool, file: TextIO) -> Node:
    line_regexp = re.compile(r'''
        \A
        (.*?)
        (?:
            (?:
                \s+
                ([+]?\d*\.?\d+(?:[eE][-+]?\d+)?)
                (?:
                    \s+
                    ([+-]?\d*\.?\d+(?:[eE][-+]?\d+)?)
                )?
            )
            (?:
                \s+
                [#]
                \s*
                (.*?)
            )?
            \s*
        )?
        \Z
    ''', re.X)
    root = Node('all')
    ignored = 0
    for line_number, line_text in enumerate(file.readlines()):
        line_number += 1
        match = line_regexp.fullmatch(line_text)
        if not match:
            if is_strict:
                sys.stderr.write('flameview.py: %s:%s: error: invalid line\n' % (path, line_number))
            ignored += 1
            continue
        names_text, size_text, _difference_text, tooltip_text = match.group(1, 2, 3, 4)
        _add_node(names_text.split(';'), root, Entry(float(size_text), tooltip_text or ''))

    if ignored > 0:
        if is_strict:
            sys.exit(1)
        sys.stderr.write('flameview.py: %s: warning: ignored %s invalid lines\n' % (path, ignored))

    return root


def _add_node(names: List[str], parent: Node, entry: Entry) -> None:
    name = names[0]
    name_node = parent.nodes.get(name)
    if name_node is None:
        name_node = parent.nodes[name] = Node(name)

    if len(names) > 1:
        _add_node(names[1:], name_node, entry)
        return

    if name_node.entry is None:
        name_node.entry = entry
        return

    name_node.entry.size += entry.size
    name_node.entry.tooltip_html = entry.tooltip_html


SELF_NAME = "(self)"


def _add_self_nodes(parent: Node) -> None:
    for node in parent.nodes.values():
        _add_self_nodes(node)
        if not node.nodes:
            assert node.entry is not None
            node.klass = 'leaf'
            continue

        assert node.klass == 'sum'
        if not node.entry:
            continue

        self_node = Node('%s;%s' % (node.name, SELF_NAME))
        self_node.label = SELF_NAME
        self_node.entry = node.entry
        self_node.klass = 'self'
        node.nodes[SELF_NAME] = self_node
        node.entry = None


def _compute_sizes(parent: Node) -> None:
    parent.total_size = 0.0
    if parent.entry is not None:
        parent.total_size += parent.entry.size
    for node in parent.nodes.values():
        _compute_sizes(node)
        parent.total_size += node.total_size


def _prune_small_nodes(root: Node, min_percent: float) -> None:
    if min_percent <= 0 or min_percent >= 100:
        return
    min_size = root.total_size * min_percent / 100.0
    _prune_small_tree(root, min_size)


def _prune_small_tree(parent: Node, min_size: float) -> None:
    assert parent.total_size >= min_size

    large_nodes: Dict[str, Node] = {}
    total_small_nodes_size = 0.0
    for name, node in parent.nodes.items():
        if node.total_size < min_size:
            total_small_nodes_size += node.total_size
        else:
            large_nodes[name] = node
            _prune_small_tree(node, min_size)

    if len(large_nodes) == len(parent.nodes):
        return

    small_node = Node('(small)')
    small_node.entry = Entry(total_small_nodes_size, '')
    small_node.total_size = total_small_nodes_size
    parent.nodes = large_nodes
    parent.nodes['...'] = small_node


def _size_tree_names(root: Node) -> Dict[str, int]:
    sizes: Dict[str, int] = {}
    _size_names(root, sizes)
    return sizes


def _size_names(parent: Node, sizes: Dict[str, int]):
    for node in parent.nodes.values():
        sizes[node.name] = sizes.get(node.name, 0) + 1
        _size_names(node, sizes)


def _compute_tree_groups(root: Node, sizes: Dict[str, int]) -> Dict[str, List[int]]:
    groups: Dict[str, List[int]] = {}
    _compute_groups(root, sizes, groups)
    return groups


def _compute_groups(parent: Node, sizes: Dict[str, int], groups: Dict[str, List[int]]) -> None:
    for node in parent.nodes.values():
        _compute_groups(node, sizes, groups)
        if sizes[node.name] == 1:
            continue
        node.group = node.name
        group = groups.get(node.name, None)
        if group is None:
            group = groups[node.name] = []
        group.append(node.index)


def _by_name(node: Node) -> str:
    return node.name


def _by_size(node: Node) -> float:
    return -node.total_size


def _by_input(node: Node) -> int:
    return node.index


def _compute_tree_column_sizes(parent: Node, sort_key: Callable[[Node], Any]) -> List[float]:
    column_sizes: List[float] = []
    _compute_column_sizes(parent, sort_key, column_sizes)
    return column_sizes


def _compute_column_sizes(parent: Node, sort_key: Callable[[Node], Any],
                          column_sizes: List[float]) -> None:
    parent.column = len(column_sizes)

    if parent.nodes:
        assert parent.entry is None
        for node in sorted(parent.nodes.values(), key=sort_key):
            _compute_column_sizes(node, sort_key, column_sizes)
            parent.columns_span = node.column + node.columns_span - parent.column

    else:
        assert parent.entry is not None
        column_sizes.append(parent.entry.size)
        parent.columns_span = 1


def _compute_tree_rows(root: Node) -> List[List[Node]]:
    rows: List[List[Node]] = []
    _collect_unsorted_rows(root, rows, 0)
    _sort_rows(rows)
    return rows


def _collect_unsorted_rows(parent: Node, rows: List[List[Node]], level: int) -> None:
    if len(rows) == level:
        rows.append([])
    row = rows[level]
    row.append(parent)
    for node in parent.nodes.values():
        _collect_unsorted_rows(node, rows, level + 1)


def _sort_rows(rows: List[List[Node]]) -> None:
    for row in rows:
        row.sort(key=_by_column)


def _by_column(node: Node) -> int:
    return node.column


BEFORE_TITLE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
"""[1:]

BEFORE_CSS = """
<style>
/*** Layout: ***/

* {
    box-sizing: border-box;
}

#width, #graph, #row, #height {
    margin: 0;
    padding: 0;
}

.row {
    position: relative;
}

.leaf,
.self,
.sum {
    position: absolute;
}

.label {
    min-width: 0;
    overflow: hidden;
}

.tooltip {
    visibility: hidden;
    position: absolute;
    z-index: 1;
}
"""

DEFAULT_APPEARANCE_CSS = """
/*** Default Appearance: ***/

* {
    font-family: sans-serif;
}

.leaf,
.self,
.sum {
    border-width: 1px;
    border-style: solid;
    border-radius: 4px;
    border-color: black;
    text-align: center;
}

.group_hover .label {
    background-color: ivory !important;
}

.name {
    font-style: italic;
}

.selected .label {
    font-weight: bold;
}

.selected .name {
    font-weight: bold;
}

.tooltip {
    border-style: solid;
    border-width: 2px;
    border-radius: 4px;
    border-color: black;
    background-color: ivory;
    padding: 0.25em 0.5em 0.25em 0.5em;
    text-align: left;
}

.tooltipped .leaf:hover .tooltip,
.tooltipped .self:hover .tooltip,
.tooltipped .sum:hover .tooltip {
    visibility: visible;
}
"""

BEFORE_JAVASCRIPT = """
</style>
<script>
/*jslint browser: true*/

/*** Generated Data: ***/
"""[1:]


BEFORE_HTML = """
/*** Behavior: ***/

// The total size of everything (for computing percentages).
// Computed on load.
var total_size = null;

// The list of currently selected cell ids.
var selected_cell_ids = [];

// The id of the root cell that covers everything (by convention).
var root_id = "N0";

// Compute which columns are visible given the current selection.
function compute_visible_columns_mask() {
    "use strict";
    if (selected_cell_ids.length === 1) {
        var selected_cell_id = selected_cell_ids[0];
        return cells_data[selected_cell_id].columns_mask;
    }

    var lowest_cell_id = undefined;
    var lowest_level = undefined;
    selected_cell_ids.forEach(function (cell_id) {
        var cell_level = cells_data[cell_id].level;
        if (lowest_cell_id === undefined || lowest_level > cell_level) {
            lowest_cell_id = cell_id;
            lowest_level = cell_level;
        }
    });

    var visible_columns_mask = cells_data[lowest_cell_id].columns_mask.slice();
    selected_cell_ids.forEach(function (cell_id) {
        var group_id = cells_data[cell_id].group_id;
        var columns_mask = (
            group_id
            ? groups_data[group_id].columns_mask
            : cells_data[cell_id].columns_mask
        );
        columns_mask.forEach(function (is_column_in_group, column_index) {
            visible_columns_mask[column_index] *= is_column_in_group;
        });
    });
    return visible_columns_mask;
}

// Compute the total size of the visible columns.
function compute_visible_size(visible_columns_mask) {
    "use strict";
    var visible_size = 0;
    column_sizes.forEach(function (column_size, column_index) {
        visible_size += column_size * visible_columns_mask[column_index];
    });
    return visible_size;
}

// Convert a number to a human-friendly precision.
//
// Allow no more than 2 decimal digits after the `.`, unless the number is very
// small, in which case allow as many as needed so that the first two
// significant digits are visible.
function stringify(number) {
    "use strict";
    if (number === 0) {
        return number;
    }
    if (number < 0) {
        return "-" + stringify(-number);
    }
    var precision = 1;
    var result = 0;
    while (result === 0) {
        precision *= 10;
        result = Math.round(number * precision) / precision;
    }
    precision *= 10;
    return Math.round(number * precision) / precision;
}

// Update the visibility and width of a specific cell.
function update_cell(visible_columns_mask,
        scale_factor, visible_size, cell_id) {
    "use strict";
    var cell_data = cells_data[cell_id];
    var cell = document.getElementById(cell_id);

    var cell_offset_is_done = false;
    var cell_offset = 0;
    var cell_size = 0;
    cell_data.columns_mask.forEach(function (is_column_used, column_index) {
        if (visible_columns_mask[column_index] > 0) {
            if (is_column_used > 0) {
                cell_offset_is_done = true;
                cell_size += column_sizes[column_index];
            } else if (!cell_offset_is_done) {
                cell_offset += column_sizes[column_index];
            }
        }
    });

    if (!cell_offset_is_done) {
        cell.style.display = "none";
        return;
    }

    cell.style.display = null;
    var left = Math.round(cell_offset * scale_factor);
    cell.style.left = left + "px";
    var width = Math.round((cell_offset + cell_size) * scale_factor) - left;
    cell.style.width = width + "px";

    var computed = cell.querySelector(".computed");
    if (!computed) {
        return;
    }

    var computed_text = stringify(cell_size);
    if (cell_size === total_size) {
        computed.innerText = computed_text;
        return;
    }

    if (visible_size !== total_size && cell_size !== visible_size) {
        var percentage_of_visible = 100 * cell_size / visible_size;
        computed_text += "<br/>" + stringify(percentage_of_visible) +
                "% out of: " + stringify(visible_size) + " visible";
    }

    var percentage_of_total = 100 * cell_size / total_size;
    computed_text += "<br/>" + stringify(percentage_of_total) +
            "% out of: " + stringify(total_size) + " total";

    computed.innerHTML = computed_text;
}

// Update all the cells visibility and width.
//
// Must be done every time the selected cell and/or the display width change.
function update_cells() {
    "use strict";
    var visible_columns_mask = compute_visible_columns_mask();
    var visible_size = compute_visible_size(visible_columns_mask);
    var graph_width = document.getElementById("width").clientWidth;
    var graph = document.getElementById("graph");
    graph.style.width = graph_width + "px";
    var scale_factor = (graph_width - 2) / visible_size;
    Object.keys(cells_data).forEach(function (cell_id) {
        update_cell(visible_columns_mask, scale_factor, visible_size, cell_id);
    });
}

// Cell hover highlights all cells in a group.
// The cell itself is highlighted using the :hover CSS selector.
// The other cells in the group are highlighted using the group_hover class.

// Highlight all group cells on entry.
function on_over(event) {
    "use strict";
    var cell = event.currentTarget;
    var group_id = cells_data[cell.id].group_id;
    if (group_id) {
        groups_data[group_id].cell_ids.forEach(function (group_cell_id) {
            var group_cell = document.getElementById(group_cell_id);
            group_cell.classList.add("group_hover");
        });
    } else {
        cell.classList.add("group_hover");
    }
}

// Unhighlight all group cells on exit.
function on_out(event) {
    "use strict";
    var cell = event.currentTarget;
    var group_id = cells_data[cell.id].group_id;
    if (group_id) {
        groups_data[group_id].cell_ids.forEach(function (group_cell_id) {
            var group_cell = document.getElementById(group_cell_id);
            group_cell.classList.remove("group_hover");
        });
    } else {
        cell.classList.remove("group_hover");
    }
}

// Select a cell for filtering the visible graph content.
//
// A simple click just shows the selected cell columns,
// a control-click adds/removes selected cells,
// an alt-click toggles tooltips.
//
// When multiple cells are selected, the lowest-level one restricts the set of
// columns, and each additional higher-level cell further restricts the columns
// to these covered by the group the cell belongs to.
function on_click(event) {
    "use strict";
    var cell = event.currentTarget;

    if (event.altKey) {
        document.getElementById("graph").classList.add("tooltipped");
        return;
    }

    if (!event.ctrlKey) {
        selected_cell_ids.forEach(function (cell_id) {
            document.getElementById(cell_id).classList.remove("selected");
        });
        selected_cell_ids = [cell.id];
        cell.classList.add("selected");
        update_cells();
        return;
    }

    var new_selected_cell_ids = [];
    selected_cell_ids.forEach(function (cell_id) {
        if (cell_id !== cell.id) {
            new_selected_cell_ids.push(cell_id);
        }
    });

    if (new_selected_cell_ids.length === selected_cell_ids.length) {
        selected_cell_ids.push(cell.id);
        cell.classList.add("selected");
        update_cells();
        return;
    }

    cell.classList.remove("selected");
    selected_cell_ids = new_selected_cell_ids;

    if (new_selected_cell_ids.length === 0) {
        selected_cell_ids = [root_id];
        document.getElementById(root_id).classList.add("selected");
    }

    update_cells();
}

// Disable tooltips.
function disable_tooltip(event) {
    "use strict";
    if (event.altKey) {
        document.getElementById("graph").classList.remove("tooltipped");
        event.stopPropagation();
    }
}

// Attach handlers to table cells.
function register_handlers() {
    "use strict";
    Object.keys(cells_data).forEach(function (cell_id) {
        var cell = document.getElementById(cell_id);
        cell.onclick = on_click;
        cell.onmouseover = on_over;
        cell.onmouseout = on_out;
        var tooltip = cell.querySelector(".tooltip");
        if (tooltip) {
            tooltip.onclick = disable_tooltip;
        }
    });
}

function compute_groups_columns_masks() {
    "use strict";
    Object.keys(groups_data).forEach(function (group_id) {
        var group_data = groups_data[group_id];
        group_data.cell_ids.forEach(function (cell_id) {
            var cell_data = cells_data[cell_id];
            if (!group_data.columns_mask) {
                group_data.columns_mask = cell_data.columns_mask.slice();
            } else {
                var columns_mask = cell_data.columns_mask;
                columns_mask.forEach(function (is_column_used, column_index) {
                    if (is_column_used > 0) {
                        group_data.columns_mask[column_index] = 1;
                    }
                });
            }
        });
    });
}

function on_load() {
    "use strict";
    register_handlers();
    total_size = compute_visible_size(cells_data[root_id].columns_mask);
    compute_groups_columns_masks();
    on_click({
        "currentTarget": document.getElementById(root_id),
        "ctrlKey": false
    });
}

// On resize, update all the cell widths.
window.onresize = update_cells;

// Properly initialize everything on load.
window.onload = on_load;
</script>
</head>
<body>
"""[1:]

AFTER_HTML = """
<div id="width"></div>
</body>
</html>
"""[1:]


def _print_output_data(args: Namespace, groups: Dict[str, List[int]],
                       column_sizes: List[float], rows: List[List[Node]]) -> None:
    if args.output is None or args.output == '-':
        _print_output_file(sys.stdout, args, groups, column_sizes, rows)
    else:
        with open(args.output, 'w') as file:
            _print_output_file(file, args, groups, column_sizes, rows)


def _print_output_file(file: TextIO, args: Namespace, groups: Dict[str, List[int]],
                       column_sizes: List[float], rows: List[List[Node]]) -> None:
    file.write(BEFORE_TITLE)

    title = args.title
    if title is None:
        if args.inverted:
            title = "Icicle Graph"
        else:
            title = "Flame Graph"
    _print_title(file, title)

    file.write(BEFORE_CSS)

    if not args.nodefaultcss:
        file.write(DEFAULT_APPEARANCE_CSS)
    for css_path in args.addcss or []:
        try:
            with open(css_path, 'r') as css_file:
                file.write(css_file.read())
        except FileNotFoundError:
            sys.stderr.write('flameview.py: No such file or directory: %s\n' % css_path)
            sys.exit(1)

    file.write(BEFORE_JAVASCRIPT)

    _print_groups_data(file, groups)
    _print_cells_data(file, rows, len(column_sizes))
    _print_column_sizes(file, column_sizes)

    file.write(BEFORE_HTML)

    _print_h1(file, title)
    if args.inverted:
        _print_table(file, args.sizename, args.colors, rows)
    else:
        _print_table(file, args.sizename, args.colors, list(reversed(rows)))

    file.write(AFTER_HTML)


def _print_title(file: TextIO, title: str) -> None:
    file.write('<title>%s</title>' % title)


def _print_groups_data(file: TextIO, groups: Dict[str, List[int]]) -> None:
    file.write(dedent("""
        // Data for each cells group:
        //   cell_ids: The ids of the group cells.
        // On load, the following is computed for each group:
        //   columns_mask: A 0/1 mask of all the columns used by the group cells.
        var groups_data = {
    """))
    group_lines = ['    "%s": {"cell_ids": ["%s"]}'
                   % (group_name, '", "'.join(['N' + str(id) for id in sorted(cell_ids)]))
                   for group_name, cell_ids in sorted(groups.items())]
    file.write(',\n'.join(group_lines))
    file.write('\n};\n\n')


def _print_cells_data(file: TextIO, rows: List[List[Node]], columns_count: int) -> None:
    file.write(dedent("""
        // Data for each cell:
        //   level: The stack nesting level.
        //   columns_mask: A 0/1 mask of all the columns used by the cell.
        //   group_id: The group the cell belongs to, if any.
        var cells_data = {
    """)[1:-1])
    is_first = True
    for level, row in enumerate(rows):
        for node in row:
            if not is_first:
                file.write(',')
            file.write('\n    ')
            _print_cell_data(file, node, columns_count, level)
            is_first = False
    file.write('\n};\n')


def _print_cell_data(file: TextIO, node: Node, columns_count: int, level: int) -> None:
    file.write('"N%s": {\n' % node.index)
    file.write('        "level": %s' % level)
    file.write(',\n        "columns_mask": [%s]'
               % _columns_mask(node.column, node.columns_span, columns_count))
    if node.group:
        file.write(',\n        "group_id": "%s"' % node.group)
    file.write('\n    }')


def _columns_mask(column: int, columns_span: int, columns_count: int) -> str:
    prefix = ["0"] * column
    middle = ["1"] * columns_span
    suffix = ["0"] * (columns_count - column - columns_span)
    return ', '.join(prefix + middle + suffix)


def _print_column_sizes(file, column_sizes: List[float]) -> None:
    file.write(dedent("""
        // The size of each leaf/self cell (that is, a column).
        var column_sizes = [%s];
    """) % ', '.join([str(size) for size in column_sizes]))
    file.write('\n')


def _print_h1(file: TextIO, title: str) -> None:
    file.write('<h1 id="title">%s</h1>\n' % title)


def _print_table(file: TextIO, sizename: str, palette: str, rows: List[List[Node]]) -> None:
    file.write('<div id="graph" class="tooltipped">\n')
    for row in rows:
        _print_row(file, sizename, palette, row)
    file.write('</div>\n')


def _print_row(file: TextIO, sizename: str, palette: str, row: List[Node]) -> None:
    file.write('<div class="row">\n')
    for node in row:
        _print_node(file, sizename, palette, node)
    file.write('<div class="height">&nbsp;</div>\n')
    file.write('</div>\n')


def _print_node(file: TextIO, sizename: str, palette: str, node: Node) -> None:
    file.write('<div id="N%s" class="%s"' % (node.index, node.klass))
    file.write(' style="background-color: %s">\n' % _node_color(node, palette))
    _print_tooltip(file, sizename, node)
    _print_label(file, node)
    file.write('</div>\n')


def _node_color(node: Node, palette: str) -> str:
    if node.label == '-':
        red, green, blue = 50.0, 50.0, 50.0
    else:
        red, green, blue = {
            'hot': _hot_color,
            'mem': _mem_color,
            'io': _io_color,
            'red': _red_color,
            'green': _green_color,
            'blue': _blue_color,
            'aqua': _aqua_color,
            'yellow': _yellow_color,
            'purple': _purple_color,
            'orange': _orange_color,
        }[palette]()
    return 'rgb(%d, %d, %d)' % (red, green, blue)


# Palettes were copied from flamegraph.pl:


def _hot_color() -> Tuple[float, float, float]:
    red = 205 + 50 * random()
    green = 230 * random()
    blue = 55 * random()
    return red, green, blue


def _mem_color() -> Tuple[float, float, float]:
    red = 0.0
    green = 190 + 50 * random()
    blue = 210 * random()
    return red, green, blue


def _io_color() -> Tuple[float, float, float]:
    red = 80 + 60 * random()
    green = red
    blue = 190 + 55 * random()
    return red, green, blue


def _red_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 200 + 55 * fraction
    green = 50 + 80 * fraction
    blue = green
    return red, green, blue


def _green_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 50 + 60 * fraction
    green = 200 + 55 * fraction
    blue = red
    return red, green, blue


def _blue_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 80 + 60 * fraction
    green = red
    blue = 205 + 50 * fraction
    return red, green, blue


def _yellow_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 175 + 55 * fraction
    green = red
    blue = 50 + 20 * fraction
    return red, green, blue


def _purple_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 190 + 65 * fraction
    green = 80 + 60 * fraction
    blue = red
    return red, green, blue


def _aqua_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 50 + 60 * fraction
    green = 165 + 55 * fraction
    blue = green
    return red, green, blue


def _orange_color() -> Tuple[float, float, float]:
    fraction = random()
    red = 190 + 65 * fraction
    green = 90 + 65 * fraction
    blue = 0.0
    return red, green, blue


def _print_tooltip(file: TextIO, sizename: str, node: Node) -> None:
    file.write('<div class="tooltip">\n')
    file.write('<span class="name">%s</span><br/>\n' % _escape(node.name))
    file.write('<hr/>\n')
    file.write('<div class="basic">%s: <span class="computed"></span></div>\n' % sizename)
    if node.entry and node.entry.tooltip_html:
        file.write('<div class="extra">\n')
        file.write(node.entry.tooltip_html)
        file.write('</div>\n')
    file.write('</div>\n')


def _print_label(file: TextIO, node: Node) -> None:
    file.write('<div class="label">%s</div>\n' % _escape(node.label))


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


if __name__ == '__main__':
    _main()
