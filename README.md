# parlayapi-line-shopper

A Python command-line example for comparing prices in the sportsbook records
returned to your request. It marks relative best and worst prices and displays
hold arithmetic for those inputs. It does not establish that every book or
required selection is present.

The script uses Python 3.9+ and the standard library. With no configured key it
selects the sandbox request path; with your own key it can select account
requests. Verify current endpoint access and scope in the documentation before
a private evaluation.

## Read a comparison against its scope

Check event identity, period, outcome and signed line before comparing prices.
Missing selections, different settlement rules and unknown observation times
remain separate problems. A numerical price difference does not establish an
executable trade, realized savings or profit.

## Existing command-line quickstart

```bash
git clone https://github.com/JacobiusMakes/parlayapi-line-shopper.git
cd parlayapi-line-shopper
uv run line_shopper.py nba
```

No [uv](https://docs.astral.sh/uv/)? Plain Python works too, there are zero dependencies:

```bash
python3 line_shopper.py nba
```

The following retained sandbox transcript contains invented prices. It is not current source data or a current endpoint-availability check:

```text
$ uv run line_shopper.py nba
parlayapi line shopper | mode: sandbox: synthetic odds, no key needed. Set PARLAY_API_KEY for live odds.
markers: * best price for that outcome, ! worst. hold = the book's margin on that market.

Boston Celtics @ Los Angeles Lakers  [NBA]  (2026-08-26 12:39 UTC)
  h2h (moneyline)
  book           Los Angeles Lakers   Boston Celtics     hold
  draftkings                 -150 !           -140 !    18.3%
  fanduel                    +120 *           +130 *   -11.1%
  betmgm                     -110             -140 !    10.7%
  caesars                    -130             -140 !    14.9%
  pinnacle                   +100             -120       4.5%
  bovada                     +120 *           +130 *   -11.1%
  polymarket                 +120 *           -140 !     3.8%
  kalshi                     -150 !           -100      10.0%
  best line                  +120             +130     -11.1%
    Los Angeles Lakers: 70 cents between polymarket (+120) and draftkings (-150)
    Boston Celtics: 70 cents between bovada (+130) and draftkings (-140)
    shopping saves 16.1 cents of hold per dollar vs the average book (29.4 vs the worst)

Miami Heat @ Golden State Warriors  [NBA]  (2026-08-26 23:08 UTC)
  h2h (moneyline)
  book           Golden State Warriors   Miami Heat     hold
  draftkings                    -150 !       -140 !    18.3%
  fanduel                       -150 !       -100      10.0%
  betmgm                        -130         -100       6.5%
  caesars                       +100 *       +130 *    -6.5%
  pinnacle                      +100 *       +110      -2.4%
  bovada                        -150 !       +110       7.6%
  polymarket                    -150 !       +130 *     3.5%
  kalshi                        -150 !       -120      14.5%
  best line                     +100         +130      -6.5%
    Golden State Warriors: 50 cents between pinnacle (+100) and draftkings (-150)
    Miami Heat: 70 cents between polymarket (+130) and draftkings (-140)
    shopping saves 13.0 cents of hold per dollar vs the average book (24.9 vs the worst)

Milwaukee Bucks @ Denver Nuggets  [NBA]  (2026-08-26 05:02 UTC)
  h2h (moneyline)
  book           Denver Nuggets   Milwaukee Bucks     hold
  draftkings             -110              +130 *    -4.1%
  fanduel                -130              +110       4.1%
  betmgm                 -130              +110       4.1%
  caesars                +100 *            -120 !     4.5%
  pinnacle               +100 *            -100       0.0%
  bovada                 -130              -120 !    11.1%
  polymarket             -130              +110       4.1%
  kalshi                 -150 !            -100      10.0%
  best line              +100              +130      -6.5%
    Denver Nuggets: 50 cents between pinnacle (+100) and kalshi (-150)
    Milwaukee Bucks: 50 cents between draftkings (+130) and caesars (-120)
    shopping saves 10.8 cents of hold per dollar vs the average book (17.6 vs the worst)

Across 3 game(s): shopping the best line saves an average of 13.3 cents of hold per dollar staked.
These are synthetic sandbox odds. Run with PARLAY_API_KEY set for live lines from 30+ books and sources.
```

These retained teaching outputs do not establish normal market margins, available payouts or savings for a private live evaluation.

## Plan a private evaluation

Record your polling window, interval, endpoints, pages and active days in the
free [workload planner](https://parlay-api.com/tools/api-workload?utm_source=github&utm_medium=tool_readme&utm_campaign=line-shopper).
It needs no account or key and makes no API requests. Leave credit cost unknown
until you verify the cost of your exact request shape.

For several request shapes with different or unknown unit costs, use the
[offline request-budget kit](https://github.com/JacobiusMakes/parlayapi-notebooks/tree/main/labs/request-budget).
It includes a CSV template, exact JSON export and a self-contained notebook
for Python 3.9 or later. Unpriced work keeps the total credit estimate unknown.

## Account requests

Create your own [account](https://parlay-api.com/signup?utm_source=github&utm_medium=tool_readme&utm_campaign=line-shopper), keep its key private, and explicitly select the request you want:

```bash
export PARLAY_API_KEY=your_key
uv run line_shopper.py nfl --markets h2h,spreads,totals
uv run line_shopper.py "Lakers"
```

Account requests use your own entitlement and allowance. Verify exact returned sport, bookmaker, market and timestamp fields. Current terms, allowances and request-cost rules are in the [documentation](https://parlay-api.com/docs) and [pricing](https://parlay-api.com/pricing).

## Usage

```text
line_shopper.py QUERY [options]

QUERY                a sport (nba, nfl, mlb, nhl, epl, tennis, ncaaf, mma, wnba,
                     or any raw sport_key like basketball_nba), or a team name
                     to search for (e.g. "Lakers", "Chiefs")

--sport SPORT_KEY    restrict a team-name search to one sport
--markets LIST       comma list: h2h, spreads, totals (default: h2h)
--regions LIST       regions parameter (default: us)
--books LIST         only compare these bookmaker keys (e.g. draftkings,pinnacle)
--decimal            show decimal odds instead of American
--live               force live mode (requires PARLAY_API_KEY)
--sandbox            force sandbox mode even if a key is set
--no-color           disable ANSI colors
```

A team-name query without --sport searches NBA, NFL, MLB, NHL, EPL, and tennis (one API request per sport in live mode).

## How the math works

- Implied probability of an American price: 100 / (p + 100) for positive p, -p / (-p + 100) for negative p.
- A book's hold on a market = sum of the implied probabilities of its outcomes, minus 1.
- The best line hold does the same sum using the single best price per outcome across all books. The difference is your savings, expressed in cents per dollar staked (1% of hold = 1 cent per dollar).
- Cents between two prices use the standard line-shopping scale where +100 and -100 are both zero: -105 vs -110 is 5 cents, +145 vs +100 is 45 cents.
- Books sometimes hang different lines (a -3 spread vs -3.5). The tool only compares books quoting the most common line for that market and lists the others as not compared, so you never see apples-to-oranges prices flagged as best.

## What it is not

This is a one-command line shopper, not a betting framework. No polling loops, no bet placement, no bankroll logic. For pre-computed cross-book arbitrage, positive EV screens, consensus lines, player props, and streaming, see the full [ParlayAPI docs](https://parlay-api.com/docs).

## License and affiliation

MIT-licensed code, built by the [ParlayAPI](https://parlay-api.com) team. Sharing this code does not grant permission to redistribute API data. Verify the applicable data-use terms for your private project.

---

Explore the related source projects at [github.com/JacobiusMakes](https://github.com/JacobiusMakes).
