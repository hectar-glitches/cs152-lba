import unittest
from app import prolog, atomize, explain_shop


# Helpers


ALL_ASKABLES = [
    "budget", "broth_pref", "rich_pref", "spice_tol",
    "diet_req", "distance_tol", "wait_tol", "group_size",
    "open_late_req", "seating_pref",
]

SHOP_PREDICATES = [
    "shop", "area", "station", "price_level", "broth", "richness",
    "spice", "diet", "open_late", "seating", "group_ok",
    "wait_level", "travel_band", "ramen_type", "jiro_style", "payment"
]


def set_known(**kwargs):
    """Assert known/2 facts so menuask/3 never prompts interactively."""
    for key, val in kwargs.items():
        prolog.assertz(f"known({key}, {val})")


def add_test_shop(shop_id, price_level="medium", broth="shoyu",
                  richness="medium", spice="none", diet="none",
                  open_late="no", seating="both", group_ok="group",
                  wait_level="short", travel_band="near",
                  ramen_type="ramen", jiro_style="no", payment="card_ok"):
    """Assert a complete shop fact bundle into Prolog."""
    prolog.assertz(f"shop({shop_id})")
    prolog.assertz(f"area({shop_id}, shinjuku)")
    prolog.assertz(f"station({shop_id}, shinjuku_station)")
    prolog.assertz(f"price_level({shop_id}, {price_level})")
    prolog.assertz(f"broth({shop_id}, {broth})")
    prolog.assertz(f"richness({shop_id}, {richness})")
    prolog.assertz(f"spice({shop_id}, {spice})")
    prolog.assertz(f"diet({shop_id}, {diet})")
    prolog.assertz(f"open_late({shop_id}, {open_late})")
    prolog.assertz(f"seating({shop_id}, {seating})")
    prolog.assertz(f"group_ok({shop_id}, {group_ok})")
    prolog.assertz(f"wait_level({shop_id}, {wait_level})")
    prolog.assertz(f"travel_band({shop_id}, {travel_band})")
    prolog.assertz(f"ramen_type({shop_id}, {ramen_type})")
    prolog.assertz(f"jiro_style({shop_id}, {jiro_style})")
    prolog.assertz(f"payment({shop_id}, {payment})")


def get_recommendations():
    results = list(prolog.query("all_recommendations(L).", maxresult=1))
    if not results:
        return []
    return [str(s) for s in results[0]["L"]]



# atomize() unit tests


class TestAtomize(unittest.TestCase):

    def test_lowercases_input(self):
        """atomize() should convert all characters to lowercase."""
        self.assertEqual(atomize("Tokyo"), "tokyo")

    def test_spaces_become_underscores(self):
        """atomize() should replace spaces with underscores."""
        self.assertEqual(atomize("Tokyo Station"), "tokyo_station")

    def test_ampersand_becomes_and(self):
        """atomize() should replace '&' with 'and'."""
        self.assertEqual(atomize("salt & pepper"), "salt_and_pepper")

    def test_empty_string_returns_unknown(self):
        """atomize() should return 'unknown' for an empty input string."""
        self.assertEqual(atomize(""), "unknown")

    def test_strips_special_characters(self):
        """atomize() should strip non-alphanumeric characters."""
        self.assertEqual(atomize("Ichiran!"), "ichiran")

    def test_collapses_repeated_underscores(self):
        """atomize() should collapse multiple spaces into a single underscore."""
        self.assertEqual(atomize("a  b"), "a_b")

    def test_strips_leading_trailing_whitespace(self):
        """atomize() should strip leading and trailing whitespace."""
        self.assertEqual(atomize("  ramen  "), "ramen")


# Recommendation rule tests

class TestRecommendations(unittest.TestCase):

    def setUp(self):
        # Clean slate before every test
        list(prolog.query("retractall(known(_,_))"))
        for pred in SHOP_PREDICATES:
            list(prolog.query(f"retractall({pred}(test_shop,_))"))
        list(prolog.query("retractall(shop(test_shop))"))

    def tearDown(self):
        list(prolog.query("retractall(known(_,_))"))
        for pred in SHOP_PREDICATES:
            list(prolog.query(f"retractall({pred}(test_shop,_))"))
        list(prolog.query("retractall(shop(test_shop))"))

    def _default_prefs(self, **overrides):
        """Return a full set of no-restriction preferences, with optional overrides."""
        defaults = dict(
            budget="medium",
            broth_pref="no_pref",
            rich_pref="no_pref",
            spice_tol="spicy",
            diet_req="none",
            distance_tol="any",
            wait_tol="any",
            group_size="solo",
            open_late_req="no",
            seating_pref="no_pref",
            ramen_type_pref="either",
            hunger_level="regular",
            payment_pref="no_pref",
        )
        defaults.update(overrides)
        return defaults

    # --- Budget ---

    def test_matching_budget_recommends_shop(self):
        """A shop whose price level matches the user's budget should be recommended."""
        add_test_shop("test_shop", price_level="medium")
        set_known(**self._default_prefs(budget="medium"))
        self.assertIn("test_shop", get_recommendations())

    def test_mismatched_budget_excludes_shop(self):
        """A shop whose price level differs from the user's budget should be excluded."""
        add_test_shop("test_shop", price_level="high")
        set_known(**self._default_prefs(budget="low"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Broth ---

    def test_no_broth_pref_accepts_any_broth(self):
        """With no broth preference, a shop with any broth type should be recommended."""
        add_test_shop("test_shop", broth="tonkotsu")
        set_known(**self._default_prefs(broth_pref="no_pref"))
        self.assertIn("test_shop", get_recommendations())

    def test_specific_broth_pref_matches(self):
        """A shop whose broth type matches the user's preference should be recommended."""
        add_test_shop("test_shop", broth="shoyu")
        set_known(**self._default_prefs(broth_pref="shoyu"))
        self.assertIn("test_shop", get_recommendations())

    def test_specific_broth_pref_excludes_wrong_broth(self):
        """A shop whose broth type does not match the user's preference should be excluded."""
        add_test_shop("test_shop", broth="miso")
        set_known(**self._default_prefs(broth_pref="shoyu"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Spice ---

    def test_spicy_tolerance_accepts_any_spice(self):
        """A user who tolerates spicy food should be matched with a spicy shop."""
        add_test_shop("test_shop", spice="spicy")
        set_known(**self._default_prefs(spice_tol="spicy"))
        self.assertIn("test_shop", get_recommendations())

    def test_mild_tolerance_accepts_mild(self):
        """A user with mild spice tolerance should be matched with a mild shop."""
        add_test_shop("test_shop", spice="mild")
        set_known(**self._default_prefs(spice_tol="mild"))
        self.assertIn("test_shop", get_recommendations())

    def test_mild_tolerance_accepts_none(self):
        """A user with mild spice tolerance should also be matched with a non-spicy shop."""
        add_test_shop("test_shop", spice="none")
        set_known(**self._default_prefs(spice_tol="mild"))
        self.assertIn("test_shop", get_recommendations())

    def test_mild_tolerance_rejects_spicy(self):
        """A user with mild spice tolerance should not be matched with a spicy shop."""
        add_test_shop("test_shop", spice="spicy")
        set_known(**self._default_prefs(spice_tol="mild"))
        self.assertNotIn("test_shop", get_recommendations())

    def test_no_spice_tolerance_rejects_mild(self):
        """A user with no spice tolerance should not be matched with even a mildly spicy shop."""
        add_test_shop("test_shop", spice="mild")
        set_known(**self._default_prefs(spice_tol="none"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Diet ---

    def test_no_diet_req_accepts_any_shop(self):
        """A user with no dietary restrictions should be matched with any shop."""
        add_test_shop("test_shop", diet="none")
        set_known(**self._default_prefs(diet_req="none"))
        self.assertIn("test_shop", get_recommendations())

    def test_vegetarian_req_accepts_vegetarian_shop(self):
        """A vegetarian user should be matched with a shop marked as vegetarian."""
        add_test_shop("test_shop", diet="vegetarian")
        set_known(**self._default_prefs(diet_req="vegetarian"))
        self.assertIn("test_shop", get_recommendations())

    def test_vegetarian_req_accepts_veg_friendly_shop(self):
        """A vegetarian user should also be matched with a shop marked as veg_friendly."""
        add_test_shop("test_shop", diet="veg_friendly")
        set_known(**self._default_prefs(diet_req="vegetarian"))
        self.assertIn("test_shop", get_recommendations())

    def test_vegetarian_req_rejects_non_vegetarian(self):
        """A vegetarian user should not be matched with a shop that has no vegetarian options."""
        add_test_shop("test_shop", diet="none")
        set_known(**self._default_prefs(diet_req="vegetarian"))
        self.assertNotIn("test_shop", get_recommendations())

    def test_halal_req_accepts_halal_shop(self):
        """A user requiring halal food should be matched with a halal-certified shop."""
        add_test_shop("test_shop", diet="halal")
        set_known(**self._default_prefs(diet_req="halal"))
        self.assertIn("test_shop", get_recommendations())

    def test_halal_req_rejects_non_halal(self):
        """A user requiring halal food should not be matched with a non-halal shop."""
        add_test_shop("test_shop", diet="none")
        set_known(**self._default_prefs(diet_req="halal"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Open late ---

    def test_late_req_accepts_open_late_shop(self):
        """A user who needs late-night dining should be matched with a shop open after 10pm."""
        add_test_shop("test_shop", open_late="yes")
        set_known(**self._default_prefs(open_late_req="yes"))
        self.assertIn("test_shop", get_recommendations())

    def test_late_req_rejects_not_open_late(self):
        """A user who needs late-night dining should not be matched with a shop that closes early."""
        add_test_shop("test_shop", open_late="no")
        set_known(**self._default_prefs(open_late_req="yes"))
        self.assertNotIn("test_shop", get_recommendations())

    def test_no_late_req_accepts_any_hours(self):
        """A user with no late-night requirement should be matched regardless of closing time."""
        add_test_shop("test_shop", open_late="no")
        set_known(**self._default_prefs(open_late_req="no"))
        self.assertIn("test_shop", get_recommendations())

    # --- Distance ---

    def test_any_distance_accepts_far_shop(self):
        """A user willing to travel any distance should be matched with even a far shop."""
        add_test_shop("test_shop", travel_band="far")
        set_known(**self._default_prefs(distance_tol="any"))
        self.assertIn("test_shop", get_recommendations())

    def test_mid_distance_accepts_near_shop(self):
        """A user willing to travel mid distance should also be matched with a nearby shop."""
        add_test_shop("test_shop", travel_band="near")
        set_known(**self._default_prefs(distance_tol="mid"))
        self.assertIn("test_shop", get_recommendations())

    def test_mid_distance_rejects_far_shop(self):
        """A user willing to travel only mid distance should not be matched with a far shop."""
        add_test_shop("test_shop", travel_band="far")
        set_known(**self._default_prefs(distance_tol="mid"))
        self.assertNotIn("test_shop", get_recommendations())

    def test_near_only_rejects_mid_shop(self):
        """A user who only wants nearby shops should not be matched with a mid-distance shop."""
        add_test_shop("test_shop", travel_band="mid")
        set_known(**self._default_prefs(distance_tol="near"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Wait time ---

    def test_any_wait_accepts_long_wait(self):
        """A user tolerant of any wait time should be matched with a shop with a long queue."""
        add_test_shop("test_shop", wait_level="long")
        set_known(**self._default_prefs(wait_tol="any"))
        self.assertIn("test_shop", get_recommendations())

    def test_short_wait_only_rejects_medium_wait(self):
        """A user who only accepts a short wait should not be matched with a medium-wait shop."""
        add_test_shop("test_shop", wait_level="medium")
        set_known(**self._default_prefs(wait_tol="short"))
        self.assertNotIn("test_shop", get_recommendations())

    def test_medium_wait_tol_accepts_short_wait(self):
        """A user tolerant of a medium wait should also be matched with a short-wait shop."""
        add_test_shop("test_shop", wait_level="short")
        set_known(**self._default_prefs(wait_tol="medium"))
        self.assertIn("test_shop", get_recommendations())

    # --- Group size ---

    def test_solo_accepted_everywhere(self):
        """A solo diner should be matched with any shop regardless of group policy."""
        add_test_shop("test_shop", group_ok="solo")
        set_known(**self._default_prefs(group_size="solo"))
        self.assertIn("test_shop", get_recommendations())

    def test_small_group_accepts_group_ok_shop(self):
        """A small group should be matched with a shop that accommodates larger groups."""
        add_test_shop("test_shop", group_ok="group")
        set_known(**self._default_prefs(group_size="small"))
        self.assertIn("test_shop", get_recommendations())

    def test_large_group_rejects_solo_only_shop(self):
        """A large group should not be matched with a shop that only caters to solo diners."""
        add_test_shop("test_shop", group_ok="solo")
        set_known(**self._default_prefs(group_size="group"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Seating ---

    def test_no_seating_pref_accepts_any_seating(self):
        """A user with no seating preference should be matched with any seating type."""
        add_test_shop("test_shop", seating="bar")
        set_known(**self._default_prefs(seating_pref="no_pref"))
        self.assertIn("test_shop", get_recommendations())

    def test_bar_pref_accepts_both_seating(self):
        """A user who wants bar seating should be matched with a shop offering both seating types."""
        add_test_shop("test_shop", seating="both")
        set_known(**self._default_prefs(seating_pref="bar"))
        self.assertIn("test_shop", get_recommendations())

    def test_table_pref_rejects_bar_only(self):
        """A user who wants table seating should not be matched with a bar-only shop."""
        add_test_shop("test_shop", seating="bar")
        set_known(**self._default_prefs(seating_pref="table"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Ramen type ---

    def test_either_ramen_type_accepts_any(self):
        """A user happy with either ramen or tsukemen should be matched with any shop."""
        add_test_shop("test_shop", ramen_type="tsukemen")
        set_known(**self._default_prefs(ramen_type_pref="either"))
        self.assertIn("test_shop", get_recommendations())

    def test_tsukemen_pref_accepts_tsukemen_shop(self):
        """A user who wants tsukemen should be matched with a tsukemen-only shop."""
        add_test_shop("test_shop", ramen_type="tsukemen")
        set_known(**self._default_prefs(ramen_type_pref="tsukemen"))
        self.assertIn("test_shop", get_recommendations())

    def test_tsukemen_pref_accepts_both_type_shop(self):
        """A user who wants tsukemen should be matched with a shop that serves both types."""
        add_test_shop("test_shop", ramen_type="both")
        set_known(**self._default_prefs(ramen_type_pref="tsukemen"))
        self.assertIn("test_shop", get_recommendations())

    def test_tsukemen_pref_rejects_ramen_only_shop(self):
        """A user who wants tsukemen should not be matched with a ramen-only shop."""
        add_test_shop("test_shop", ramen_type="ramen")
        set_known(**self._default_prefs(ramen_type_pref="tsukemen"))
        self.assertNotIn("test_shop", get_recommendations())

    def test_ramen_pref_rejects_tsukemen_only_shop(self):
        """A user who wants regular ramen should not be matched with a tsukemen-only shop."""
        add_test_shop("test_shop", ramen_type="tsukemen")
        set_known(**self._default_prefs(ramen_type_pref="ramen"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Hunger level (jiro style) ---

    def test_regular_hunger_accepts_any_shop(self):
        """A user with a regular appetite should be matched with any shop."""
        add_test_shop("test_shop", jiro_style="no")
        set_known(**self._default_prefs(hunger_level="regular"))
        self.assertIn("test_shop", get_recommendations())

    def test_jiro_hunger_accepts_jiro_shop(self):
        """A very hungry user wanting jiro-style should be matched with a jiro-serving shop."""
        add_test_shop("test_shop", jiro_style="yes")
        set_known(**self._default_prefs(hunger_level="jiro"))
        self.assertIn("test_shop", get_recommendations())

    def test_jiro_hunger_rejects_non_jiro_shop(self):
        """A very hungry user wanting jiro-style should not be matched with a regular-portion shop."""
        add_test_shop("test_shop", jiro_style="no")
        set_known(**self._default_prefs(hunger_level="jiro"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- Payment preference ---

    def test_no_payment_pref_accepts_cash_only_shop(self):
        """A user with no payment preference should be matched with a cash-only shop."""
        add_test_shop("test_shop", payment="cash_only")
        set_known(**self._default_prefs(payment_pref="no_pref"))
        self.assertIn("test_shop", get_recommendations())

    def test_card_required_accepts_card_ok_shop(self):
        """A user who needs to pay by card should be matched with a card-accepting shop."""
        add_test_shop("test_shop", payment="card_ok")
        set_known(**self._default_prefs(payment_pref="card_ok"))
        self.assertIn("test_shop", get_recommendations())

    def test_card_required_rejects_cash_only_shop(self):
        """A user who needs to pay by card should not be matched with a cash-only shop."""
        add_test_shop("test_shop", payment="cash_only")
        set_known(**self._default_prefs(payment_pref="card_ok"))
        self.assertNotIn("test_shop", get_recommendations())

    # --- No matches ---

    def test_no_shops_returns_empty_list(self):
        """When no shops are loaded, all_recommendations should return an empty list."""
        set_known(**self._default_prefs())
        self.assertEqual(get_recommendations(), [])

    # --- Multiple constraints together ---

    def test_combined_filters_all_must_pass(self):
        """A shop that passes some but not all filters should not be recommended."""
        # Shop passes budget and broth but fails on spice
        add_test_shop("test_shop", price_level="low", broth="shio", spice="spicy")
        set_known(**self._default_prefs(budget="low", broth_pref="shio", spice_tol="none"))
        self.assertNotIn("test_shop", get_recommendations())


# ---------------------------------------------------------------------------
# Explanation output tests
# ---------------------------------------------------------------------------

class TestExplanation(unittest.TestCase):

    def setUp(self):
        list(prolog.query("retractall(known(_,_))"))
        for pred in SHOP_PREDICATES:
            list(prolog.query(f"retractall({pred}(explain_shop,_))"))
        list(prolog.query("retractall(shop(explain_shop))"))

    def tearDown(self):
        list(prolog.query("retractall(known(_,_))"))
        for pred in SHOP_PREDICATES:
            list(prolog.query(f"retractall({pred}(explain_shop,_))"))
        list(prolog.query("retractall(shop(explain_shop))"))

    def test_explanation_contains_shop_name(self):
        """explain_shop() output should include the shop's name."""
        add_test_shop("explain_shop")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("explain shop", result)

    def test_explanation_contains_broth(self):
        """explain_shop() output should mention the broth type."""
        add_test_shop("explain_shop", broth="tonkotsu")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("tonkotsu", result)

    def test_explanation_contains_budget(self):
        """explain_shop() output should mention the price level."""
        add_test_shop("explain_shop", price_level="low")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("low", result)

    def test_explanation_mentions_open_late(self):
        """explain_shop() output should say 'open late' for a late-night shop."""
        add_test_shop("explain_shop", open_late="yes")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("open late", result)

    def test_explanation_omits_open_late_when_not_applicable(self):
        """explain_shop() output should not mention 'open late' for a shop that closes early."""
        add_test_shop("explain_shop", open_late="no")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertNotIn("open late", result)

    def test_explanation_mentions_jiro(self):
        """explain_shop() output should mention jiro-style portions when applicable."""
        add_test_shop("explain_shop", jiro_style="yes")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("jiro", result)

    def test_explanation_mentions_regular_portions_when_not_jiro(self):
        """explain_shop() output should say 'regular portions' for a non-jiro shop."""
        add_test_shop("explain_shop", jiro_style="no")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("regular portions", result)

    def test_explanation_mentions_no_spice(self):
        """explain_shop() output should say 'no spice' for a shop with no spice."""
        add_test_shop("explain_shop", spice="none")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("no spice", result)

    def test_explanation_mentions_spice_level_when_spicy(self):
        """explain_shop() output should mention the spice level for a spicy shop."""
        add_test_shop("explain_shop", spice="spicy")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("spicy spice", result)

    def test_explanation_starts_with_recommended(self):
        """explain_shop() output should always start with 'Recommended'."""
        add_test_shop("explain_shop")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertTrue(result.startswith("Recommended"))

    def test_explanation_contains_station(self):
        """explain_shop() output should mention the station name."""
        add_test_shop("explain_shop")
        result = explain_shop("explain_shop")
        print(f"\n[query] explain_shop('explain_shop') -> {result}")
        self.assertIn("station", result)


if __name__ == "__main__":
    unittest.main()
