//+------------------------------------------------------------------+
//|                                       LWMarketStructure.mq5      |
//|                                                       lwms       |
//|             Larry Williams Market Secrets — Part 1 (article 20511)|
//+------------------------------------------------------------------+
//| 3-tier swing-structure indicator. Detects short-term swing       |
//| highs/lows on the bar timeframe, then promotes them to           |
//| intermediate and long-term swings. Plotted as on-chart marks:    |
//|                                                                  |
//|   short-term  -> small ring  (Wingdings 161)                     |
//|   intermediate-> bigger ring (Wingdings 161, width 4)            |
//|   long-term   -> arrow above/below (Wingdings 233/234)            |
//|                                                                  |
//| Six buffers (indices 0..5) are exposed for consumer EAs:         |
//|   0 = short-term lows         3 = intermediate-term highs        |
//|   1 = short-term highs        4 = long-term lows                 |
//|   2 = intermediate-term lows  5 = long-term highs                |
//|                                                                  |
//| Empty bars carry EMPTY_VALUE.                                    |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#property indicator_chart_window
#property indicator_plots   6
#property indicator_buffers 6

#property indicator_label1  "ShortTermLows"
#property indicator_color1  clrSeaGreen
#property indicator_width1  1
#property indicator_label2  "ShortTermHighs"
#property indicator_color2  clrBlack
#property indicator_width2  1

#property indicator_label3  "IntermediateLows"
#property indicator_color3  clrSeaGreen
#property indicator_width3  4
#property indicator_label4  "IntermediateHighs"
#property indicator_color4  clrBlack
#property indicator_width4  4

#property indicator_label5  "LongTermLows"
#property indicator_color5  clrSeaGreen
#property indicator_width5  2
#property indicator_label6  "LongTermHighs"
#property indicator_color6  clrBlack
#property indicator_width6  2

double shortTermLows  [];
double shortTermHighs [];
double intermTermLows [];
double intermTermHighs[];
double longTermLows   [];
double longTermHighs  [];

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, shortTermLows,   INDICATOR_DATA);
   SetIndexBuffer(1, shortTermHighs,  INDICATOR_DATA);
   SetIndexBuffer(2, intermTermLows,  INDICATOR_DATA);
   SetIndexBuffer(3, intermTermHighs, INDICATOR_DATA);
   SetIndexBuffer(4, longTermLows,    INDICATOR_DATA);
   SetIndexBuffer(5, longTermHighs,   INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(0, PLOT_ARROW, 161);
   PlotIndexSetDouble (0, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(1, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(1, PLOT_ARROW, 161);
   PlotIndexSetDouble (1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(2, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(2, PLOT_ARROW, 161);
   PlotIndexSetDouble (2, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(3, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(3, PLOT_ARROW, 161);
   PlotIndexSetDouble (3, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(4, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(4, PLOT_ARROW, 233);
   PlotIndexSetInteger(4, PLOT_ARROW_SHIFT, -30);
   PlotIndexSetDouble (4, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(5, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(5, PLOT_ARROW, 234);
   PlotIndexSetInteger(5, PLOT_ARROW_SHIFT, +30);
   PlotIndexSetDouble (5, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME, "LW Market Structure");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Build intermediate (or long) swings from a lower-tier swing list.|
//| ``isHigh`` controls whether middle must be higher (true) or      |
//| lower (false) than its same-kind neighbours.                     |
//+------------------------------------------------------------------+
void BuildPromoted(const double &src[], const int total,
                   const bool isHigh, double &dst[])
{
   if(ArraySize(dst) != total) ArrayResize(dst, total);
   for(int i = 0; i < total; i++) dst[i] = EMPTY_VALUE;

   int idx[];
   ArrayResize(idx, 0);
   for(int i = 0; i < total; i++)
   {
      if(src[i] != EMPTY_VALUE)
      {
         const int n = ArraySize(idx) + 1;
         ArrayResize(idx, n);
         idx[n - 1] = i;
      }
   }

   const int count = ArraySize(idx);
   if(count < 3) return;
   for(int k = 1; k < count - 1; k++)
   {
      const int a = idx[k - 1];
      const int b = idx[k];
      const int c = idx[k + 1];
      if(isHigh)
      {
         if(src[b] > src[a] && src[b] > src[c]) dst[b] = src[b];
      }
      else
      {
         if(src[b] < src[a] && src[b] < src[c]) dst[b] = src[b];
      }
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
   if(prev_calculated == 0)
   {
      ArrayInitialize(shortTermLows,   EMPTY_VALUE);
      ArrayInitialize(shortTermHighs,  EMPTY_VALUE);
      ArrayInitialize(intermTermLows,  EMPTY_VALUE);
      ArrayInitialize(intermTermHighs, EMPTY_VALUE);
      ArrayInitialize(longTermLows,    EMPTY_VALUE);
      ArrayInitialize(longTermHighs,   EMPTY_VALUE);
   }

   if(prev_calculated < rates_total)
   {
      ArrayInitialize(shortTermLows,  EMPTY_VALUE);
      ArrayInitialize(shortTermHighs, EMPTY_VALUE);

      // Detect short-term swings (forward indexing here).
      for(int i = 1; i < rates_total - 2; i++)
      {
         if(low[i]  < low[i - 1]  && low[i]  < low[i + 1])  shortTermLows [i] = low [i];
         if(high[i] > high[i - 1] && high[i] > high[i + 1]) shortTermHighs[i] = high[i];
      }

      // Promote.
      BuildPromoted(shortTermLows,  rates_total, false, intermTermLows);
      BuildPromoted(shortTermHighs, rates_total, true,  intermTermHighs);
      BuildPromoted(intermTermLows, rates_total, false, longTermLows);
      BuildPromoted(intermTermHighs,rates_total, true,  longTermHighs);
   }

   return rates_total;
}
//+------------------------------------------------------------------+
