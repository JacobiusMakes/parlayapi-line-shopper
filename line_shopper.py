#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""line_shopper.py: compare every sportsbook's price on the same bet.

Given a team or a sport, prints each book's current price per outcome,
flags the best and worst price, and shows how many cents of hold you
save by shopping the best line instead of betting at one book.

Zero setup: with no API key it runs against the ParlayAPI sandbox
(synthetic data, no signup). Set PARLAY_API_KEY for live odds.

    uv run line_shopper.py nba
    uv run line_shopper.py "Lakers"
    PARLAY_API_KEY=... uv run line_shopper.py nfl --markets h2h,spreads

Built by the ParlayAPI team. https://parlay-api.com
MIT license.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict

BASE_URL = "https://parlay-api.com"

SPORT_ALIASES = {
    "nba": "basketball_nba",
    "wnba": "basketball_wnba",
    "ncaab": "basketball_ncaab",
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "cfb": "americanfootball_ncaaf",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
    "epl": "soccer_england_premier_league",
    "premier-league": "soccer_england_premier_league",
    "tennis": "tennis",
    "mma": "mma_mixed_martial_arts",
    "ufc": "mma_mixed_martial_arts",
}

# Sports scanned when the query is a team name and --sport is not given.
TEAM_SEARCH_SPORTS = [
    "basketball_nba",
    "americanfootball_nfl",
    "baseball_mlb",
    "icehockey_nhl",
    "soccer_england_premier_league",
    "tennis",
]

MARKET_LABELS = {
    "h2h": "moneyline",
    "spreads": "spread",
    "totals": "total",
}

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


# ---------------------------------------------------------------- odds math

def american_to_decimal(price):
    p = float(price)
    if p >= 100:
        return 1.0 + p / 100.0
    if p <= -100:
        return 1.0 + 100.0 / -p
    # Should not happen with oddsFormat=american, but stay safe.
    raise ValueError("not an American price: %r" % price)


def implied_prob(price):
    return 1.0 / american_to_decimal(price)


def cents_scale(price):
    """Linear 'cents' scale used by line shoppers.

    +100 and -100 are both 0. +145 is 45. -110 is -10. The gap between
    two prices on this scale is the familiar 'cents' difference:
    -105 vs -110 is 5 cents, +145 vs +100 is 45 cents.
    """
    p = float(price)
    return p - 100 if p > 0 else p + 100


def fmt_price(price, decimal=False):
    if decimal:
        return "%.2f" % american_to_decimal(price)
    p = int(round(float(price)))
    return "%+d" % p


# ---------------------------------------------------------------- API client

class ApiError(Exception):
    pass


def api_get(path, params, api_key=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "parlayapi-line-shopper/1.0",
        "Accept": "application/json",
    })
    if api_key:
        req.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        if e.code == 401:
            raise ApiError("401 unauthorized: check PARLAY_API_KEY. %s" % detail)
        if e.code in (402, 429):
            raise ApiError("%d from the API (credits or rate limit). %s" % (e.code, detail))
        raise ApiError("HTTP %d from %s. %s" % (e.code, url, detail))
    except urllib.error.URLError as e:
        raise ApiError("could not reach %s (%s)" % (BASE_URL, e.reason))


def fetch_odds(sport_key, markets, regions, live, api_key):
    prefix = "/v1/sports/" if live else "/v1/sandbox/sports/"
    params = {
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american",
    }
    return api_get(prefix + sport_key + "/odds", params, api_key if live else None)


# ---------------------------------------------------------------- shopping

def outcome_key(outcome):
    return (outcome.get("name", "?"), outcome.get("point"))


def outcome_header(key):
    name, point = key
    if point is None:
        return name
    return "%s %+g" % (name, point) if name not in ("Over", "Under") else "%s %g" % (name, point)


def shop_market(game, market_key, books_filter):
    """Collect per-book prices for one market of one game.

    Returns None if fewer than 2 books quote the market, else a dict with
    the ordered outcome keys, per-book price rows, best/worst per outcome,
    and hold numbers.
    """
    per_book = OrderedDict()   # book_title -> {outcome_key: price}
    signatures = []
    first_order = {}           # signature -> ordered outcome keys

    for bm in game.get("bookmakers", []):
        book = bm.get("key", "?")
        if books_filter and book not in books_filter:
            continue
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            prices = OrderedDict()
            for o in m.get("outcomes", []):
                try:
                    american_to_decimal(o["price"])
                except (ValueError, KeyError, TypeError):
                    continue
                prices[outcome_key(o)] = float(o["price"])
            if not prices:
                continue
            sig = frozenset(prices.keys())
            signatures.append(sig)
            first_order.setdefault(sig, list(prices.keys()))
            per_book[book] = prices

    if len(per_book) < 2:
        return None

    # Books can hang different lines (e.g. -3 vs -3.5). Compare only the
    # books quoting the most common line for this market.
    modal_sig, _ = Counter(signatures).most_common(1)[0]
    outcomes = first_order[modal_sig]
    rows = OrderedDict((b, p) for b, p in per_book.items()
                       if frozenset(p.keys()) == modal_sig)
    skipped = [b for b in per_book if b not in rows]
    if len(rows) < 2:
        return None

    best = {}
    worst = {}
    for ok in outcomes:
        ranked = sorted(rows.items(), key=lambda bp: american_to_decimal(bp[1][ok]))
        worst[ok] = ranked[0]
        best[ok] = ranked[-1]

    holds = OrderedDict()
    for book, prices in rows.items():
        holds[book] = sum(implied_prob(prices[ok]) for ok in outcomes) - 1.0
    shopped_hold = sum(implied_prob(best[ok][1][ok]) for ok in outcomes) - 1.0
    avg_hold = sum(holds.values()) / len(holds)
    worst_hold = max(holds.values())

    return {
        "outcomes": outcomes,
        "rows": rows,
        "best": best,
        "worst": worst,
        "holds": holds,
        "shopped_hold": shopped_hold,
        "avg_hold": avg_hold,
        "worst_hold": worst_hold,
        "skipped_books": skipped,
    }


# ---------------------------------------------------------------- rendering

def paint(text, color, use_color):
    return color + text + RESET if use_color else text


def render_market(market_key, shop, decimal, use_color, out):
    label = MARKET_LABELS.get(market_key, market_key)
    outcomes = shop["outcomes"]
    rows = shop["rows"]

    headers = [outcome_header(ok) for ok in outcomes]
    book_w = max([len("best line"), len("book")] + [len(b) for b in rows]) + 2
    col_ws = [max(len(h), 10) for h in headers]

    out.append("  %s (%s)" % (market_key, label))
    head = "  " + "book".ljust(book_w)
    head += "".join(h.rjust(w + 3) for h, w in zip(headers, col_ws))
    head += "hold".rjust(9)
    out.append(head)

    for book, prices in rows.items():
        line = "  " + book.ljust(book_w)
        for ok, w in zip(outcomes, col_ws):
            cell = fmt_price(prices[ok], decimal)
            best_p = shop["best"][ok][1][ok]
            worst_p = shop["worst"][ok][1][ok]
            if best_p != worst_p and prices[ok] == best_p:
                cell = paint(cell + " *", GREEN, use_color)
            elif best_p != worst_p and prices[ok] == worst_p:
                cell = paint(cell + " !", RED, use_color)
            else:
                cell = cell + "  "
            pad = w + 3 - len(fmt_price(prices[ok], decimal)) - 2
            line += " " * max(pad, 1) + cell
        line += ("%.1f%%" % (shop["holds"][book] * 100)).rjust(9)
        out.append(line)

    # Best-line row: what you get if you shop every outcome.
    line = "  " + paint("best line".ljust(book_w), BOLD, use_color)
    for ok, w in zip(outcomes, col_ws):
        cell = fmt_price(shop["best"][ok][1][ok], decimal)
        pad = w + 3 - len(cell) - 2
        line += " " * max(pad, 1) + paint(cell, BOLD, use_color) + "  "
    line += paint(("%.1f%%" % (shop["shopped_hold"] * 100)).rjust(9), BOLD, use_color)
    out.append(line)

    for ok in outcomes:
        bb, bp = shop["best"][ok]
        wb, wp = shop["worst"][ok]
        gap = cents_scale(bp[ok]) - cents_scale(wp[ok])
        if gap <= 0:
            continue
        out.append("    %s: %.0f cents between %s (%s) and %s (%s)" % (
            outcome_header(ok), gap,
            bb, fmt_price(bp[ok], decimal),
            wb, fmt_price(wp[ok], decimal)))

    saved_avg = (shop["avg_hold"] - shop["shopped_hold"]) * 100
    saved_worst = (shop["worst_hold"] - shop["shopped_hold"]) * 100
    out.append("    shopping saves %.1f cents of hold per dollar vs the average book"
               " (%.1f vs the worst)" % (saved_avg, saved_worst))
    if shop["skipped_books"]:
        out.append("    (different line, not compared: %s)" % ", ".join(shop["skipped_books"]))
    return saved_avg


def render_game(game, market_keys, books_filter, decimal, use_color, out):
    when = str(game.get("commence_time", ""))[:16].replace("T", " ")
    sport = game.get("sport_title") or game.get("sport_key", "")
    title = "%s @ %s" % (game.get("away_team", "?"), game.get("home_team", "?"))
    if sport:
        title += "  [%s]" % sport
    savings = []
    body = []
    for mk in market_keys:
        shop = shop_market(game, mk, books_filter)
        if shop is None:
            continue
        if body:
            body.append("")
        savings.append(render_market(mk, shop, decimal, use_color, body))
    if not body:
        return savings
    out.append("")
    out.append(paint("%s  (%s UTC)" % (title, when), BOLD, use_color))
    out.extend(body)
    return savings


# ---------------------------------------------------------------- main

def resolve_query(query):
    """Return (sport_keys, team_filter)."""
    q = query.strip()
    low = q.lower()
    if low in SPORT_ALIASES:
        return [SPORT_ALIASES[low]], None
    if "_" in low:
        return [low], None
    return None, low


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="line_shopper.py",
        description="Compare every book's price on the same bet and see the "
                    "cents of hold you save by shopping. Sandbox by default; "
                    "set PARLAY_API_KEY for live odds from parlay-api.com.")
    ap.add_argument("query", help="a sport (nba, nfl, mlb, nhl, epl, tennis, "
                                  "or any sport_key like basketball_nba) or a "
                                  "team name to search for (e.g. 'Lakers')")
    ap.add_argument("--sport", help="restrict a team search to one sport_key")
    ap.add_argument("--markets", default="h2h",
                    help="comma list: h2h, spreads, totals (default: h2h)")
    ap.add_argument("--regions", default="us", help="regions param (default: us)")
    ap.add_argument("--books", help="comma list of bookmaker keys to include")
    ap.add_argument("--decimal", action="store_true", help="show decimal odds")
    ap.add_argument("--live", action="store_true",
                    help="force live mode (requires PARLAY_API_KEY)")
    ap.add_argument("--sandbox", action="store_true",
                    help="force sandbox mode even if a key is set")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    args = ap.parse_args(argv)

    api_key = os.environ.get("PARLAY_API_KEY", "").strip()
    live = bool(api_key) and not args.sandbox
    if args.live and not api_key:
        print("error: --live needs PARLAY_API_KEY "
              "(free tier: https://parlay-api.com/signup)", file=sys.stderr)
        return 2
    use_color = sys.stdout.isatty() and not args.no_color

    sport_keys, team_filter = resolve_query(args.query)
    if team_filter is not None:
        sport_keys = [args.sport] if args.sport else list(TEAM_SEARCH_SPORTS)
    market_keys = [m.strip() for m in args.markets.split(",") if m.strip()]
    books_filter = None
    if args.books:
        books_filter = {b.strip().lower() for b in args.books.split(",") if b.strip()}

    if live:
        mode = "live (key found in PARLAY_API_KEY)"
    else:
        mode = "sandbox: synthetic odds, no key needed. Set PARLAY_API_KEY for live odds."
    print("parlayapi line shopper | mode: %s" % mode)
    print("markers: * best price for that outcome, ! worst. "
          "hold = the book's margin on that market.")

    out = []
    savings = []
    games_shown = 0
    for sk in sport_keys:
        try:
            games = fetch_odds(sk, args.markets, args.regions, live, api_key)
        except ApiError as e:
            print("warning: %s: %s" % (sk, e), file=sys.stderr)
            continue
        if not isinstance(games, list):
            continue
        for game in games:
            if team_filter is not None:
                haystack = ("%s %s" % (game.get("home_team", ""),
                                       game.get("away_team", ""))).lower()
                if team_filter not in haystack:
                    continue
            got = render_game(game, market_keys, books_filter,
                              args.decimal, use_color, out)
            savings.extend(got)
            if got:
                games_shown += 1

    if not out:
        target = args.query if team_filter is None else "team '%s'" % args.query
        print("\nNo comparable odds found for %s right now." % target)
        if team_filter is not None and not args.sport:
            print("Searched: %s. Narrow or widen with --sport <sport_key>."
                  % ", ".join(sport_keys))
        return 1

    print("\n".join(out))
    if savings:
        print()
        print("Across %d game(s): shopping the best line saves an average of "
              "%.1f cents of hold per dollar staked." %
              (games_shown, sum(savings) / len(savings)))
    if not live:
        print("These are synthetic sandbox odds. Run with PARLAY_API_KEY set "
              "for live lines from 45+ books and sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
