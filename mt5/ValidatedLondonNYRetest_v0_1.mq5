#property strict
#property version   "0.100"
#property description "DEMO/TESTER-ONLY evidence-backed XAUUSD London-low break/retest short strategy."

#include <Trade/Trade.mqh>

CTrade trade;

input ulong  InpMagic                    = 26100801;
input string InpTag                      = "VALIDATED_RETEST_v0_1";

// Positioning: split total exposure into several hedged tickets without increasing total risk.
input double InpTotalLot                 = 0.10;
input int    InpTickets                  = 5;
input int    InpDeviationPoints          = 50;
input double InpMaxSpreadPrice           = 0.50;

// Frozen research rule in UTC.
input int    InpLondonStartUTC           = 6;
input int    InpLondonEndUTC             = 12;
input int    InpTradeWindowEndUTC        = 17;
input double InpBreakATR                 = 0.30;
input double InpRetestBandATR            = 0.40;
input int    InpRetestMaxBars            = 10;
input double InpR240Max                  = -8.0;
input double InpMaxBreakDepthATR         = 2.0;
input int    InpHoldMinutes              = 60;

// XM server convention: GMT+2 in winter, GMT+3 in summer (EU DST schedule).
input bool   InpUseEUDSTServerClock      = true;
input int    InpWinterServerUTCOffset    = 2;
input int    InpSummerServerUTCOffset    = 3;
input int    InpFixedServerUTCOffset     = 2;

// Account safety. Strategy itself has no price stop because the frozen research rule did not use one.
input double InpEmergencyEquityLossPct   = 20.0;
input bool   InpRequireHedging           = true;
input bool   InpRequireGoldSymbol        = true;

datetime g_last_bar0 = 0;
int      g_utc_day_key = -1;
bool     g_have_london = false;
double   g_london_high = 0.0;
double   g_london_low = 0.0;
double   g_session_atr = 0.0;
bool     g_break_found = false;
double   g_break_close = 0.0;
int      g_bars_after_break = 0;
bool     g_day_done = false;
bool     g_pending_entry = false;
datetime g_entry_time = 0;
bool     g_halted = false;
double   g_start_equity = 0.0;
int      g_log = INVALID_HANDLE;

int LastSunday(const int year,const int month)
  {
   MqlDateTime x={};
   if(month==12)
     {
      x.year=year+1; x.mon=1; x.day=1;
     }
   else
     {
      x.year=year; x.mon=month+1; x.day=1;
     }
   datetime first_next=StructToTime(x);
   datetime last_day=first_next-86400;
   MqlDateTime d={};
   TimeToStruct(last_day,d);
   return d.day-d.day_of_week;
  }

int ServerUTCOffsetHours(const datetime server_time)
  {
   if(!InpUseEUDSTServerClock)
      return InpFixedServerUTCOffset;

   MqlDateTime t={};
   TimeToStruct(server_time,t);

   bool summer=false;
   if(t.mon>3 && t.mon<10)
      summer=true;
   else if(t.mon==3)
     {
      int ls=LastSunday(t.year,3);
      if(t.day>ls || (t.day==ls && t.hour>=3)) summer=true;
     }
   else if(t.mon==10)
     {
      int ls=LastSunday(t.year,10);
      if(t.day<ls || (t.day==ls && t.hour<4)) summer=true;
     }

   return summer ? InpSummerServerUTCOffset : InpWinterServerUTCOffset;
  }

datetime ServerToUTC(const datetime server_time)
  {
   return server_time-(datetime)(ServerUTCOffsetHours(server_time)*3600);
  }

int UTCDateKey(const datetime server_time)
  {
   MqlDateTime t={};
   TimeToStruct(ServerToUTC(server_time),t);
   return t.year*10000+t.mon*100+t.day;
  }

void ResetUTCday(const int key)
  {
   g_utc_day_key=key;
   g_have_london=false;
   g_london_high=0.0;
   g_london_low=0.0;
   g_session_atr=0.0;
   g_break_found=false;
   g_break_close=0.0;
   g_bars_after_break=0;
   g_day_done=false;
   g_pending_entry=false;
  }

double SimpleATR20(const int shift)
  {
   if(Bars(_Symbol,PERIOD_M1)<shift+21)
      return 0.0;

   double sum=0.0;
   for(int s=shift; s<shift+20; ++s)
     {
      double h=iHigh(_Symbol,PERIOD_M1,s);
      double l=iLow(_Symbol,PERIOD_M1,s);
      double pc=iClose(_Symbol,PERIOD_M1,s+1);
      if(h<=0.0 || l<=0.0 || pc<=0.0)
         return 0.0;
      double tr=MathMax(h-l,MathMax(MathAbs(h-pc),MathAbs(l-pc)));
      sum+=tr;
     }
   return sum/20.0;
  }

double NormalizeVolume(double v)
  {
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double st=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(st<=0.0) st=mn;
   if(st<=0.0) return 0.0;
   v=MathMax(mn,MathMin(mx,v));
   v=MathFloor(v/st+1e-9)*st;
   int digits=2;
   if(st<0.01) digits=3;
   if(st<0.001) digits=4;
   return NormalizeDouble(v,digits);
  }

bool IsOwnedSelectedPosition()
  {
   if(PositionGetString(POSITION_SYMBOL)!=_Symbol) return false;
   if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagic) return false;
   return true;
  }

int OwnedPositionCount()
  {
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;--i)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(IsOwnedSelectedPosition()) ++n;
     }
   return n;
  }

double OwnedVolume()
  {
   double v=0.0;
   for(int i=PositionsTotal()-1;i>=0;--i)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(IsOwnedSelectedPosition()) v+=PositionGetDouble(POSITION_VOLUME);
     }
   return v;
  }

void LogEvent(const string event,const string detail="")
  {
   MqlTick tick={}; SymbolInfoTick(_Symbol,tick);
   string line=StringFormat("VRET,%s,server=%s,utc=%s,day=%d,pos=%d,vol=%.2f,bid=%.3f,ask=%.3f,london_low=%.3f,atr=%.3f,%s",
                            event,
                            TimeToString((datetime)tick.time,TIME_DATE|TIME_SECONDS),
                            TimeToString(ServerToUTC((datetime)tick.time),TIME_DATE|TIME_SECONDS),
                            g_utc_day_key,OwnedPositionCount(),OwnedVolume(),tick.bid,tick.ask,g_london_low,g_session_atr,detail);
   Print(line);
   if(g_log!=INVALID_HANDLE)
     {
      FileWrite(g_log,TimeToString((datetime)tick.time,TIME_DATE|TIME_SECONDS),
                TimeToString(ServerToUTC((datetime)tick.time),TIME_DATE|TIME_SECONDS),
                event,g_utc_day_key,OwnedPositionCount(),OwnedVolume(),tick.bid,tick.ask,
                g_london_low,g_london_high,g_session_atr,detail);
      FileFlush(g_log);
     }
  }

void CloseOwned(const string reason)
  {
   LogEvent("CLOSE_START",reason);
   for(int i=PositionsTotal()-1;i>=0;--i)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(!IsOwnedSelectedPosition()) continue;
      if(!trade.PositionClose(ticket,(ulong)InpDeviationPoints))
         PrintFormat("VRET,CLOSE_FAIL,ticket=%I64u,ret=%u,%s",ticket,trade.ResultRetcode(),trade.ResultRetcodeDescription());
     }
  }

void RecoverOpenCampaign()
  {
   datetime earliest=0;
   for(int i=PositionsTotal()-1;i>=0;--i)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !IsOwnedSelectedPosition()) continue;
      datetime pt=(datetime)PositionGetInteger(POSITION_TIME);
      if(earliest==0 || pt<earliest) earliest=pt;
     }
   if(earliest>0)
     {
      g_entry_time=earliest;
      LogEvent("RECOVER_OPEN",StringFormat("entry=%s",TimeToString(g_entry_time,TIME_DATE|TIME_SECONDS)));
     }
  }

bool OpenShortBasket()
  {
   if(g_halted) return false;
   if(OwnedPositionCount()>0) return false;

   MqlTick tick={};
   if(!SymbolInfoTick(_Symbol,tick)) return false;
   double spread=tick.ask-tick.bid;
   if(spread>InpMaxSpreadPrice)
     {
      LogEvent("ENTRY_SKIP",StringFormat("spread=%.3f>max=%.3f",spread,InpMaxSpreadPrice));
      return false;
     }

   int tickets=(InpTickets<1 ? 1 : InpTickets);
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   if(mn<=0.0) return false;
   int max_tickets=(int)MathFloor(InpTotalLot/mn+1e-9);
   if(max_tickets<1) return false;
   tickets=(tickets<max_tickets ? tickets : max_tickets);

   double each=NormalizeVolume(InpTotalLot/tickets);
   if(each<=0.0) return false;

   int opened=0;
   for(int i=0;i<tickets;++i)
     {
      if(trade.Sell(each,_Symbol,0.0,0.0,0.0,InpTag))
         ++opened;
      else
         PrintFormat("VRET,SELL_FAIL,index=%d,ret=%u,%s",i,trade.ResultRetcode(),trade.ResultRetcodeDescription());
     }

   if(opened>0)
     {
      MqlTick now={}; SymbolInfoTick(_Symbol,now);
      g_entry_time=(datetime)now.time;
      LogEvent("ENTRY",StringFormat("requested_tickets=%d;opened=%d;each=%.2f;total_actual=%.2f",tickets,opened,each,OwnedVolume()));
      return true;
     }
   return false;
  }

void ProcessClosedM1()
  {
   datetime bt=iTime(_Symbol,PERIOD_M1,1);
   if(bt<=0) return;

   int key=UTCDateKey(bt);
   if(key!=g_utc_day_key)
     {
      ResetUTCday(key);
      LogEvent("DAY_RESET");
     }

   MqlDateTime u={};
   TimeToStruct(ServerToUTC(bt),u);

   double o=iOpen(_Symbol,PERIOD_M1,1);
   double h=iHigh(_Symbol,PERIOD_M1,1);
   double l=iLow(_Symbol,PERIOD_M1,1);
   double c=iClose(_Symbol,PERIOD_M1,1);
   if(o<=0.0 || h<=0.0 || l<=0.0 || c<=0.0) return;

   if(u.hour>=InpLondonStartUTC && u.hour<InpLondonEndUTC)
     {
      if(!g_have_london)
        {
         g_london_high=h;
         g_london_low=l;
         g_have_london=true;
        }
      else
        {
         if(h>g_london_high) g_london_high=h;
         if(l<g_london_low)  g_london_low=l;
        }

      double a=SimpleATR20(1);
      if(a>0.0) g_session_atr=a;
      return;
     }

   if(g_day_done || !g_have_london || g_session_atr<=0.0)
      return;

   if(u.hour<InpLondonEndUTC || u.hour>=InpTradeWindowEndUTC)
      return;

   if(!g_break_found)
     {
      double threshold=g_london_low-InpBreakATR*g_session_atr;
      if(c<=threshold)
        {
         g_break_found=true;
         g_break_close=c;
         g_bars_after_break=0;
         LogEvent("BREAK",StringFormat("close=%.3f;threshold=%.3f;depth_atr=%.3f",c,threshold,(g_london_low-c)/g_session_atr));
        }
      return;
     }

   ++g_bars_after_break;
   if(g_bars_after_break>InpRetestMaxBars)
     {
      g_day_done=true;
      LogEvent("NO_RETEST",StringFormat("bars=%d",g_bars_after_break-1));
      return;
     }

   bool rejection=(h>=g_london_low-InpRetestBandATR*g_session_atr && c<g_london_low && c<o);
   if(!rejection)
      return;

   double c240=iClose(_Symbol,PERIOD_M1,241);
   double r240=(c240>0.0 ? (c-c240)/g_session_atr : 999.0);
   double depth=(g_london_low-g_break_close)/g_session_atr;
   bool pass=(r240<=InpR240Max && depth<=InpMaxBreakDepthATR);

   LogEvent("REJECTION",StringFormat("r240=%.3f;max=%.3f;break_depth=%.3f;max_depth=%.3f;pass=%s",
                                      r240,InpR240Max,depth,InpMaxBreakDepthATR,pass?"true":"false"));
   g_day_done=true;
   if(pass) g_pending_entry=true;
  }

void ManageCampaign(const datetime now)
  {
   int pc=OwnedPositionCount();
   if(pc<=0)
     {
      g_entry_time=0;
      return;
     }

   if(g_entry_time==0) RecoverOpenCampaign();
   if(g_entry_time>0 && now-g_entry_time>=InpHoldMinutes*60)
     {
      CloseOwned(StringFormat("time_exit;held_sec=%I64d",(long)(now-g_entry_time)));
      if(OwnedPositionCount()==0) g_entry_time=0;
     }
  }

void EmergencyCheck()
  {
   if(g_halted || InpEmergencyEquityLossPct<=0.0 || g_start_equity<=0.0) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double floor_eq=g_start_equity*(1.0-InpEmergencyEquityLossPct/100.0);
   if(eq<=floor_eq)
     {
      g_halted=true;
      CloseOwned(StringFormat("equity_emergency;equity=%.2f;floor=%.2f",eq,floor_eq));
      LogEvent("HALTED","equity_emergency");
     }
  }

int OnInit()
  {
   bool tester=(bool)MQLInfoInteger(MQL_TESTER);
   if(!tester && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     {
      Print("INIT_FAILED: This EA is locked to Strategy Tester or DEMO accounts.");
      return INIT_FAILED;
     }

   string upper_symbol=_Symbol;
   StringToUpper(upper_symbol);
   if(InpRequireGoldSymbol && StringFind(upper_symbol,"GOLD")<0 && StringFind(upper_symbol,"XAU")<0)
     {
      Print("INIT_FAILED: This research rule is for GOLD/XAUUSD only.");
      return INIT_FAILED;
     }

   if(InpRequireHedging && AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("INIT_FAILED: Hedging account required when splitting exposure across tickets.");
      return INIT_FAILED;
     }

   if(InpTotalLot<=0.0 || InpTickets<1 || InpHoldMinutes<1 || InpRetestMaxBars<1 || InpMaxSpreadPrice<=0.0)
      return INIT_PARAMETERS_INCORRECT;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   g_start_equity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_last_bar0=iTime(_Symbol,PERIOD_M1,0);

   g_log=FileOpen("ValidatedLondonNYRetest_v0_1.csv",FILE_COMMON|FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(g_log!=INVALID_HANDLE)
     {
      FileSeek(g_log,0,SEEK_END);
      if(FileTell(g_log)==0)
         FileWrite(g_log,"server_time","utc_time","event","utc_day","positions","volume","bid","ask","london_low","london_high","session_atr","detail");
     }

   RecoverOpenCampaign();
   LogEvent("INIT",StringFormat("version=0.10;tester=%s;total_lot=%.2f;tickets=%d;hold=%d;server_offsets=%d/%d;research_side=SHORT_ONLY",
                                tester?"true":"false",InpTotalLot,InpTickets,InpHoldMinutes,InpWinterServerUTCOffset,InpSummerServerUTCOffset));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   LogEvent("DEINIT",StringFormat("reason=%d",reason));
   if(g_log!=INVALID_HANDLE) FileClose(g_log);
  }

void OnTick()
  {
   MqlTick tick={};
   if(!SymbolInfoTick(_Symbol,tick)) return;

   EmergencyCheck();
   ManageCampaign((datetime)tick.time);
   if(g_halted) return;

   datetime bar0=iTime(_Symbol,PERIOD_M1,0);
   if(bar0>0 && bar0!=g_last_bar0)
     {
      g_last_bar0=bar0;
      ProcessClosedM1();

      if(g_pending_entry)
        {
         g_pending_entry=false;
         if(OwnedPositionCount()==0)
            OpenShortBasket();
         else
            LogEvent("ENTRY_SKIP","owned_position_already_open");
        }
     }
  }
