import os, csv
from pyswip.prolog import Prolog
from pyswip.easy import Atom, Variable, registerForeign

KB_FILE = "ramen_kb.pl"
CSV_FILE = os.path.join("data", "ramen_shops.csv")

prolog = Prolog()


# Menu handler dispatch.
# _active_handler is None by default (terminal mode).
# gui.py calls set_menu_handler() to replace it with a GUI version.
_active_handler = None


def set_menu_handler(fn):
    """Replace the active menu handler.

    Args:
        fn: Callable with signature (attribute, options_list, result) that
            handles a single menuask/3 prompt.  Pass None to restore the
            default terminal handler.
    """
    global _active_handler
    _active_handler = fn


def _terminal_menu_handler(attribute, options_list, result):
    """Print a numbered menu to stdout and read the user's choice.

    Terminal fallback used when no GUI handler has been registered via
    set_menu_handler().  Looks up the human-readable question string from
    QUESTION_TEXTS before printing.

    Args:
        attribute: Prolog Atom naming the preference being asked (e.g. 'budget').
        options_list: Prolog linked-list of Atoms representing the available choices.
        result: Prolog Variable to be unified with the chosen Atom.

    Returns:
        True after successfully unifying result; False if result is already bound.
    """
    if not isinstance(result, Variable):
        return False

    opts = []
    term = options_list
    while str(term) != "[]":
        opts.append(str(term[1]))
        term = term[2]

    attr_str = str(attribute)
    question = QUESTION_TEXTS.get(attr_str, attr_str.replace('_', ' '))
    print(f"\n{question}")
    for i, opt in enumerate(opts, 1):
        print(f"  {i}) {opt.replace('_', ' ')}")

    while True:
        choice = input("Enter option number: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(opts):
                result.unify(Atom(opts[idx - 1]))
                return True
        print("Invalid choice, try again.")


def _dispatch_menu(attribute, options_list, result):
    """Foreign predicate registered with Prolog as read_menu_py/3.

    Delegates each menuask/3 prompt to whichever handler is currently
    active.  Defaults to _terminal_menu_handler when no GUI handler has
    been set via set_menu_handler().

    Args:
        attribute: Prolog Atom naming the preference being asked.
        options_list: Prolog linked-list of Atoms representing the choices.
        result: Prolog Variable to be unified with the chosen value.

    Returns:
        True after the handler successfully unifies result; False otherwise.
    """
    handler = _active_handler or _terminal_menu_handler
    return handler(attribute, options_list, result)


_dispatch_menu.arity = 3
registerForeign(_dispatch_menu, name="read_menu_py")


# Helper: assert a Prolog fact.
def assert_fact(pred, *args):
    """Assert a ground Prolog fact into the dynamic database.

    Args:
        pred: Predicate name as a string (e.g. 'broth').
        *args: String arguments forming the fact's argument list.
            Each value must already be a safe Prolog atom; use atomize()
            if the value comes from raw user or CSV input.
    """
    arg_str = ",".join(args)
    prolog.assertz(f"{pred}({arg_str})")


def atomize(s: str) -> str:
    """Convert an arbitrary string into a safe lowercase Prolog atom.

    Strips surrounding whitespace, lower-cases, replaces '&' with 'and',
    converts every non-alphanumeric character to '_', then collapses
    consecutive underscores.

    Args:
        s: Raw string to convert (e.g. a CSV cell value).

    Returns:
        A non-empty lowercase alphanumeric-and-underscore atom string,
        or 'unknown' if the input reduces to an empty string.

    Example:
        >>> atomize('Tokyo Station')
        'tokyo_station'
    """
    s = s.strip().lower()
    s = s.replace("&", "and")
    s = "".join(ch if ch.isalnum() else "_" for ch in s)
    s = "_".join([p for p in s.split("_") if p])
    return s if s else "unknown"


# Load CSV data and assert shop facts.
def load_csv():
    """Read the CSV shop data file and assert all shop facts into Prolog.

    Opens CSV_FILE, iterates over each row, and calls assert_fact() for
    every attribute column.  shop_id and all string values are first
    normalised through atomize() before being asserted.
    """
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shop_id = atomize(row["shop_id"])
            assert_fact("shop", shop_id)

            # Basic info
            assert_fact("area", shop_id, atomize(row["area"]))
            assert_fact("station", shop_id, atomize(row["station"]))

            # Askable-related attributes
            assert_fact("price_level", shop_id, atomize(row["price_level"]))
            assert_fact("broth", shop_id, atomize(row["broth"]))
            assert_fact("richness", shop_id, atomize(row["richness"]))
            assert_fact("spice", shop_id, atomize(row["spice"]))
            assert_fact("diet", shop_id, atomize(row["diet"]))
            assert_fact("open_late", shop_id, atomize(row["open_late"]))
            assert_fact("seating", shop_id, atomize(row["seating"]))
            assert_fact("group_ok", shop_id, atomize(row["group_ok"]))
            assert_fact("wait_level", shop_id, atomize(row["wait_level"]))
            assert_fact("travel_band", shop_id, atomize(row["travel_band"]))
            assert_fact("ramen_type", shop_id, atomize(row["ramen_type"]))
            assert_fact("jiro_style", shop_id, atomize(row["jiro_style"]))
            assert_fact("payment", shop_id, atomize(row["payment"]))


# Load the Prolog knowledge base and CSV shop data.
prolog.consult(KB_FILE)
load_csv()

# Pre-load natural language question texts from DCG rules.
# These are fetched once here (main thread, after KB is loaded) so that
# both the terminal handler and gui.py can look them up without making
# re-entrant Prolog calls from inside a foreign predicate callback.
_ASKABLE_ATTRS = [
    'budget', 'broth_pref', 'rich_pref', 'spice_tol',
    'diet_req', 'distance_tol', 'wait_tol', 'group_size',
    'open_late_req', 'seating_pref', 'ramen_type_pref',
    'hunger_level', 'payment_pref',
]
QUESTION_TEXTS = {}
for _attr in _ASKABLE_ATTRS:
    _rows = list(prolog.query(f"question_text({_attr}, T).", maxresult=1))
    QUESTION_TEXTS[_attr] = str(_rows[0]['T']) if _rows else _attr.replace('_', ' ')


# Build a human-readable explanation for a recommended shop.
def explain_shop(shop_id):
    """Build a human-readable explanation sentence for a recommended shop.

    Queries each attribute of the shop from the Prolog database and
    assembles them into a single descriptive sentence.  Spice and
    jiro-style information are always included even when they indicate
    the absence of a feature (e.g. "no spice", "regular portions").

    Args:
        shop_id: Prolog atom string identifying the shop
            (e.g. 'ichiran_shinjuku').

    Returns:
        A sentence of the form
        "Recommended <shop> because: <detail list>."
    """
    def query_val(pred, var="X"):
        """Query a single-value Prolog predicate for this shop.

        Args:
            pred: Prolog predicate name (e.g. 'broth').
            var: Variable name used in the query string.

        Returns:
            The string value of the first matching result, or None.
        """
        ans = list(prolog.query(f"{pred}({shop_id},{var}).", maxresult=1))
        return str(ans[0][var]) if ans else None
    
    area      = query_val("area")
    station   = query_val("station")
    budget    = query_val("price_level")
    broth     = query_val("broth")
    richness  = query_val("richness")
    spice     = query_val("spice")
    open_late = query_val("open_late")
    wait      = query_val("wait_level")
    seating   = query_val("seating")
    rtype     = query_val("ramen_type")
    jiro      = query_val("jiro_style")
    payment   = query_val("payment")

    parts = []
    if broth:     parts.append(f"{broth} broth")
    if richness:  parts.append(f"{richness} richness")
    if spice and spice != "none": parts.append(f"{spice} spice")
    if spice == "none":            parts.append("no spice")
    if rtype:     parts.append(f"{rtype}")
    if jiro == "yes": parts.append("jiro-style portions")
    if jiro == "no":  parts.append("regular portions")
    if budget:    parts.append(f"{budget} budget")
    if payment:   parts.append(f"payment: {payment.replace('_', ' ')}")
    if open_late == "yes": parts.append("open late")
    if wait:      parts.append(f"{wait} wait")
    if seating:   parts.append(f"{seating} seating")
    if station:   parts.append(f"near {station.replace('_', ' ')} station")
    if area:      parts.append(f"in {area.replace('_', ' ')}")

    detail = ", ".join(parts) if parts else "matches your preferences"
    return f"Recommended {shop_id.replace('_', ' ')} because: {detail}."


# Run one terminal consultation.
def run_once():
    """Run a single terminal consultation and print the top matching shops.

    Invokes all_recommendations/1 in Prolog (which triggers menuask/3
    for each askable preference in turn), then prints up to three results
    with an explanation sentence for each.
    """
    results = list(prolog.query("all_recommendations(L).", maxresult=1))
    if not results:
        print("\nNo matches found.")
        return

    shops = results[0]["L"]
    shops = [str(s) for s in shops]

    print("\nTop matches:")
    for s in shops[:3]:
        print(" -", s)
        print(" ", explain_shop(s))

if __name__ == "__main__":
    print("Tokyo Ramen Expert System")
    run_once()