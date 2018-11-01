# flameview
Generate a flame graph view.

## REQUIREMENTS

`flameview.py` requires Python 3.6 or above. It does not require the installation
of any supporting modules.

## INSTALLATION

Download
[flameview.py](https://raw.githubusercontent.com/orenbenkiki/flameview/master/flameview.py)
and place it in your path. You might need to tweak the `#!` line to execute the
correct python interpreter; by default it invokes `python3`.

## STATUS

This is a beta version **0.1-b2**. It provides the basic functionality and seems
to work in Firefox, Chrome and Edge. However, it hasn't been heavily tested.
Feedback is welcome.

## USAGE

The output of ``flameview.py -h`` is:

    usage: flameview.py [-h] [--minpercent PERCENT] [--sortby SORT_KEY]
                        [--inverted] [--title TITLE] [--countname NAME]
                        [--nodefaultcss] [--addcss CSS] [--colors PALETTE]
                        [--output HTML] [--version]
                        [FLAMEGRAPH]

    Generate a flamegraph view.

    positional arguments:
      FLAMEGRAPH            The flamegraph data file to read; default: "-", read
                            from standard input

    optional arguments:
      -h, --help            show this help message and exit
      --minpercent PERCENT  The minimal percent of the entries to display;
                            default: 0.1 (1/1000 of the total)
      --sortby SORT_KEY     How to sort nodes: name (default) - lexicographically,
                            counts - by the counted data
      --inverted            If specified, generate an inverted (icicles) graph.
      --title TITLE         An optional title for the HTML document; default:
                            "Flame Graph" or "Icicle Graph"
      --countname NAME      The name of the counted data; default: "samples".
      --nodefaultcss        If specified, the default appearance CSS is omitted,
                            probably to avoid interfering with --addcss
      --addcss CSS          The name of a CSS file to embed into the output HTML
      --colors PALETTE      The color palette to use, subset of flamegraph.pl;
                            default: "hot", other choices: mem, io, red, green,
                            blue, aqua, yellow, purple, orange
      --output HTML         The HTML file to write; default: "-", write to
                            standard output
      --version             Print the version information (0.1-b1) and exit

    INPUT: A flamegraph file. Each line must be in the format:

        name;...;name size [difference] [#tooltip_html]

    OUTPUT: An HTML file visualizing the flame graph.

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
  of `gprof`.

* The output is an interactive file, using HTML rather than SVG. As a result,
  there is no need to specify the size of the graph in advance. Instead it
  always spans the full width of the browser's window.

* Selecting (clicking on) a cell restricts the view to the subset of the graph
  rooted in the selected cell. Selecting the bottom "all" cell views all the
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

  Hovering over any cell will display (for a few seconds) a tooltip containing
  its name, its measurement, the percentage of this measurement out of the total
  visible graph, and the additional tooltip HTML, if any, from the input file.

  Hovering over the "all" cell when a subset of the graph is visible will
  display the percentages of the currently visible (selected) graph out of the
  total graph.

* Explicit "(self)" cells are created when some call chain has both its own
  measurements and also measurements for further nested call chains. In such a
  case, the self cell will display the input tooltip and the measurement for the
  call chain; the lower level cell will display the sum of the self measurement
  and all the nested invocations.

The above allows the result flame graph to provide all the information one would
get from a `gprof` output (and more), in a visual form:

* The tooltips may provide the invocations count, or any other data which is
  associated with the call chain.

* Self nodes allow viewing the measurements of the function itself, as opposed
  to the sum of the function and everything it invokes (which is also
  available).

* If "all" is selected, and you control-click to select a function "foo", you
  will see all the invocations of the "foo" function anywhere in the graph, each
  one above its caller chain. This makes it easy to see the both total measure
  of "foo", what percentage this is of the program's total, and which percentage
  is due to which caller.

* A further control-click of a higher level "bar" function will show all the
  invocations of "bar" from "foo". This makes it easy to see which percentage of
  the measurements is due to any "bar" invoked from "foo" (directly or
  indirectly).

* A further control-click to deselect "all" will restrict the view to only the
  calls to "bar" from the specific selected invocation of "foo", again allowing
  to view the total measurement and percentages of such calls.

That is, by selecting multiple cells it is possible to gain valuable additional
insights about the execution, which are impossible to obtain using the output of
`flamegraph.pl`, even though the data is present in the graph.

TWEAKING
--------

The output of `flameview` tries to be well-behaved CSS-annotated HTML 5 (clean
according to https://validator.w3.org/), with the inevitable embedded javascript
code (clean according to https://jslint.com/). The file requires no external
resources, and contains hopefully helpful comments to help tweaking it.

The HTML uses absolute positioning to control the horizontal location of the cells,
and lets HTML automatically determine the height of each row (one "normal"
text line height). I tried using both `table` and CSS ``grid`` layout but
neither approach gave me the needed control across browsers.

It should be "easy" to tweak the appearance of the graph by tweaking the CSS.
The embedded CSS stylesheet is given in two parts. The first part controls the
layout, which you probably don't want to mess with (unless you want to try
switching to CSS grid layout).

The second part controls appearance, using the following CSS selectors:

* `#graph`: The `div` containing the whole graph.

* `#width`: An empty `div` following the graph, used to detect the available
  vertical space. If you force its width, the graph will adjust accordingly.

* `.row`: Class for a `div` containing a single graph row. Uses relative
  positioning.

* `.height`: An invisible `div` containing `&nbsp;` to force the height of the
  row. If you adjust its height, the row will adjust accordingly. Note the
  actual row cells do not affect the height because they use absolute
  positioning.

* `.self`, `.leaf`, `.sum`: Classes for `div` elements, reflecting the kind of
  cell. Currently simple border/centering rules are applied to the non-empty
  cells.

  The background color of non-empty cells is hard-coded in the `div` element
  according to the chosen color palette. It might arguably make sense to define
  some color classes instead, and switch palettes using CSS instead.

* `.tooltip`: Class for the `div` contained in each `td` to hold the tooltip.
  This uses absolute positioning and is only visible when hovering over the
  cell.

* `.size`: Class for an empty `span` inside the tooltip `div`, which is
  automatically filled with the computed measurement sum and percentage
  depending on the visible cells. Currently this has no special formatting.

* `.name`: Class for a `span` inside the tooltip `div`, which holds the name of
  the cell. Note the name may be different from the label; specifically, when
  the label is "(self)", the name is "name;(self)". Currently the CSS just makes
  the name font *italic*.

* `.label`: Class for the `div` contained in each non-empty cell to hold the
  label. Making this a sibling rather than a parent of the tooltip makes it
  easier to apply CSS rules only to it.

* `.group_hover`: Class applied to each other cell that has the same name as
  the one under the mouse. The cell directly under the mouse uses the `:hover`
  selector as usual. Currently both turn the cell(s) background color to
  `white`, which makes them stand out of the rest of the colored cells.

* `.selected`: Class for the currently selected cell(s). Currently this just
  makes the label font **bold**. This might be too subtle an effect.

You can append additional CSS rules into the HTML to tweak the default
appearance CSS, or omit the default and provide a full replacement CSS
instead.

FURTHER WORK
------------

* If HTML is preferable to SVG, then it would make sense to further develop
  `flameview.py` to become a true replacement for `flamegraph.pl`. This would
  require re-implementing all the features already present in `flamegraph`. None
  of the features seem terribly complex, but their total is far from trivial.

  Otherwise, it might make more sense to enhance the SVG output of
  `flamegraph.pl` to provide for multiple cell selection and explicit "(self)"
  nodes. This would have to be done in Perl though ;-)

* The default CSS appearance rules could definitely be improved. It is also
  technically trivial to provide a selection between several built-in
  `--csstheme` options. Actually designing such options is much more work.

* Using absolute positioning for layout is basically giving up on the CSS layout
  engine. It would be nice if CSS grid layout could be made to handle this for
  us instead.

The code is pretty simple and short (~1K LOC total, including the Python, CSS,
Javascript and HTML). It gets a clean bill of health from `mypy` and `pylint`.
Pull requests are welcome.

## LICENSE

`flameview.py` is available under the MIT license.
