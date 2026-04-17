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

load_csv()

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

    # Optional: show details for first recommendation
    if shops:
        s = shops[0]
        print("\nDetails for:", s)
        for q in [
            f"area({s},A).",
            f"station({s},St).",
            f"price_level({s},P).",
            f"broth({s},B).",
            f"richness({s},R).",
            f"open_late({s},OL).",
            f"wait_level({s},W).",
            f"seating({s},S)."
        ]:
            ans = list(prolog.query(q, maxresult=1))
            if ans:
                # print first variable value found
                print(" ", q.split("(")[0], "=", list(ans[0].values())[0])

if __name__ == "__main__":
    print("Tokyo Ramen Expert System")
    run_once()