# CS152 LBA — Tokyo Ramen Expert System

A small Prolog expert system that recommends Tokyo ramen shops based on
your preferences (broth, richness, spice, diet, distance, budget, etc.).

## Run

```bash
pip install pyswip
python app.py
```

Edit `data/ramen_shops.csv` to add shops, or `ramen_kb.pl` to change logic/rules.

## Data

`data/ramen_shops.csv` — **64 shops**, 8 per neighborhood across:
Shinjuku · Shibuya · Ginza · Akihabara · Ueno · Shinagawa · Roppongi · Asakusa.

### Columns

| Group       | Columns |
| ----------- | ------- |
| Identity    | `shop_id`, `name`, `address`, `latitude`, `longitude` |
| Location    | `area`, `station`, `travel_band` |
| KB facts    | `price_level`, `broth`, `richness`, `spice`, `diet`, `open_late`, `seating`, `group_ok`, `wait_level`, `ramen_type`, `jiro_style`, `payment` |

`app.py` reads only the KB-fact columns via `DictReader`; the identity /
location columns are kept for human review and map rendering.

### Vocabularies (must match `ramen_kb.pl`)

| Field       | Values |
| ----------- | ------ |
| `price_level` | low · medium · high |
| `broth`       | tonkotsu · shoyu · shio · miso · tsukemen · other |
| `richness`    | light · medium · rich |
| `spice`       | none · mild · spicy |
| `diet`        | none · vegetarian · halal · veg_friendly |
| `open_late`   | yes · no |
| `seating`     | bar · table · both |
| `group_ok`    | solo · small · group |
| `wait_level`  | short · medium · long |
| `travel_band` | near · mid · far |
| `ramen_type`  | ramen · tsukemen · both |
| `jiro_style`  | yes · no |
| `payment`     | cash_only · card_ok |

### Sample (one shop per area, broth-diverse)

| Area       | Shop | Broth | Richness | Spice | Price | Diet |
| ---------- | ---- | ----- | -------- | ----- | ----- | ---- |
| Akihabara  | Kyushu Jangara Akihabara | tonkotsu | rich   | spicy | medium | none |
| Asakusa    | HALAL RAMEN & WAGYU「SAMURAI SOUL」 | shoyu | medium | none  | low    | halal |
| Ginza      | Ippudo | miso | rich | spicy | medium | none |
| Roppongi   | 函館麺や 一文字PREMIUM 虎ノ門店 | shio | light | spicy | low | none |
| Shibuya    | Tsujita Ebisu | tsukemen | medium | none | low | none |
| Shinagawa  | Chisui Halal Lanzhou Beef Ramen | other | medium | none | medium | halal |
| Shinjuku   | ICHIRAN Shinjuku Station Central East Exit | tonkotsu | rich | none | medium | none |
| Ueno       | らぁ麺はやし田上野御徒町 | shoyu | medium | none | medium | none |

## Rebuilding `data/ramen_shops.csv`

```bash
export GOOGLE_MAPS_API_KEY=...
python build_kb_csv.py 8     # 8 shops per area
```

`build_kb_csv.py` calls Google Places (legacy Text Search) with
**broth-specific queries per area** (`"tonkotsu ramen in Shibuya"`, etc.),
so the query term is the ground-truth label for each returned shop's
`broth`. Targeted queries also populate `diet=halal`, `spice=spicy`, and
`jiro_style=yes`.

Fields Google does not expose (`seating`, `group_ok`, `payment`, and some
values of `spice`/`price_level`) are filled by a **seeded weighted
sampler** keyed on `shop_id` — values are plausible and the output is
deterministic across runs. Review `data/ramen_shops.csv` manually if you
want to overwrite any inferred/sampled values with real data.
