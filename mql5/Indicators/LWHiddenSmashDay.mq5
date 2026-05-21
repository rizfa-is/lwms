//+------------------------------------------------------------------+
//|                                       LWHiddenSmashDay.mq5       |
//|                                                       lwms       |
//|     Larry Williams Hidden Smash Day — Parts 13/14 (21391/21392)  |
//+------------------------------------------------------------------+
//| Plots arrows on confirmed Hidden Smash Day reversal bars.        |
//|                                                                  |
//| Hidden Smash Buy:                                                |
//|   close[i] > close[i-1]                                          |
//|   range[i] > 0                                                   |
//|   close in lower InpQuartilePct of own range (default 25.0)      |
//|   optional: close[i] < open[i] (strictest)                       |
//|   confirmation: close[i+1] > high[i]                             |
//| Sell mirror (close in upper quartile, close[i+1] < low[i]).      |
//|                                                                  |
//| Validation modes (article 21392):                                |
//|   HIDDEN_SMASH_BAR_ONLY  — show as soon as smash bar passes      |
//|   HIDDEN_SMASH_CONFIRMED — show only after next-bar confirmation |
//|                                                                  |
//| Buffers (must not be reordered):                                 |
//|   0 = BuyHiddenSmash  (low-anchored)                             |
//|   1 = SellHiddenSmash (high-anchored)                            |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#property indicator_chart_window
#property indicator_plots   2
#property indicator_buffers 2

#property indicator_label1  "BuyHiddenSmash"
#property indicator_color1  clrSeaGreen
#property indicator_width1  2
#property indicator_label2  "SellHiddenSmash"
#property indicator_color2  clrBlack
#property indicator_width2  2

enum ENUM_HIDDEN_SMASH_MODE
{
   HIDDEN_SMASH_BAR_ONLY,
   HIDDEN_SMASH_CONFIRMED
};

input double                InpQuartilePct           = 25.0;
input bool                  InpRequireCloseVsOpen    = false;
input ENUM_HIDDEN_SMASH_MODE InpValidationMode       = HIDDEN_SMASH_CONFIRMED;

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

   IndicatorSetString(INDICATOR_SHORTNAME, "LW Hidden Smash Day");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
double ClosePositionPct(const double op, const double hi,
                        const double lo, const double cl)
{
   const double rng = hi - lo;
   if(rng <= 0.0) return 50.0;
   return (cl - lo) / rng * 100.0;
}

bool BuyBarAt(const int i, const double &open[], const double &high[],
              const double &low[], const double &close[])
{
   if(i < 1) return false;
   if(close[i] <= close[i - 1]) return false;
   if(high[i] - low[i] <= 0.0)  return false;
   if(ClosePositionPct(open[i], high[i], low[i], close[i]) > InpQuartilePct) return false;
   if(InpRequireCloseVsOpen && close[i] >= open[i]) return false;
   return true;
}

bool SellBarAt(const int i, const double &open[], const double &high[],
               const double &low[], const double &close[])
{
   if(i < 1) return false;
   if(close[i] >= close[i - 1]) return false;
   if(high[i] - low[i] <= 0.0)  return false;
   if(ClosePositionPct(open[i], high[i], low[i], close[i]) < (100.0 - InpQuartilePct))
      return false;
   if(InpRequireCloseVsOpen && close[i] <= open[i]) return false;
   return true;
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
   if(rates_total < 3) return rates_total;
   ArrayInitialize(buySmash,  EMPTY_VALUE);
   ArrayInitialize(sellSmash, EMPTY_VALUE);

   const int last_evaluable = (InpValidationMode == HIDDEN_SMASH_CONFIRMED)
      ? rates_total - 1 : rates_total;
   for(int i = 1; i < last_evaluable; i++)
   {
      if(BuyBarAt(i, open, high, low, close))
      {
         if(InpValidationMode == HIDDEN_SMASH_BAR_ONLY ||
            (i + 1 < rates_total && close[i + 1] > high[i]))
            buySmash[i] = low[i];
      }
      if(SellBarAt(i, open, high, low, close))
      {
         if(InpValidationMode == HIDDEN_SMASH_BAR_ONLY ||
            (i + 1 < rates_total && close[i + 1] < low[i]))
            sellSmash[i] = high[i];
      }
   }
   return rates_total;
}
//+------------------------------------------------------------------+
