"""Tkinter GUI front-end for the Tokyo Ramen Expert System.

Architecture:
    The GUI owns the question loop entirely.  It walks through ASKABLES one
    at a time, collecting answers from the user.  Questions that are
    irrelevant given previous answers are skipped automatically.  Once all
    relevant questions have been answered the GUI asserts each answer as a
    known/2 fact into Prolog and calls all_recommendations/1 on the main
    thread.  Because all known/2 facts are already present, menuask/3
    returns immediately from its cache clause and no prompting occurs,
    avoiding any cross-thread Prolog calls.

Dynamic behaviour:
    _should_skip(attr, answers) encodes skip rules.  For example, the jiro
    hunger question is skipped when the user wants tsukemen or has dietary
    restrictions incompatible with jiro-style pork portions.
"""

import tkinter as tk
from tkinter import font as tkfont

from app import prolog, explain_shop, QUESTION_TEXTS

# Ordered list of (attribute, options) pairs matching the Prolog KB askables.
# The GUI iterates this list, optionally skipping entries via _should_skip.
ASKABLES = [
    ('budget',          ['low', 'medium', 'high']),
    ('broth_pref',      ['tonkotsu', 'shoyu', 'shio', 'miso', 'tsukemen', 'no_pref']),
    ('rich_pref',       ['light', 'medium', 'rich', 'no_pref']),
    ('spice_tol',       ['none', 'mild', 'spicy']),
    ('diet_req',        ['none', 'vegetarian', 'halal']),
    ('distance_tol',    ['near', 'mid', 'any']),
    ('wait_tol',        ['short', 'medium', 'any']),
    ('group_size',      ['solo', 'small', 'group']),
    ('open_late_req',   ['yes', 'no']),
    ('seating_pref',    ['bar', 'table', 'no_pref']),
    ('ramen_type_pref', ['ramen', 'tsukemen', 'either']),
    ('hunger_level',    ['jiro', 'regular']),
    ('payment_pref',    ['card_ok', 'no_pref']),
]

# Default values assigned to skipped attributes so Prolog still has a
# known/2 fact for every askable when all_recommendations/1 is called.
_SKIP_DEFAULTS = {
    'hunger_level': 'regular',
    'rich_pref':    'no_pref',
}

# Maps each matches_* predicate to a short human-readable constraint label
# used to report which preferences a shop did not satisfy.
_CONSTRAINT_LABELS = [
    ('matches_budget',     'budget'),
    ('matches_broth',      'broth preference'),
    ('matches_richness',   'richness'),
    ('matches_spice',      'spice tolerance'),
    ('matches_diet',       'dietary requirement'),
    ('matches_distance',   'distance tolerance'),
    ('matches_wait',       'wait tolerance'),
    ('matches_group',      'group size'),
    ('matches_open_late',  'open late'),
    ('matches_seating',    'seating preference'),
    ('matches_ramen_type', 'ramen type'),
    ('matches_hunger',     'portion style'),
    ('matches_payment',    'payment method'),
]

# Colour for GUI.
ACCENT = "#c0392b"   # warm red
BG     = "#fdf6ec"   # warm off-white
FG     = "#2c2c2c"   # near-black text
SUBTLE = "#8B8484"   # secondary text
ACTIVE = "#26a933"   # green for hover/active states


def _should_skip(attr, answers):
    """Return True if attr is irrelevant given answers collected so far.

    Args:
        attr: Askable attribute name string.
        answers: Dict mapping previously answered attribute names to values.

    Returns:
        True if the question should be skipped; False otherwise.
    """
    if attr == 'hunger_level':
        # Jiro-style is only for regular ramen. Skip if the user wants
        # tsukemen or has dietary restrictions that rule out pork portions.
        if answers.get('ramen_type_pref') == 'tsukemen':
            return True
        if answers.get('diet_req') in ('vegetarian', 'halal'):
            return True
    if attr == 'rich_pref':
        # Richness is only meaningful when the user cares about broth type.
        if answers.get('broth_pref') == 'no_pref':
            return True
    return False


class RamenGUI:
    """Tkinter front-end for the Tokyo Ramen Expert System.

    Owns the entire question loop.  Answers are collected in Python, then
    asserted as known/2 facts before a single synchronous Prolog query
    retrieves recommendations on the main thread.

    Attributes:
        root: The root Tk window this GUI is attached to.
    """

    def __init__(self, root: tk.Tk):
        """Initialise the application window and start the first session.

        Args:
            root: The root Tkinter window to attach the GUI to.
        """
        self.root = root
        self.root.title("Tokyo Ramen Finder")
        self.root.geometry("580x460")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self._answers = {}
        self._askable_queue = []
        self._current_attr = None
        self._q_count = 0
        self._selected = tk.StringVar()

        self._build_ui()
        self._start_session()

    def _build_ui(self):
        """Build the header, question frame, and results frame widgets."""
        # Header frame.
        hdr = tk.Frame(self.root, bg=ACCENT, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="Tokyo Ramen Finder",
            bg=ACCENT, fg="white",
            font=tkfont.Font(family="Helvetica", size=17, weight="bold"),
        ).pack(side="left", padx=20, pady=12)

        # Question frame.
        self._q_frame = tk.Frame(self.root, bg=BG, padx=36, pady=24)

        self._q_label = tk.Label(
            self._q_frame, text="",
            bg=BG, fg=FG,
            font=tkfont.Font(family="Helvetica", size=14, weight="bold"),
            wraplength=500, justify="left",
        )
        self._q_label.pack(anchor="w", pady=(0, 16))

        self._radio_frame = tk.Frame(self._q_frame, bg=BG)
        self._radio_frame.pack(anchor="w", fill="x")

        btn_row = tk.Frame(self._q_frame, bg=BG)
        btn_row.pack(fill="x", pady=(24, 0))

        self._status_label = tk.Label(
            btn_row, text="", bg=BG, fg=SUBTLE,
            font=tkfont.Font(family="Helvetica", size=10),
        )
        self._status_label.pack(side="left")

        self._next_btn = tk.Label(
            btn_row, text="Next  \u2192",
            bg="#cccccc", fg="#888888",
            font=tkfont.Font(family="Helvetica", size=12, weight="bold"),
            padx=22, pady=8,
        )
        self._next_btn.pack(side="right")

        # Results frame.
        self._r_frame = tk.Frame(self.root, bg=BG, padx=36, pady=24)

        tk.Label(
            self._r_frame, text="Your Recommendations",
            bg=BG, fg=FG,
            font=tkfont.Font(family="Helvetica", size=14, weight="bold"),
        ).pack(anchor="w", pady=(0, 12))

        _so = tk.Label(
            self._r_frame, text="Start Over",
            bg=ACCENT, fg="white",
            font=tkfont.Font(family="Helvetica", size=12, weight="bold"),
            padx=22, pady=8, cursor="hand2",
        )
        _so.bind("<Button-1>", lambda e: self._restart())
        _so.bind("<Enter>",    lambda e: _so.config(bg=ACTIVE))
        _so.bind("<Leave>",    lambda e: _so.config(bg=ACCENT))
        _so.pack(side="bottom", pady=(16, 0))

        self._results_text = tk.Text(
            self._r_frame, bg=BG, fg=FG,
            font=tkfont.Font(family="Helvetica", size=11),
            relief="flat", wrap="word",
            height=11, state="disabled",
        )
        self._results_text.pack(fill="both", expand=True)

        self._show_frame(self._q_frame)

    def _show_frame(self, frame):
        """Swap the visible content frame.

        Args:
            frame: The tk.Frame instance to make visible.
        """
        for f in (self._q_frame, self._r_frame):
            f.pack_forget()
        frame.pack(fill="both", expand=True)

    def _start_session(self):
        """Clear all state and begin a fresh question sequence."""
        list(prolog.query("retractall(known(_,_))"))
        self._answers = {}
        self._q_count = 0
        self._askable_queue = list(ASKABLES)
        self._show_frame(self._q_frame)
        self._advance()

    def _advance(self):
        """Move to the next relevant question, or finish if all are answered.

        Pops askables from the queue one at a time.  Any askable that
        _should_skip deems irrelevant is silently assigned its default value
        and skipped.  When the queue is empty, _finish is called.
        """
        while self._askable_queue:
            attr, opts = self._askable_queue.pop(0)
            if _should_skip(attr, self._answers):
                self._answers[attr] = _SKIP_DEFAULTS.get(attr, opts[-1])
                continue
            self._current_attr = attr
            self._q_count += 1
            question = QUESTION_TEXTS.get(attr, attr.replace('_', ' '))
            self._show_question(question, opts)
            return
        self._finish()

    def _set_next_enabled(self, enabled: bool):
        """Enable or disable the Next label-button.

        Args:
            enabled: True to activate the button with ACCENT colour;
                False to grey it out and ignore clicks.
        """
        if enabled:
            self._next_btn.config(bg=ACCENT, fg="white", cursor="hand2")
            self._next_btn.bind("<Button-1>", lambda e: self._submit_answer())
            self._next_btn.bind("<Enter>",    lambda e: self._next_btn.config(bg=ACTIVE))
            self._next_btn.bind("<Leave>",    lambda e: self._next_btn.config(bg=ACCENT))
        else:
            self._next_btn.config(bg="#cccccc", fg="#888888", cursor="")
            self._next_btn.unbind("<Button-1>")
            self._next_btn.unbind("<Enter>")
            self._next_btn.unbind("<Leave>")

    def _show_question(self, question_text: str, options: list):
        """Render a question with radio buttons on the question frame.

        Clears any previously rendered radio buttons, updates the question
        label, and disables the Next button until a selection is made.

        Args:
            question_text: The human-readable question string to display.
            options: List of option atom strings to render as radio buttons.
        """
        self._selected.set("")
        self._set_next_enabled(False)
        self._status_label.config(text=f"Question {self._q_count}")
        self._q_label.config(text=question_text)

        for widget in self._radio_frame.winfo_children():
            widget.destroy()

        for opt in options:
            rb = tk.Radiobutton(
                self._radio_frame,
                text=f"  {opt.replace('_', ' ')}",
                variable=self._selected,
                value=opt,
                bg=BG, fg=FG,
                activebackground=BG,
                font=tkfont.Font(family="Helvetica", size=12),
                command=lambda: self._set_next_enabled(True),
            )
            rb.pack(anchor="w", pady=3)

    def _submit_answer(self):
        """Record the user's choice and advance to the next question.

        Stores the selected value in _answers and calls _advance so the
        GUI moves on without any Prolog interaction at this stage.
        """
        chosen = self._selected.get()
        if not chosen:
            return
        self._answers[self._current_attr] = chosen
        self._set_next_enabled(False)
        self._advance()

    def _finish(self):
        """Show a loading label and schedule the Prolog query.

        Uses root.after so the label update is painted before the
        (briefly blocking) Prolog call runs on the main thread.
        """
        self._q_label.config(text="Finding your recommendations\u2026")
        self._status_label.config(text="")
        for widget in self._radio_frame.winfo_children():
            widget.destroy()
        self.root.update_idletasks()
        self.root.after(10, self._run_prolog)

    def _run_prolog(self):
        """Assert all collected answers and run all_recommendations/1.

        Each answer is asserted as known(attr, value) so that menuask/3
        in the KB reads from the cache and never calls read_menu_py/3.
        If no shop satisfies all constraints, falls back to a scored
        closest-match ranking so the user always sees a result.
        """
        for attr, val in self._answers.items():
            prolog.assertz(f"known({attr}, {val})")
        results = list(prolog.query("all_recommendations(L).", maxresult=1))
        shops = [str(s) for s in results[0]['L']] if results else []
        if shops:
            self._show_results(shops, exact=True)
        else:
            self._show_results(self._score_shops(), exact=False)

    def _score_shops(self):
        """Return all shops ranked by how many constraints they satisfy.

        Dietary requirement is treated as a hard primary sort key: all
        diet-compliant shops rank above every non-compliant shop regardless
        of how many other constraints the non-compliant shop satisfies.
        Within each dietary tier shops are ranked by the count of remaining
        satisfied constraints.  The known/2 facts must already be asserted
        before calling this.

        Returns:
            List of shop atom strings ordered from best to worst score,
            capped at the top 5.
        """
        all_shops_q = list(prolog.query("shop(S)."))
        all_shops = [str(r['S']) for r in all_shops_q]
        scored = []
        for shop in all_shops:
            diet_ok = bool(list(prolog.query(f"matches_diet({shop}).", maxresult=1)))
            other_score = sum(
                1 for pred, _ in _CONSTRAINT_LABELS
                if pred != "matches_diet"
                and list(prolog.query(f"{pred}({shop}).", maxresult=1))
            )
            # Tuple sort: diet_ok (1 beats 0) is primary, other_score secondary.
            scored.append(((1 if diet_ok else 0, other_score), shop))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [shop for _, shop in scored[:5]]

    def _missed_constraints(self, shop: str) -> list:
        """Return labels for every constraint the shop does not satisfy.

        The known/2 facts must already be asserted before calling this.

        Args:
            shop: Prolog atom string identifying the shop.

        Returns:
            List of human-readable constraint label strings for each
            matches_* predicate that returned False for this shop.
        """
        return [
            label
            for pred, label in _CONSTRAINT_LABELS
            if not list(prolog.query(f"{pred}({shop}).", maxresult=1))
        ]

    def _show_results(self, shops: list, exact: bool = True):
        """Display recommendation results and switch to the results frame.

        Always shows at least the closest-match shops; never shows a
        'no results' dead end.  When exact is False a note explains that
        these are the nearest matches rather than perfect ones.

        Args:
            shops: List of shop atom strings to display.
            exact: True when every shop satisfies all constraints; False
                when the list was produced by the scoring fallback.
        """
        self._show_frame(self._r_frame)
        self._results_text.config(state="normal")
        self._results_text.delete("1.0", "end")

        # Tag for missed-constraint lines: amber text on the dark background.
        self._results_text.tag_configure("missed", foreground="#f59e0b")

        if exact:
            self._results_text.insert("end", f"Found {len(shops)} perfect match(es):\n\n")
        else:
            self._results_text.insert(
                "end",
                "No shop matched every preference exactly.\n"
                "Here are the closest options:\n\n",
            )

        for i, shop in enumerate(shops, 1):
            explanation = explain_shop(shop)
            self._results_text.insert("end", f"{i}.  {explanation}\n")
            if not exact:
                missed = self._missed_constraints(shop)
                if missed:
                    self._results_text.insert(
                        "end",
                        f"    Missed: {', '.join(missed)}\n",
                        "missed",
                    )
            self._results_text.insert("end", "\n")

        self._results_text.config(state="disabled")

    def _restart(self):
        """Reset the session and start a new consultation."""
        self._start_session()


# Entry point.

def main():
    """Create the root window, launch RamenGUI, and enter the Tkinter event loop."""
    root = tk.Tk()
    RamenGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
