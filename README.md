# flameview
Generate a flame graph view.

## REQUIREMENTS

`flameview.py` requires Python 3.6 or above. It does not require the installation
of any supporting modules.

## INSTALLATION

Download `flameview.py` and place it in your path. You might need to tweak the
`#!` line to execute the correct python interpreter; by default it invokes
`python3`.

## DESCRIPTION

`flameview.py` is inspired by the `flamegraph.pl` program, which you can obtain
from https://github.com/brendangregg/FlameGraph. The `flamegraph` program is
much more mature, contains a detailed description of what flame graphs are, and
provides many features that `flameview` lacks: support for differential graphs,
flamecharts, stable hash-based colors, automatic language-specific color
palettes, ...

The `flameview` program does provide some features that `flamegraph` lacks:

* Each input line may end with a `#` character followed by an arbitrary HTML
  string. This string will be placed in the tooltip displayed when hovering
  above the relevant graph cell. This allows attaching arbitrary data to each
  cell. For example, it is possible to display both CPU time (as the
  measurements) and invocations count (in the tooltip), similarly to the output
  of gprof.

* The output is an interactive file, using HTML rather than SVG. As a result,
  there is no need to specify the size of the graph in advance. Instead it
  always spans the full width of the browser's window.

* Selecting (clicking on) a cell restricts the view to the subset of the graph
  rooted in the selected cell. Clicking on the bottom "all" cell views all the
  graph.

  Control-clicking a cell allows for de/selecting multiple cells. The currently
  selected cell(s) are highlighted. There is always at least one such selected
  cell; by default it is the bottom "all" cell.

  When more than one cell is selected, the lowest-level one restricts the view
  to the subset of the graph rooted in that cell, as usual. The additional
  selected higher-level cells further restrict the view, to include only paths
  that contain any cell with the same name as these higher-level selected cells.

* Hovering over any cell highlights all other cells with the same name. These
  are the cells that will remain visible if you add the cell to the selection
  using control-click.

  Hovering over any cell will display a tooltip containing its name, its
  measurement, the percentage of this measurement out of the total visible
  graph, and the additional tooltip HTML, if any, from the input file.

  Hovering over the "all" cell when a subset of the graph is visible will
  display the percentages of the visible graph out of the total graph.

* Explicit "(self)" cells are created when some call chain both has its own
  measurements and measurements for further nested call chains. In such a case,
  the self cell will display the input tooltip and the measurement for the call
  chain; the lower level cell will display the sum of the self measurement and
  all the nested invocations.

The above allows the result flame graph to provide all the information one would
get from a gprof output (and more), in a visual form:

* The tooltips may provide the invocations count, or any other data which is
  associated with the call chain.

* Self nodes allow viewing the measurements of the function itself, as opposed
  to the sum of the function and everything it invokes (which is also
  available).

* If "all" is selected, and you control-click to select a function "foo", you
  will see all the invocations of the "foo" function anywhere in the graph, each
  one above its caller chain. This makes it easy to see the both total measure
  of "foo", what percentage this is of the total, and which percentage is due to
  which caller.

* A further control-click of a higher level "bar" function will show all the
  invocations of "bar" from "foo". This makes it easy to see which percentage of
  the measurements is due to any "bar" (indirectly) invoked from "foo".

* A further control-click to deselect "all" will restrict the view to only the
  calls to "bar" from the specific selected invocation of "foo", again allowing
  to view the total measurement and percentages of such calls.

TWEAKING
--------

The output of `flameview` tries to be well-behaved CSS-annotated HTML,
with the inevitable embedded javascript code. The file requires no external
resources, and contains hopefully helpful comments to help tweaking it.

The output uses a `table` element for laying out the graph, which arguably
should be replaced by using CSS grid layout; but I had less luck getting CSS
grid layout to behave well across browsers.

It should be "easy" to tweak the appearance of the graph by tweaking the CSS.
The CSS stylesheet is given in two parts. The first part controls the layout,
which you probably don't want to mess with (unless you want to try switching
to CSS grid layout).

The second part controls appearance, using the following CSS selectors:

* `#graph`: The table element containing the whole graph.

* `.self`, `.leaf`, `.sum`, `.empty`: Classes for the `td` elements,
  reflecting the kind of cell.

  The background color of empty cells is controlled by CSS; the background color
  of non-empty cells is hard-coded in the `td` element according to the color
  palette specified when the output is generated. It might arguably make sense
  to define some color classes instead, and switch palettes using CSS instead.

* `.selected`: Class for the `td` elements of the currently selected cell(s).
  Currently this just makes the label font **bold**.

* `.label`: Class for the `div` contained in each `td` to hold the label.
  This needs to be a nested `div` to allow for `overflow: hidden`, which
  is not supported for the `td` itself.

* `.tooltip`: Class for the `div` contained in each `td` to hold the tooltip.
  This uses absolute positioning and is only visible when hovering over the `td`.

* `.group_hover`: Class applied to each other `td` that uses the same label as
  the one under the mouse. The `td` under the mouse uses the `:hover` selector
  as usual.

* `.name`: Class for a `span` inside the tooltip `div`, which holds the name
  of the cell. Note the name may be different from the label; specifically,
  when the label is "(self)", the name is "name;(self)". Currently the CSS
  just makes the name font *italic*.

* `.size`: Class for an empty `span` inside the tooltip `div`, which is
  automatically filled with the computed measurement sum and percentage
  depending on the visible cells.

## LICENSE

`flameview.py` is available under the MIT license.