# gta6-twitch-ccu-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/feza992/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/feza992/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A program that forecasts Grand Theft Auto VI's launch-day Twitch concurrent
viewers hour by hour: from a case's hour-1 count and its comparables, it
pools the launch-day shape of midnight-local releases and writes five
quantiles per hour for hours 2–24.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` (Python 3.13, standard library only) reads every `<id>.in` case in
the input directory and writes one `<id>.out` forecast per case: 23 rows,
hours 2–24, each with the five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) of
that hour's concurrent viewers.

---

<sub>Entered on [make.fun](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>

## Method

For each hour, the program pools the log-ratios `ln(viewers_h / viewers_1)`
across past big launches that unlocked at midnight local time with no early
access — the same rollout as GTA VI — and reads off the five empirical
quantiles, winsorized to median ± 2.5σ, then scales by the case's hour-1
print. The pool and the quantiles are computed at run time from the case
file's own comparables.

Validated on the four practice cases against the hourly counts the
historical source publishes: mean pinball loss **0.267** against **0.387**
for the house baseline.

## License

MIT — see `LICENSE`.
