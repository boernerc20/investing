# Technical Indicators Reference

Running reference built as each indicator is added to the system.
All indicators are calculated in `utils/technical_indicators.py`.

---

## Increment 1: Moving Averages

### SMA — Simple Moving Average

**Formula**: Sum of last N closing prices ÷ N

**Common periods**:
| Period | Represents | Use |
|--------|-----------|-----|
| SMA 10 | ~2 weeks | Very short-term noise filter |
| SMA 20 | ~1 month | Short-term trend |
| SMA 50 | ~1 quarter | Medium-term trend |
| SMA 200 | ~1 year | Long-term trend, major support/resistance |

**How to read it**:
- Price **above** SMA = bullish (price is above average, upward pressure)
- Price **below** SMA = bearish (price is below average, downward pressure)
- The further price is from the SMA, the more extended (and potentially reversible) the move

**Golden Cross / Death Cross** (most watched signal):
- **Golden Cross**: SMA 50 crosses *above* SMA 200 → long-term bullish signal
- **Death Cross**: SMA 50 crosses *below* SMA 200 → long-term bearish signal

---

### EMA — Exponential Moving Average

**Formula**: Weighted average where recent days count more than older days

**Key difference from SMA**: EMA reacts faster to price changes because it weights recent prices more heavily. SMA treats all days equally.

**When to use EMA vs SMA**:
- **EMA**: Better for timing entries/exits — catches moves earlier
- **SMA**: Better for identifying major support/resistance levels — less noise

**Common use**: EMA 12 and EMA 26 are the inputs to MACD (see below).

---

### SPY Example (Feb 13, 2026)

```
Close:    $681.75
SMA 10:   $688.04   ← price below → short-term bearish
SMA 20:   $689.15   ← price below → short-term bearish
SMA 50:   $687.36   ← price below → medium-term bearish
SMA 200:  $648.65   ← price above → long-term bullish

Golden Cross: SMA 50 ($687) > SMA 200 ($648) ✓
```

**Interpretation**: SPY is mid-dip within a healthy long-term uptrend. Price has pulled back below the quarterly average but remains well above the yearly average ($33 gap). Normal market behavior, not a warning sign.

---

## Increment 2: MACD

### MACD — Moving Average Convergence Divergence

**Three components**:

| Component | Formula | What it shows |
|-----------|---------|---------------|
| MACD Line | EMA(12) − EMA(26) | Direction and momentum |
| Signal Line | EMA(9) of MACD Line | Smoothed trigger line |
| Histogram | MACD Line − Signal Line | Strength of the move |

**How to read each**:

**MACD Line**:
- Positive = short-term average above long-term average (upward momentum)
- Negative = short-term average below long-term average (downward momentum)
- Crossing zero = momentum shift — significant signal

**Signal Line**:
- Just a smoothed version of the MACD line — lags behind it
- Used only for crossover detection

**Histogram**:
- Shows the gap between MACD and Signal
- Positive and growing = momentum building upward
- Negative and shrinking (toward zero) = downward momentum fading (potential reversal)

**The key signals**:
- **Bullish crossover**: MACD line crosses *above* signal line → buy signal
- **Bearish crossover**: MACD line crosses *below* signal line → sell signal
- **Zero line cross**: MACD crossing above/below zero = stronger confirmation

**Limitations**:
- MACD is a lagging indicator — it confirms moves after they've started, not before
- Works best in trending markets; gives false signals in choppy/sideways markets
- Always confirm with another indicator (RSI, volume, price action)

---

### SPY Example (Feb 13, 2026)

```
MACD Line:   -0.377   ← negative, short-term momentum has flipped down
Signal Line:  0.758   ← still positive, lagging behind the MACD drop
Histogram:   -1.136   ← negative, MACD below signal, momentum fading
```

**Interpretation**: All three MACD components are bearish — confirming the same dip the moving averages showed. The MACD line at -0.377 is only slightly negative, suggesting the weakness is real but not severe. Combined with the Golden Cross still intact, this looks like a normal correction rather than a trend reversal.

---

## Increment 3: RSI

### RSI — Relative Strength Index

**Formula**:
```
delta    = daily price change
avg_gain = exponential average of up-days over 14 periods
avg_loss = exponential average of down-days over 14 periods
RS       = avg_gain / avg_loss
RSI      = 100 - (100 / (1 + RS))
```

**Scale**: Always 0 to 100

| RSI Level | Zone | Meaning |
|-----------|------|---------|
| Above 70 | Overbought | Price has risen too fast — pullback likely |
| 60–70 | Bullish | Strong momentum, but not extreme |
| 40–60 | Neutral | No strong signal either way |
| 30–40 | Bearish | Weak momentum |
| Below 30 | Oversold | Price has fallen too fast — bounce likely |

**How to use it**:
- **Overbought (>70)**: Consider waiting for a better entry, or a sign to trim a position
- **Oversold (<30)**: Potential buying opportunity — price may be cheap relative to recent history
- **Divergence** (advanced): Price makes a new high but RSI doesn't → weakening momentum, possible reversal ahead

**Key difference from MACD**:
- MACD tells you **direction** of momentum
- RSI tells you **intensity** — how stretched the move is
- Use both together: MACD for trend direction, RSI for timing entries

**Limitations**:
- In strong trends, RSI can stay overbought (>70) for a long time without reversing — don't use it alone
- 14-period is standard but shorter periods (7) are more sensitive, longer (21) are smoother
- More reliable on daily charts than intraday

---

### SPY Example (Feb 13, 2026)

```
RSI (14): 43.79 → Neutral zone, slightly below 50 midpoint
```

**Interpretation**: Mild bearish lean — sellers have a slight edge over the past 14 days, but the reading is far from the oversold zone (<30) that would signal a strong buying opportunity. Combined with the MACD and SMA signals, this confirms a moderate pullback, not a panic. A true oversold reading would be RSI dipping toward 30, which would be a much stronger buy signal for a long-term investor.

---

## Increment 4: Bollinger Bands

### BB — Bollinger Bands

**Formula**:
```
Middle Band = SMA(20)
Upper Band  = SMA(20) + (2 × standard deviation over 20 days)
Lower Band  = SMA(20) - (2 × standard deviation over 20 days)
```

**Five values produced**:

| Value | Formula | What it shows |
|-------|---------|---------------|
| Middle Band | SMA(20) | The baseline trend |
| Upper Band | Middle + 2σ | Resistance / overbought zone |
| Lower Band | Middle − 2σ | Support / oversold zone |
| Band Width | (Upper − Lower) / Middle × 100 | Volatility as a % |
| %B | (Close − Lower) / (Upper − Lower) | Where price sits in the bands |

**%B explained** (the most useful single number):
- **%B = 0.0** → price is at the lower band
- **%B = 0.5** → price is at the middle (SMA 20)
- **%B = 1.0** → price is at the upper band
- **%B > 1.0** → price is above the upper band (overbought)
- **%B < 0.0** → price is below the lower band (oversold)

**The statistical basis**: In a normal distribution, ~95% of prices fall within 2 standard deviations. So touching the upper or lower band is genuinely unusual — only ~2.5% of days should be outside each band. When price reaches those extremes, a reversion toward the middle is statistically likely.

**Band Width (the squeeze)**:
- **Narrow bands (<5%)** = low volatility — the market is coiling. A big breakout move often follows a squeeze, but you can't know the direction in advance.
- **Wide bands (>15%)** = high volatility — big swings already happening
- **Normal (5–15%)** = typical market conditions

**Key signals**:
- Price **touches upper band** = overbought, watch for a pullback toward the middle
- Price **touches lower band** = oversold, watch for a bounce toward the middle
- **Squeeze** (bands narrow sharply) = volatility compression, breakout likely soon
- **Walking the band** (price hugs upper band across multiple days) = very strong uptrend — don't short just because it's "at the upper band"

**Limitations**:
- Bands adapt to volatility — in a volatile market they widen, making "overbought" harder to reach
- Like RSI, price can walk the upper band for extended periods in strong bull runs
- Best used with RSI for confirmation: price at upper band + RSI >70 = stronger overbought signal

**Difference from RSI**:
- RSI measures momentum speed (how fast price moved)
- Bollinger Bands measure volatility and relative price position
- They complement each other well

---

### SPY Example (Feb 13, 2026)

```
Upper Band:  $700.55
Middle Band: $689.15  (SMA 20)
Lower Band:  $677.74
Close:       $681.75
Band Width:    3.31%  ← SQUEEZE (below 5% threshold)
%B:            0.18   ← price near lower band, only 18% up from floor
```

**Interpretation**: Two key signals. First, price (%B=0.18) is sitting near the lower band — consistent with the bearish RSI and MACD readings, confirming the pullback is real. Second, the squeeze (3.31%) is the standout signal: the market has compressed into an unusually tight range. A volatility expansion is likely coming. Combined with the Golden Cross still intact, the long-term trend bias favors an upward breakout, but the direction isn't confirmed until price breaks decisively above the middle band ($689) or below the lower band ($677).

---

## Increment 5: Volume Analysis

### Volume Indicators

Volume answers the question the price indicators can't: **is this move real?** Price moves on high volume have conviction. Price moves on low volume are suspect — they tend to reverse.

**Four values produced**:

| Value | Formula | What it shows |
|-------|---------|---------------|
| Vol SMA | Average volume over 20 days | The "normal" baseline |
| Vol Ratio | Today's volume ÷ Vol SMA | How unusual today's volume is |
| OBV | Cumulative +volume on up days, −volume on down days | Net money flow direction |
| OBV SMA | 20-day average of OBV | Smoothed flow trend |

**Vol Ratio thresholds**:
| Ratio | Meaning |
|-------|---------|
| > 2.0x | Very high — strong conviction behind the move |
| 1.5–2.0x | Above average — meaningful participation |
| 0.5–1.5x | Normal range |
| < 0.5x | Very low — weak conviction, move may not hold |

**OBV (On Balance Volume)**:
The key insight: volume leads price. If buyers are absorbing more shares than sellers are dumping (OBV rising), that's bullish pressure building even if the price hasn't moved yet.

- **OBV rising** = on balance, more volume on up-days than down-days → buyers in control
- **OBV falling** = on balance, more volume on down-days → sellers in control
- **OBV above its own SMA** = the trend in volume flow is bullish
- **OBV below its own SMA** = the trend in volume flow is bearish

**The most powerful use — divergence**:
- **Bullish divergence**: price making lower lows, but OBV making higher lows → sellers losing conviction, reversal likely upward
- **Bearish divergence**: price making higher highs, but OBV making lower highs → buyers losing conviction, reversal likely downward

**Why volume matters for confirming the Bollinger Band squeeze**:
When the squeeze breaks, check volume immediately. A breakout on high volume (>1.5x) is far more reliable than one on low volume. Low-volume breakouts often fail and reverse.

**Limitations**:
- OBV is a cumulative number — the absolute value is meaningless, only direction and trend matter
- ETFs can have volume distorted by institutional block trades
- Works best combined with price action confirmation

---

### SPY Example (Feb 13, 2026)

```
Volume:      96.3M shares  (1.09x normal — unremarkable)
Avg Volume:  88.1M shares
OBV:         1,074.5M cumulative
OBV vs Avg:  Below 20-day average (sellers winning on balance)
```

**Interpretation**: The dip is happening on normal volume — not a panic. Capitulation selloffs show 2–3x volume as everyone rushes for the exit. At 1.09x, there's no panic. However OBV is below its 20-day average, meaning more volume has flowed out than in recently. This confirms the other bearish signals without amplifying them. Combined with the Bollinger squeeze, watch for the next high-volume day — that's likely when the direction resolves.

---

## Reading All Five Together

When all indicators align, that's a high-confidence signal. When they're mixed, size your conviction accordingly.

**Full bullish alignment**:
- Price above SMA 50 and SMA 200 (Golden Cross)
- MACD line above signal, histogram positive and growing
- RSI 50–70 (strong but not overbought)
- %B above 0.5 (upper half of bands)
- Vol Ratio ≥ 1.5x on up moves, OBV above its average

**Full bearish alignment**:
- Price below SMA 50, SMA 50 below SMA 200 (Death Cross)
- MACD line below signal, histogram negative
- RSI below 40
- %B below 0.3 (lower half of bands)
- High volume on down moves, OBV below its average

**SPY Feb 13, 2026 — mixed signals (healthy pullback)**:
- Long-term bullish: Golden Cross intact, price well above SMA 200
- Short-term bearish: below SMA 50, MACD negative, OBV declining
- Not extreme: RSI neutral at 43.8, volume normal at 1.09x
- Key watch: Bollinger squeeze (3.3%) will resolve soon — volume on the breakout day tells you if it's real

**Verdict**: A moderate, unconvincing dip inside a solid long-term uptrend. For a dollar-cost averaging investor, this is noise. For a trader, wait for the squeeze to resolve with volume confirmation before acting.

---

## Coming Next

- [ ] Technical analysis agent — combines all 5 indicators into scored buy/sell signals
- [ ] Support & resistance levels
- [ ] Pattern detection (higher highs/lower lows, etc.)
- [ ] Multi-symbol scanning

When SMA, MACD, and RSI agree — that's a high-confidence signal.

**Bullish alignment**:
- Price above SMA 50 and SMA 200
- MACD line above signal, histogram positive
- RSI between 50–70 (strong but not overbought)

**Bearish alignment**:
- Price below SMA 50
- MACD line below signal, histogram negative
- RSI below 50 (and especially below 40)

**SPY Feb 13, 2026 — mixed signals**:
- Long-term: Bullish (Golden Cross, price above SMA 200)
- Medium/Short-term: Bearish (below SMA 50, MACD negative)
- RSI: TBD after next run

This mixed picture = **healthy pullback within an uptrend**, not a reversal. For a long-term index fund investor, this is noise.

---

## Coming Next

- [ ] Bollinger Bands — volatility-based support/resistance bands
- [ ] Volume analysis — confirms whether moves are "real"
- [ ] Support & resistance levels
- [ ] Trading signal generation (combining all indicators)
