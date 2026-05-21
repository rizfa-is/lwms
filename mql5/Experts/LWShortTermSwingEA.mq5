//+------------------------------------------------------------------+
//|                                       LWShortTermSwingEA.mq5     |
//|                                                       lwms       |
//|     Larry Williams short-term swing trader — Part 4 (20716)     |
//+------------------------------------------------------------------+
//| BUY when bar 2 forms a short-term low (Williams 3-bar rule with  |
//| outside / inside filters). SELL on the swing-high mirror.         |
//| Several exit modes (article 20716):                              |
//|   TP_HOLD_ONE_BAR        — close on next bar open                |
//|   TP_FIXED_RR_1_TO_X     — fixed RR (1, 1.5, 2, 3)               |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

enum ENUM_LW_TP_MODE
{
   LW_TP_HOLD_ONE_BAR,
   LW_TP_FIXED_RR_1_TO_1,
   LW_TP_FIXED_RR_1_TO_1_5,
   LW_TP_FIXED_RR_1_TO_2,
   LW_TP_FIXED_RR_1_TO_3
};

input group "Information"
input ulong                 InpMagicNumber          = 254700930001;
input ENUM_TIMEFRAMES       InpTimeframe            = PERIOD_CURRENT;

input group "Direction & exits"
input ENUM_LW_TRADE_DIRECTION InpDirection          = LW_TRADE_BOTH;
input ENUM_LW_TP_MODE         InpTpMode             = LW_TP_FIXED_RR_1_TO_2;

input group "Sizing"
input ENUM_LW_SIZING_MODEL  InpSizingModel          = LW_SIZE_RISK_PCT;
input double                InpRiskPerTradePct      = LW_DEFAULT_RISK_PCT;
input double                InpFixedLot             = 0.10;
input double                InpMaxLotSize           = 1.00;

CTrade   g_trade;
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(LW_DetectFillingMode(_Symbol));
   g_trade.SetDeviationInPoints(LW_DEFAULT_DEVIATION);
   g_lastBar = 0;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { }

//+------------------------------------------------------------------+
double RrFromMode()
{
   switch(InpTpMode)
   {
      case LW_TP_FIXED_RR_1_TO_1:    return 1.0;
      case LW_TP_FIXED_RR_1_TO_1_5:  return 1.5;
      case LW_TP_FIXED_RR_1_TO_2:    return 2.0;
      case LW_TP_FIXED_RR_1_TO_3:    return 3.0;
   }
   return 0.0; // hold-one-bar exit handled separately
}

double ComputeVolume(const ENUM_ORDER_TYPE order_type,
                     const double entry, const double sl)
{
   if(InpSizingModel == LW_SIZE_MANUAL) return MathMin(InpFixedLot, InpMaxLotSize);
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
void ClosePositionsByMagic(const ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong ticket = PositionGetTicket(i);
      if((ulong)PositionGetInteger(POSITION_MAGIC) == magic)
         g_trade.PositionClose(ticket);
   }
}

void OpenWith(const ENUM_LW_DIRECTION dir, const double sl_price)
{
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double entry = (dir == LW_DIR_BUY) ? ask : bid;
   const double rr = RrFromMode();
   double tp = 0.0;
   if(rr > 0.0) tp = LW_TpFromRR(dir, entry, sl_price, rr);
   const ENUM_ORDER_TYPE ot = (dir == LW_DIR_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double vol = ComputeVolume(ot, entry, sl_price);
   if(vol <= 0.0) return;
   if(dir == LW_DIR_BUY) g_trade.Buy (vol, _Symbol, entry, sl_price, tp, "LW short-term swing");
   else                  g_trade.Sell(vol, _Symbol, entry, sl_price, tp, "LW short-term swing");
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!LW_IsNewBar(_Symbol, InpTimeframe, g_lastBar)) return;

   // Hold-one-bar exit: close any position carried over from prior bar.
   if(InpTpMode == LW_TP_HOLD_ONE_BAR && LW_HasOpenPositionByMagic(InpMagicNumber))
   {
      ClosePositionsByMagic(InpMagicNumber);
      Sleep(50);
   }
   if(LW_HasOpenPositionByMagic(InpMagicNumber)) return;

   if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_LONG_ONLY)
      && LW_IsShortTermLow(_Symbol, InpTimeframe))
   {
      const double sl = iLow(_Symbol, InpTimeframe, 2);
      OpenWith(LW_DIR_BUY, sl);
      return;
   }
   if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_SHORT_ONLY)
      && LW_IsShortTermHigh(_Symbol, InpTimeframe))
   {
      const double sl = iHigh(_Symbol, InpTimeframe, 2);
      OpenWith(LW_DIR_SELL, sl);
   }
}
//+------------------------------------------------------------------+
