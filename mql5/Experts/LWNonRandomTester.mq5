//+------------------------------------------------------------------+
//|                                       LWNonRandomTester.mq5     |
//|                                                       lwms       |
//|        Larry Williams non-random behaviour tester (article 20510)|
//+------------------------------------------------------------------+
//| Runs ONE statistical experiment at a time. Selectable via input. |
//| For each new bar:                                                |
//|   1. close any open position from this EA (one-bar holding)      |
//|   2. evaluate the selected predicate                             |
//|   3. if true, open a market BUY at the new bar's open            |
//|                                                                  |
//| The next bar's close exits the trade. The aggregate outcome      |
//| answers the question: "Does the trigger condition shift the      |
//| probability of the next bar closing bullish?"                    |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

enum ENUM_LW_NONRANDOM_MODE
{
   LW_TEST_OPEN_TO_CLOSE_BIAS,
   LW_TEST_AFTER_ONE_DOWN,
   LW_TEST_AFTER_TWO_DOWN,
   LW_TEST_AFTER_THREE_DOWN,
   LW_TEST_AFTER_ONE_UP,
   LW_TEST_AFTER_TWO_UP,
   LW_TEST_AFTER_THREE_UP,
   LW_TEST_AFTER_SHORT_TERM_LOW
};

input group "Information"
input ulong                 InpMagicNumber = 254700910001;
input ENUM_TIMEFRAMES       InpTimeframe   = PERIOD_CURRENT;

input group "Trade & Test"
input ENUM_LW_NONRANDOM_MODE InpMode        = LW_TEST_OPEN_TO_CLOSE_BIAS;
input double                 InpLotSize     = 0.01;

CTrade   g_trade;
datetime g_lastBar = 0;
double   g_ask     = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(LW_DetectFillingMode(_Symbol));
   g_trade.SetDeviationInPoints(LW_DEFAULT_DEVIATION);
   g_lastBar = 0;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { Print("LWNonRandomTester ended, reason=", reason); }

//+------------------------------------------------------------------+
void ClosePositionsByMagic(const ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) == magic)
         g_trade.PositionClose(ticket);
   }
}

bool TriggerForMode(const ENUM_LW_NONRANDOM_MODE mode)
{
   switch(mode)
   {
      case LW_TEST_OPEN_TO_CLOSE_BIAS:    return true;
      case LW_TEST_AFTER_ONE_DOWN:         return LW_IsConsecutiveBarCloseState(_Symbol, InpTimeframe, 1, LW_BAR_DOWN);
      case LW_TEST_AFTER_TWO_DOWN:         return LW_IsConsecutiveBarCloseState(_Symbol, InpTimeframe, 2, LW_BAR_DOWN);
      case LW_TEST_AFTER_THREE_DOWN:       return LW_IsConsecutiveBarCloseState(_Symbol, InpTimeframe, 3, LW_BAR_DOWN);
      case LW_TEST_AFTER_ONE_UP:           return LW_IsConsecutiveBarCloseState(_Symbol, InpTimeframe, 1, LW_BAR_UP);
      case LW_TEST_AFTER_TWO_UP:           return LW_IsConsecutiveBarCloseState(_Symbol, InpTimeframe, 2, LW_BAR_UP);
      case LW_TEST_AFTER_THREE_UP:         return LW_IsConsecutiveBarCloseState(_Symbol, InpTimeframe, 3, LW_BAR_UP);
      case LW_TEST_AFTER_SHORT_TERM_LOW:   return LW_IsShortTermLow(_Symbol, InpTimeframe);
   }
   return false;
}

//+------------------------------------------------------------------+
void OnTick()
{
   g_ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(!LW_IsNewBar(_Symbol, InpTimeframe, g_lastBar)) return;

   if(LW_HasOpenPositionByMagic(InpMagicNumber))
   {
      ClosePositionsByMagic(InpMagicNumber);
      Sleep(50);
   }

   if(TriggerForMode(InpMode))
      g_trade.Buy(NormalizeDouble(InpLotSize, 2), _Symbol, g_ask);
}
//+------------------------------------------------------------------+
