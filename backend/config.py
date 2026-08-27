"""
config.py — Authoritative game constants and rule tables.
All numeric constants live here; no module should duplicate them.
"""

# ── Time ──────────────────────────────────────────────────────────────────────
TOTAL_TURNS: int = 720
TURNS_PER_DAY: int = 24
TOTAL_DAYS: int = TOTAL_TURNS // TURNS_PER_DAY          # 30

# ── Market ────────────────────────────────────────────────────────────────────
MAX_ORDERS: int = 10          # maximum SELL actions per turn
PRICE_FLOOR: float = 1.0      # no product can sell below $1

# ── Workers / Inventory ───────────────────────────────────────────────────────
WORKER_CAPACITY: int = 10     # units a single worker can carry
SHED_CAPACITY: int = 100      # total shared shed units (seeds excluded)
INITIAL_WORKERS: int = 2
INITIAL_CASH: float = 500.0

# ── Board ─────────────────────────────────────────────────────────────────────
BOARD_ROWS: int = 5
BOARD_COLS: int = 5

# ── Endgame ───────────────────────────────────────────────────────────────────
ENDGAME_THRESHOLD: int = 670  # turn at which "endgame mode" activates
MAX_REPLANS: int = 5          # counterfactual replanning hard bound

# ── Hiring cost progression (cost of Nth hire that day, 0-indexed) ────────────
HIRE_COSTS: list[float] = [34.0, 50.0, 75.0, 110.0, 160.0]

# ── Crop rules ────────────────────────────────────────────────────────────────
# Each crop: seed_cost, maturity_turns, yield_units, ongoing_interval,
#            one_time (bool), water_required_every_n_turns, max_missed_water,
#            fertilizer_window_start, fertilizer_window_end (crop age in turns),
#            fertilizer_yield_bonus, base_sell_price
CROP_RULES: dict = {
    "WHEAT": {
        "seed_cost": 10.0,
        "maturity_turns": 48,        # 2 days
        "yield_units": 5,
        "ongoing_interval": None,    # one-time crop
        "one_time": True,
        "water_every": 1,            # every turn
        "max_missed_water": 2,       # dies after 2 missed consecutive waterings
        "fertilizer_window": (0, 24),  # turns 0-24 of crop age
        "fertilizer_bonus": 2,       # +2 units at harvest
        "base_sell_price": 8.0,
    },
    "TOMATO": {
        "seed_cost": 15.0,
        "maturity_turns": 72,        # 3 days
        "yield_units": 3,
        "ongoing_interval": 24,      # produces every 1 day after maturity
        "one_time": False,
        "water_every": 1,
        "max_missed_water": 2,
        "fertilizer_window": (0, 36),
        "fertilizer_bonus": 1,
        "base_sell_price": 10.0,
    },
    "STRAWBERRY": {
        "seed_cost": 12.0,
        "maturity_turns": 48,        # 2 days
        "yield_units": 2,
        "ongoing_interval": 12,      # produces every 12 turns after maturity
        "one_time": False,
        "water_every": 1,
        "max_missed_water": 2,
        "fertilizer_window": (0, 24),
        "fertilizer_bonus": 1,
        "base_sell_price": 12.0,
    },
}

# ── Animal rules ──────────────────────────────────────────────────────────────
ANIMAL_RULES: dict = {
    "COW": {
        "cost": 200.0,
        "structure": "BARN",
        "structure_cost": 150.0,
        "feed_cost_per_turn": 2.0,
        "product": "MILK",
        "product_units": 2,
        "product_interval": 24,      # every day
        "sell_price": 15.0,
        "max_missed_feed": 2,
    },
    "CHICKEN": {
        "cost": 50.0,
        "structure": "COOP",
        "structure_cost": 80.0,
        "feed_cost_per_turn": 0.5,
        "product": "EGGS",
        "product_units": 3,
        "product_interval": 12,      # every 12 turns
        "sell_price": 5.0,
        "max_missed_feed": 2,
    },
}

# ── Market price-decay rules ──────────────────────────────────────────────────
# Price of the Nth unit sold = max(PRICE_FLOOR, base_price - decay_per_unit * (N-1))
MARKET_DECAY_PER_UNIT: float = 0.5   # each additional unit sold lowers price by $0.50

# ── Demand events ─────────────────────────────────────────────────────────────
# Demand boosts at day boundaries (day → extra demand units consumed from market)
DEMAND_EVENTS: list[dict] = [
    {"day": 10, "product": "WHEAT",      "units": 10, "source": "town"},
    {"day": 10, "product": "TOMATO",     "units": 5,  "source": "town"},
    {"day": 20, "product": "WHEAT",      "units": 15, "source": "town"},
    {"day": 20, "product": "STRAWBERRY", "units": 8,  "source": "town"},
    {"day": 5,  "product": "MILK",       "units": 4,  "source": "shop"},
    {"day": 10, "product": "EGGS",       "units": 6,  "source": "shop"},
    {"day": 15, "product": "MILK",       "units": 6,  "source": "shop"},
    {"day": 20, "product": "EGGS",       "units": 8,  "source": "shop"},
    {"day": 25, "product": "MILK",       "units": 8,  "source": "shop"},
]

# ── Land expansion ────────────────────────────────────────────────────────────
LAND_COST: float = 100.0       # cost to unlock one extra tile/plot
LAND_MIN_RUNWAY: int = 96      # minimum remaining turns to justify land purchase

# ── Task priorities ───────────────────────────────────────────────────────────
PRIORITY_SURVIVAL: int = 100   # WATER, FEED — must happen
PRIORITY_HARVEST: int = 80     # collect ripe crops / animal products
PRIORITY_PLANT: int = 60       # plant seeds
PRIORITY_SELL: int = 50        # market sales
PRIORITY_FERTILIZE: int = 40   # fertilizer application
PRIORITY_MOVE: int = 20        # repositioning
PRIORITY_ECONOMIC: int = 10    # land/labor/animal buy
