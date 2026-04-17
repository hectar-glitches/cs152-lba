import os, sys, csv
from pyswip.prolog import Prolog
from pyswip.easy import Atom, Functor, Variable, registerForeign

KB_FILE = "ramen_kb.pl"
CSV_FILE = os.path.join("data", "ramen_shops.csv")

prolog = Prolog()

# --- Foreign predicate: read_menu_py(Attribute, OptionsList, Value) ---
def read_menu_py(A, Options, V):
    """
    A: Atom
    Options: Prolog list of atoms
    V: Variable (to unify with chosen Atom)
    """
    if not isinstance(V, Variable):
        return False

    # Convert Prolog list term to Python list
    # Options is a linked-list term like '.'(Head, Tail) or [].
    opts = []
    term = Options
    while str(term) != "[]":
        head = term[1]  # '.'(Head,Tail) -> head at index 1 in PySWIP term
        tail = term[2]
        opts.append(str(head))
        term = tail

    attr = str(A)
    print(f"\nChoose {attr}:")
    for i, opt in enumerate(opts, 1):
        print(f"  {i}) {opt}")

    while True:
        choice = input("Enter option number: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(opts):
                V.unify(Atom(opts[idx - 1]))
                return True
        print("Invalid choice, try again.")

read_menu_py.arity = 3
registerForeign(read_menu_py)

# --- Helper: assert a Prolog fact safely ---
def assert_fact(pred, *args):
    # Build like: pred(arg1,arg2,...).
    arg_str = ",".join(args)
    prolog.assertz(f"{pred}({arg_str})")

def atomize(s: str) -> str:
    """
    Convert CSV strings into safe Prolog atoms.
    Example: 'Tokyo Station' -> 'tokyo_station'
    """
    s = s.strip().lower()
    s = s.replace("&", "and")
    s = "".join(ch if ch.isalnum() else "_" for ch in s)
    s = "_".join([p for p in s.split("_") if p])
    return s if s else "unknown"

# --- Load KB ---
prolog.consult(KB_FILE)

# --- Load CSV data and assert shop facts ---
def load_csv():
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

load_csv()

# --- Build a human-readable explanation for a recommended shop ---
def explain_shop(shop_id):
    """
    Query each attribute of shop_id from Prolog and return a single
    sentence explaining why the shop was recommended.
    """
    def query_val(pred, var="X"):
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


# --- Run one consultation ---
def run_once():
    # Ask Prolog for all matching shops
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