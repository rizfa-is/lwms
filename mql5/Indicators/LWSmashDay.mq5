//+------------------------------------------------------------------+
//|                                              LWSmashDay.mq5      |
//|                                                       lwms       |
//|         Larry Williams Smash Day — Parts 10/11 (articles 21127/8)|
//+------------------------------------------------------------------+
//| Plots arrows on confirmed Smash Day reversal bars.               |
//|   Sea-green up-arrow under buy-side smash bars.                  |
//|   Black down-arrow above sell-side smash bars.                   |
//|                                                                  |
//| Detection rules per article 21128:                               |
//|   buy:  close < each of the prior N lows (N = InpLookback)       |
//|         AND smash bar is NOT outside relative to its predecessor |
//|         AND the next bar closes above the smash bar's high.      |
//|   sell: mirror — close > each of prior N highs, not outside,     |
//|         next bar closes below smash low.                         |
//|                                                                  |
//| The arrow is anchored on the smash bar itself, drawn AFTER the   |
//| confirmation bar closes.                                          |
//|                                                                  |
//| Buffers exposed for consumer EAs (must not be reordered):        |
//|   0 = Buy-side smash arrow buffer  (low-anchored)                |
//|   1 = Sell-side smash arrow buffer (high-anchored)               |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#property indicator_chart_window
#property indicator_plots   2
#property indicator_buffers 2

#property indicator_label1  "BuySmash"
#property indicator_color1  clrSeaGreen
#property indicator_width1  2
#property indicator_label2  "SellSmash"
#property indicator_color2  clrBlack
#property indicator_width2  2

input int InpBuyLookbackBars  = 1;     // smash buy: prior N lows to clear
input int InpSellLookbackBars = 1;     // smash sell: prior N highs to clear

double buySmash [];
double sellSmash[];

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, buySmash,  INDICATOR_DATA);
   SetIndexBuffer(1, sellSmash, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(0, PLOT_ARROW_SHIFT, -20);
   PlotIndexSetDouble (0, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(1, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   PlotIndexSetInteger(1, PLOT_ARROW_SHIFT, +20);
   PlotIndexSetDouble (1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME, "LW Smash Day Reversal");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Outside-bar test (forward-indexed inputs).                       |
//+------------------------------------------------------------------+
bool IsOutside(const double prev_h, const double prev_l,
               const double cur_h,  const double cur_l)
{
   return (cur_h > prev_h && cur_l < prev_l);
}

//+------------------------------------------------------------------+
//| Map all Smash Day reversals across the historical bars.          |
//+------------------------------------------------------------------+
void MapSmashDays(const int rates_total,
                  const double &high[], const double &low[], const double &close[])
{
   ArrayInitialize(buySmash,  EMPTY_VALUE);
   ArrayInitialize(sellSmash, EMPTY_VALUE);

   for(int i = MathMax(InpBuyLookbackBars, InpSellLookbackBars); i < rates_total - 1; i++)
   {
      // Buy smash: close[i] < every low in [i-1 .. i-N], not outside, next closes > high[i].
      bool buy_ok = (i + 1 < rates_total);
      if(buy_ok)
      {
         for(int k = 1; k <= InpBuyLookbackBars; k++)
         {
            if(i - k < 0) { buy_ok = false; break; }
            if(close[i] >= low[i - k]) { buy_ok = false; break; }
         }
      }
      if(buy_ok && i - 1 >= 0 && IsOutside(high[i - 1], low[i - 1], high[i], low[i]))
         buy_ok = false;
      if(buy_ok && close[i + 1] <= high[i]) buy_ok = false;
      if(buy_ok) buySmash[i] = low[i];

      // Sell smash mirror.
      bool sell_ok = (i + 1 < rates_total);
      if(sell_ok)
      {
         for(int k = 1; k <= InpSellLookbackBars; k++)
         {
            if(i - k < 0) { sell_ok = false; break; }
            if(close[i] <= high[i - k]) { sell_ok = false; break; }
         }
      }
      if(sell_ok && i - 1 >= 0 && IsOutside(high[i - 1], low[i - 1], high[i], low[i]))
         sell_ok = false;
      if(sell_ok && close[i + 1] >= low[i]) sell_ok = false;
      if(sell_ok) sellSmash[i] = high[i];
   }
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   if(rates_total < 4) return rates_total;
   MapSmashDays(rates_total, high, low, close);
   return rates_total;
}
//+------------------------------------------------------------------+
