//+------------------------------------------------------------------+
//|                                       LWMarketStructureEA.mq5    |
//|                                                       lwms       |
//|     Larry Williams Market Structure trading EA — Part 2 (20512) |
//+------------------------------------------------------------------+
//| Reads market-structure buffers from LWMarketStructure.ex5 via    |
//| iCustom and trades the confirmation pattern:                     |
//|                                                                  |
//|   BUY  when a short-term swing low confirms an intermediate-term |
//|        low (both indicators flag the same bar in their lows      |
//|        buffers, with the most recent short-term swing being the  |
//|        same bar that holds the intermediate value).              |
//|   SELL  mirror with highs.                                        |
//|                                                                  |
//| Stops at the most recent short-term swing (or intermediate, by   |
//| input). Take-profit is risk-multiple based.                      |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

#resource "\\Indicators\\lwms\\LWMarketStructure.ex5"

enum ENUM_LW_SL_STRUCTURE
{
   LW_SL_AT_SHORT_TERM,
   LW_SL_AT_INTERMEDIATE
};

input group "Information"
input ulong                 InpMagicNumber          = 254700920001;
input ENUM_TIMEFRAMES       InpTimeframe            = PERIOD_CURRENT;

input group "Trade Direction"
input ENUM_LW_TRADE_DIRECTION InpDirection          = LW_TRADE_BOTH;

input group "Stops & Targets"
input ENUM_LW_SL_STRUCTURE  InpSLStructure          = LW_SL_AT_INTERMEDIATE;
input double                InpRiskRewardRatio      = LW_DEFAULT_RR;
input int                   InpMinStopPoints        = 100;
input int                   InpMaxStopPoints        = 600;

input group "Sizing"
input ENUM_LW_SIZING_MODEL  InpSizingModel          = LW_SIZE_RISK_PCT;
input double                InpRiskPerTradePct      = LW_DEFAULT_RISK_PCT;
input double                InpFixedLot             = 0.10;
input double                InpMaxLotSize           = 1.00;

CTrade   g_trade;
int      g_handle  = INVALID_HANDLE;
datetime g_lastBar = 0;
double   g_point   = 0.0;

double shortLows []; double shortHighs []; double intermLows []; double intermHighs[];

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(LW_DetectFillingMode(_Symbol));
   g_trade.SetDeviationInPoints(LW_DEFAULT_DEVIATION);

   g_handle = iCustom(_Symbol, InpTimeframe, "::Indicators\\lwms\\LWMarketStructure.ex5");
   if(g_handle == INVALID_HANDLE)
   {
      Print("Failed to load LWMarketStructure: ", GetLastError());
      return INIT_FAILED;
   }

   ArraySetAsSeries(shortLows,   true);
   ArraySetAsSeries(shortHighs,  true);
   ArraySetAsSeries(intermLows,  true);
   ArraySetAsSeries(intermHighs, true);

   g_point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_lastBar = 0;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_handle != INVALID_HANDLE) IndicatorRelease(g_handle);
}

//+------------------------------------------------------------------+
bool RefreshBuffers()
{
   if(CopyBuffer(g_handle, 0, 0, 200, shortLows ) <= 0) return false;
   if(CopyBuffer(g_handle, 1, 0, 200, shortHighs) <= 0) return false;
   if(CopyBuffer(g_handle, 2, 0, 200, intermLows ) <= 0) return false;
   if(CopyBuffer(g_handle, 3, 0, 200, intermHighs) <= 0) return false;
   ArraySetAsSeries(shortLows,   true);
   ArraySetAsSeries(shortHighs,  true);
   ArraySetAsSeries(intermLows,  true);
   ArraySetAsSeries(intermHighs, true);
   return true;
}

bool BuySignalIndex(int &outIdx)
{
   // The most recent short-term low must coincide with an intermediate low.
   if(shortLows[2] == EMPTY_VALUE) return false;
   for(int i = 2; i < ArraySize(shortLows); i++)
   {
      if(shortLows[i] != EMPTY_VALUE)
      {
         if(intermLows[i] != EMPTY_VALUE) { outIdx = i; return true; }
         return false;
      }
   }
   return false;
}

bool SellSignalIndex(int &outIdx)
{
   if(shortHighs[2] == EMPTY_VALUE) return false;
   for(int i = 2; i < ArraySize(shortHighs); i++)
   {
      if(shortHighs[i] != EMPTY_VALUE)
      {
         if(intermHighs[i] != EMPTY_VALUE) { outIdx = i; return true; }
         return false;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
double SelectStopForBuy()
{
   if(InpSLStructure == LW_SL_AT_SHORT_TERM) return shortLows[2];
   for(int i = 0; i < ArraySize(intermLows); i++)
      if(intermLows[i] != EMPTY_VALUE) return intermLows[i];
   return 0.0;
}

double SelectStopForSell()
{
   if(InpSLStructure == LW_SL_AT_SHORT_TERM) return shortHighs[2];
   for(int i = 0; i < ArraySize(intermHighs); i++)
      if(intermHighs[i] != EMPTY_VALUE) return intermHighs[i];
   return 0.0;
}

double ComputeVolume(const ENUM_ORDER_TYPE order_type,
                     const double entry, const double sl)
{
   if(InpSizingModel == LW_SIZE_MANUAL)
      return MathMin(InpFixedLot, InpMaxLotSize);

   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double v;
   if(InpSizingModel == LW_SIZE_RISK_PCT)
      v = LW_SizeBrokerAware(_Symbol, order_type, entry, sl, balance, InpRiskPerTradePct);
   else
      v = LW_SizeLegacy(_Symbol, balance, InpRiskPerTradePct, MathAbs(entry - sl));
   v = MathMin(v, InpMaxLotSize);
   return LW_NormalizeVolume(_Symbol, v);
}

//+------------------------------------------------------------------+
void TryOpen(const ENUM_LW_DIRECTION dir)
{
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double entry = (dir == LW_DIR_BUY) ? ask : bid;
   const double sl = (dir == LW_DIR_BUY) ? SelectStopForBuy() : SelectStopForSell();
   if(sl == 0.0) return;
   const double sl_distance = MathAbs(entry - sl);
   if(sl_distance < InpMinStopPoints * g_point) return;
   if(sl_distance > InpMaxStopPoints * g_point) return;

   const double tp = LW_TpFromRR(dir, entry, sl, InpRiskRewardRatio);
   const ENUM_ORDER_TYPE ot = (dir == LW_DIR_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double vol = ComputeVolume(ot, entry, sl);
   if(vol <= 0.0) return;

   if(dir == LW_DIR_BUY) g_trade.Buy(vol, _Symbol, entry, sl, tp, "LW market-structure");
   else                  g_trade.Sell(vol, _Symbol, entry, sl, tp, "LW market-structure");
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!LW_IsNewBar(_Symbol, InpTimeframe, g_lastBar)) return;
   if(LW_HasOpenPositionByMagic(InpMagicNumber)) return;
   if(!RefreshBuffers()) return;

   int idx;
   if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_LONG_ONLY)
      && BuySignalIndex(idx))      TryOpen(LW_DIR_BUY);
   else if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_SHORT_ONLY)
      && SellSignalIndex(idx))     TryOpen(LW_DIR_SELL);
}
//+------------------------------------------------------------------+
