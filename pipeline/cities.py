"""Per-city tier-1 grid configurations for build_city_grid.py.

Corridors: (label, orientation, parts). Parts are OSM street-name chains
(P) or literal coordinate extensions (PTS); gaps between parts render as
straight connectors (tunnels). Orientation ("ew"/"ns") drives crossing
pairing and terminal naming — for rotated grids assign the closest axis.
"""


def P(names, bbox=None):
    return {"names": names if isinstance(names, list) else [names], "bbox": bbox}


def PTS(points):
    return {"points": points}


CITIES = {
    "sf": {
        "label": "San Francisco",
        "slug": "sf",
        "bbox": (37.703, -122.525, 37.815, -122.350),
        "center_lat": 37.76,
        "corridors": [
            ("Geary",      "ew", [P("Point Lobos Avenue"), P("Geary Boulevard"), P("Geary Street"),
                                  PTS([[-122.3927, 37.7897]])]),
            ("Fulton",     "ew", [P("Fulton Street")]),
            ("Judah",      "ew", [P("Judah Street"), P("Duboce Avenue")]),
            ("Taraval",    "ew", [P("Taraval Street"), P("West Portal Avenue"),
                                  P("Castro Street", (37.760, -122.437, 37.7627, -122.433))]),
            ("Vicente–24th", "ew", [P("Vicente Street"), P("24th Street")]),
            ("Ocean",      "ew", [P("Ocean Avenue"), P("Geneva Avenue")]),
            ("California", "ew", [P("California Street")]),
            ("Union",      "ew", [P("Union Street")]),
            ("Market",     "ew", [P("Portola Drive"), P("Market Street")]),
            ("16th St",    "ew", [P("Parnassus Avenue"), P("16th Street")]),
            ("Sunset",     "ns", [P("Sunset Boulevard"),
                                  P("36th Avenue", (37.771, -122.51, 37.79, -122.49))]),
            ("9th Ave",    "ns", [P("9th Avenue")]),
            ("19th Ave",   "ns", [P("19th Avenue"), P("Park Presidio Boulevard")]),
            ("Masonic",    "ns", [P("Clayton Street"), P("Masonic Avenue"), P("Presidio Avenue")]),
            ("Divisadero", "ns", [P("San Jose Avenue", (37.703, -122.46, 37.742, -122.42)),
                                  P("Castro Street", (37.741, -122.44, 37.769, -122.43)),
                                  P("Divisadero Street")]),
            ("Fillmore",   "ns", [P("Church Street"), P("Fillmore Street")]),
            ("Van Ness",   "ns", [P("South Van Ness Avenue"), P("Van Ness Avenue")]),
            ("Polk",       "ns", [P("Polk Street")]),
            ("Mission",    "ns", [P("Mission Street")]),
            ("Stockton",   "ns", [P("4th Street", (37.768, -122.41, 37.79, -122.39)),
                                  P("Stockton Street")]),
            ("Columbus",   "ns", [P("3rd Street"),
                                  P("Kearny Street", (37.786, -122.4065, 37.7962, -122.4000)),
                                  P("Columbus Avenue")]),
            ("Potrero",    "ns", [P("Bayshore Boulevard", (37.703, -122.42, 37.75, -122.39)),
                                  P("Potrero Avenue"),
                                  P("10th Street", (37.768, -122.42, 37.78, -122.40))]),
            ("Embarcadero", "ns", [P("The Embarcadero")]),
        ],
    },
    "eastbay": {
        "label": "Oakland–Berkeley",
        "slug": "eastbay",
        "bbox": (37.700, -122.350, 37.905, -122.210),
        "center_lat": 37.80,
        "corridors": [
            ("Shattuck",     "ns", [P("Shattuck Avenue")]),
            ("Telegraph",    "ns", [P("Telegraph Avenue")]),
            ("College",      "ns", [P("College Avenue")]),
            ("San Pablo",    "ns", [P("San Pablo Avenue")]),
            ("MLK",          "ns", [P(["Martin Luther King Jr Way", "Martin Luther King Jr. Way",
                                       "Martin Luther King Junior Way"])]),
            ("Broadway",     "ns", [P("Broadway", (37.790, -122.285, 37.850, -122.235))]),
            ("University",   "ew", [P("University Avenue")]),
            ("Ashby",        "ew", [P("Ashby Avenue")]),
            ("Grand",        "ew", [P("Grand Avenue", (37.795, -122.275, 37.822, -122.230))]),
            ("MacArthur",    "ew", [P("MacArthur Boulevard", (37.760, -122.285, 37.840, -122.210))]),
            ("International", "ew", [P("International Boulevard")]),
        ],
    },
}
