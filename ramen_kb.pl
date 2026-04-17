% Tokyo Ramen Expert System KB

:- use_module(library(lists)).


:- dynamic known/2.
:- dynamic shop/1.
:- dynamic area/2.
:- dynamic station/2.
:- dynamic price_level/2.      % price_level(Shop, low|medium|high)
:- dynamic broth/2.            % broth(Shop, tonkotsu|shoyu|shio|miso|tsukemen|other)
:- dynamic richness/2.         % richness(Shop, light|medium|rich)
:- dynamic spice/2.            % spice(Shop, none|mild|spicy)
:- dynamic diet/2.             % diet(Shop, none|vegetarian|halal|veg_friendly)
:- dynamic open_late/2.        % open_late(Shop, yes|no)
:- dynamic seating/2.          % seating(Shop, bar|table|both)
:- dynamic group_ok/2.         % group_ok(Shop, solo|small|group)
:- dynamic wait_level/2.       % wait_level(Shop, short|medium|long)
:- dynamic travel_band/2.      % travel_band(Shop, near|mid|far):- dynamic ramen_type/2.       % ramen_type(Shop, ramen|tsukemen|both)
:- dynamic jiro_style/2.       % jiro_style(Shop, yes|no)
:- dynamic payment/2.          % payment(Shop, cash_only|card_ok)
% ASKABLES
% Each predicate below prompts the user for one preference via menuask/3.
% They bind X to the user's chosen value (not a yes/no flag).

budget(X)        :- menuask(budget, X, [low, medium, high]).
broth_pref(X)    :- menuask(broth_pref, X, [tonkotsu, shoyu, shio, miso, tsukemen, no_pref]).
rich_pref(X)     :- menuask(rich_pref, X, [light, medium, rich, no_pref]).
spice_tol(X)     :- menuask(spice_tol, X, [none, mild, spicy]).
diet_req(X)      :- menuask(diet_req, X, [none, vegetarian, halal]).
distance_tol(X)  :- menuask(distance_tol, X, [near, mid, any]).
wait_tol(X)      :- menuask(wait_tol, X, [short, medium, any]).
group_size(X)    :- menuask(group_size, X, [solo, small, group]).
open_late_req(X)    :- menuask(open_late_req, X, [yes, no]).
seating_pref(X)    :- menuask(seating_pref, X, [bar, table, no_pref]).
ramen_type_pref(X) :- menuask(ramen_type_pref, X, [ramen, tsukemen, either]).
hunger_level(X)    :- menuask(hunger_level, X, [jiro, regular]).
payment_pref(X)    :- menuask(payment_pref, X, [card_ok, no_pref]).


% MENUASK/3  —  memoised user-input predicate
%
% menuask(Attribute, Value, Options)
%   1. If the user already answered this question (known/2 fact exists),
%      unify Value with the cached answer and cut — no re-prompting.
%   2. Otherwise, delegate to the Python foreign predicate read_menu_py/3
%      which displays the numbered menu and reads the selection, then
%      cache the result with assertz(known(Attribute, Value)) for future
%      calls within the same session.

menuask(A, V, _Options) :-
    known(A, V),
    !.

menuask(A, V, Options) :-
    read_menu_py(A, Options, V),
    assertz(known(A, V)),
    !.


% ENTRY POINTS
%
% top_goal(Shop)  — succeeds (possibly on backtracking) for each Shop
%                   that satisfies all user preferences.
%
% solve(Shop)     — clears any cached answers from a previous run, then
%                   invokes top_goal/1 so the user is asked fresh questions.
%
% all_recommendations(List) — collects every matching shop into List in
%                   one shot using findall/3 (used by the Python front-end
%                   to display the full result set).

top_goal(Shop) :- recommend(Shop).

solve(Shop) :-
    retractall(known(_,_)),
    top_goal(Shop).

all_recommendations(List) :-
    findall(S, recommend(S), List).

% CORE RECOMMENDATION RULE
%
% recommend(Shop) succeeds when Shop is a known shop AND it passes every
% constraint check below.  Constraints are ordered cheapest-first:
% hard filters (diet, late-night) come before preference filters so we
% fail fast on shops that can never satisfy a requirement.

recommend(Shop) :-
    shop(Shop),
    matches_diet(Shop),
    matches_open_late(Shop),
    matches_budget(Shop),
    matches_broth(Shop),
    matches_richness(Shop),
    matches_spice(Shop),
    matches_distance(Shop),
    matches_wait(Shop),
    matches_group(Shop),
    matches_seating(Shop),
    matches_ramen_type(Shop),
    matches_hunger(Shop),
    matches_payment(Shop).

% matches_diet(Shop)
%   No dietary restriction: any shop passes.
%   Vegetarian: accept shops marked vegetarian or veg_friendly.
%   Halal: only shops explicitly marked halal pass.
matches_diet(Shop) :-
    diet_req(none),
    !.
matches_diet(Shop) :-
    diet_req(vegetarian),
    (diet(Shop, vegetarian) ; diet(Shop, veg_friendly)),
    !.
matches_diet(Shop) :-
    diet_req(halal),
    diet(Shop, halal),
    !.

% matches_open_late(Shop)
%   User doesn't need late hours: any shop passes.
%   User needs late hours: shop must have open_late(Shop, yes).
matches_open_late(Shop) :-
    open_late_req(no),
    !.
matches_open_late(Shop) :-
    open_late_req(yes),
    open_late(Shop, yes).

% matches_budget(Shop)
%   Shop's price level must exactly match the user's budget choice
%   (low / medium / high).  No tolerance range — strict equality.
matches_budget(Shop) :-
    budget(B),
    price_level(Shop, B).

% matches_broth(Shop)
%   no_pref: skip the broth check entirely.
%   Otherwise, the shop's broth type must match the user's preference.
matches_broth(Shop) :-
    broth_pref(no_pref),
    !.
matches_broth(Shop) :-
    broth_pref(B),
    broth(Shop, B).

% matches_richness(Shop)
%   no_pref: skip the richness check.
%   Otherwise, the shop's broth richness must match (light/medium/rich).
matches_richness(Shop) :-
    rich_pref(no_pref),
    !.
matches_richness(Shop) :-
    rich_pref(R),
    richness(Shop, R).

% matches_spice(Shop)
%   spicy tolerance: any spice level is acceptable.
%   mild tolerance : shop must be none or mild (not spicy).
%   none tolerance : shop must have no spice at all.
matches_spice(Shop) :-
    spice_tol(spicy),
    !.
matches_spice(Shop) :-
    spice_tol(mild),
    (spice(Shop, none) ; spice(Shop, mild)),
    !.
matches_spice(Shop) :-
    spice_tol(none),
    spice(Shop, none).

% matches_distance(Shop)
%   any tolerance: distance doesn't matter, all shops pass.
%   mid tolerance : shop must be near or mid distance.
%   near only     : shop must be in the near travel band.
matches_distance(Shop) :-
    distance_tol(any),
    !.
matches_distance(Shop) :-
    distance_tol(mid),
    (travel_band(Shop, near) ; travel_band(Shop, mid)),
    !.
matches_distance(Shop) :-
    distance_tol(near),
    travel_band(Shop, near).

% matches_wait(Shop)
%   any tolerance : queue length doesn't matter, all shops pass.
%   medium tolerance: shop's typical wait must be short or medium.
%   short only    : shop must have a short wait (no long queues).
matches_wait(Shop) :-
    wait_tol(any),
    !.
matches_wait(Shop) :-
    wait_tol(medium),
    (wait_level(Shop, short) ; wait_level(Shop, medium)),
    !.
matches_wait(Shop) :-
    wait_tol(short),
    wait_level(Shop, short).

% matches_group(Shop)
%   solo : a single diner is welcome everywhere, skip check.
%   small: shop must accommodate small groups or larger groups.
%   group: shop must explicitly support larger group seatings.
matches_group(Shop) :-
    group_size(solo),
    !.
matches_group(Shop) :-
    group_size(small),
    (group_ok(Shop, small) ; group_ok(Shop, group)),
    !.
matches_group(Shop) :-
    group_size(group),
    group_ok(Shop, group).

% matches_seating(Shop)
%   no_pref: seating style doesn't matter, skip check.
%   bar    : shop must have counter/bar seating or both types.
%   table  : shop must have table seating or both types.
matches_seating(Shop) :-
    seating_pref(no_pref),
    !.
matches_seating(Shop) :-
    seating_pref(bar),
    (seating(Shop, bar) ; seating(Shop, both)),
    !.
matches_seating(Shop) :-
    seating_pref(table),
    (seating(Shop, table) ; seating(Shop, both)).

% matches_ramen_type(Shop)
%   either   : user is happy with ramen or tsukemen, skip check.
%   ramen    : shop must serve regular ramen or both styles.
%   tsukemen : shop must serve tsukemen or both styles.
matches_ramen_type(Shop) :-
    ramen_type_pref(either),
    !.
matches_ramen_type(Shop) :-
    ramen_type_pref(ramen),
    (ramen_type(Shop, ramen) ; ramen_type(Shop, both)),
    !.
matches_ramen_type(Shop) :-
    ramen_type_pref(tsukemen),
    (ramen_type(Shop, tsukemen) ; ramen_type(Shop, both)).

% matches_hunger(Shop)
%   regular  : user wants a normal portion; any shop passes.
%   jiro     : user wants a jiro-style mega portion; shop must offer it.
matches_hunger(Shop) :-
    hunger_level(regular),
    !.
matches_hunger(Shop) :-
    hunger_level(jiro),
    jiro_style(Shop, yes).

% matches_payment(Shop)
%   no_pref  : user is fine paying cash; any shop passes.
%   card_ok  : user needs to pay by card; shop must accept cards.
matches_payment(Shop) :-
    payment_pref(no_pref),
    !.
matches_payment(Shop) :-
    payment_pref(card_ok),
    payment(Shop, card_ok).