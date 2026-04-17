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
:- dynamic travel_band/2.      % travel_band(Shop, near|mid|far)

% Askables (menu-based)
% These return a VALUE, not yes/no.

budget(X)        :- menuask(budget, X, [low, medium, high]).
broth_pref(X)    :- menuask(broth_pref, X, [tonkotsu, shoyu, shio, miso, tsukemen, no_pref]).
rich_pref(X)     :- menuask(rich_pref, X, [light, medium, rich, no_pref]).
spice_tol(X)     :- menuask(spice_tol, X, [none, mild, spicy]).
diet_req(X)      :- menuask(diet_req, X, [none, vegetarian, halal]).
distance_tol(X)  :- menuask(distance_tol, X, [near, mid, any]).
wait_tol(X)      :- menuask(wait_tol, X, [short, medium, any]).
group_size(X)    :- menuask(group_size, X, [solo, small, group]).
open_late_req(X) :- menuask(open_late_req, X, [yes, no]).
seating_pref(X)  :- menuask(seating_pref, X, [bar, table, no_pref]).


% menuask/3 with memory (known/2)
% known(Attribute, Value) stores chosen value per attribute.
% Calls Python foreign predicate read_menu_py/3 when not known.


menuask(A, V, _Options) :-
    known(A, V),
    !.

menuask(A, V, Options) :-
    read_menu_py(A, Options, V),
    assertz(known(A, V)),
    !.


% Top goal

top_goal(Shop) :- recommend(Shop).

solve(Shop) :-
    retractall(known(_,_)),
    top_goal(Shop).

all_recommendations(List) :-
    findall(S, recommend(S), List).

% Recommendation rules

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
    matches_seating(Shop).

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

matches_open_late(Shop) :-
    open_late_req(no),
    !.
matches_open_late(Shop) :-
    open_late_req(yes),
    open_late(Shop, yes).

matches_budget(Shop) :-
    budget(B),
    price_level(Shop, B).

matches_broth(Shop) :-
    broth_pref(no_pref),
    !.
matches_broth(Shop) :-
    broth_pref(B),
    broth(Shop, B).

matches_richness(Shop) :-
    rich_pref(no_pref),
    !.
matches_richness(Shop) :-
    rich_pref(R),
    richness(Shop, R).

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

matches_group(Shop) :-
    group_size(solo),
    !. % solo can go anywhere
matches_group(Shop) :-
    group_size(small),
    (group_ok(Shop, small) ; group_ok(Shop, group)),
    !.
matches_group(Shop) :-
    group_size(group),
    group_ok(Shop, group).

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