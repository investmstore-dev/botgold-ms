//+------------------------------------------------------------------+
//| BotGold_Bridge.mq5 — Puente archivo ↔ Python                    |
//| Lee commands.json, ejecuta ordenes, escribe state.json           |
//+------------------------------------------------------------------+
#property copyright "Mining Store GOLD"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

CTrade trade;

string CMD_FILE     = "botgold_command.json";
string STATE_FILE   = "botgold_state.json";
string DONE_FILE    = "botgold_done.json";
string CANDLES_FILE = "botgold_candles.csv";

int      lastCmdId       = -1;
datetime lastCandleWrite = 0;

int OnInit()
{
   trade.SetExpertMagicNumber(20260610);
   EventSetMillisecondTimer(1000);
   WriteState("init");
   Print("BotGold Bridge iniciado");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   WriteState("stopped");
}

void OnTimer()
{
   WriteState("running");
   ReadAndExecuteCommand();

   // Exportar velas H4 cada 60 segundos
   if(TimeCurrent() - lastCandleWrite >= 60)
   {
      WriteCandles();
      lastCandleWrite = TimeCurrent();
   }
}

//--- Exporta las ultimas 250 velas H4 a CSV en Common/Files
void WriteCandles()
{
   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_H4, 0, 250, rates);
   if(copied <= 0) return;

   int fh = FileOpen(CANDLES_FILE, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(fh == INVALID_HANDLE) return;

   FileWriteString(fh, "datetime,open,high,low,close,volume\n");
   for(int i = 0; i < copied; i++)
   {
      FileWriteString(fh, StringFormat("%s,%.2f,%.2f,%.2f,%.2f,%d\n",
         TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS),
         rates[i].open, rates[i].high, rates[i].low, rates[i].close,
         (int)rates[i].tick_volume));
   }
   FileClose(fh);
}

void OnTick()
{
   WriteState("running");
}

//--- Escribe el estado actual de la cuenta y posiciones
void WriteState(string status)
{
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin   = AccountInfoDouble(ACCOUNT_MARGIN);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double profit   = AccountInfoDouble(ACCOUNT_PROFIT);
   long   login    = AccountInfoInteger(ACCOUNT_LOGIN);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   string server   = AccountInfoString(ACCOUNT_SERVER);

   string posJson = "";
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         string sym    = PositionGetString(POSITION_SYMBOL);
         double vol    = PositionGetDouble(POSITION_VOLUME);
         double openP  = PositionGetDouble(POSITION_PRICE_OPEN);
         double sl     = PositionGetDouble(POSITION_SL);
         double tp     = PositionGetDouble(POSITION_TP);
         double pnl    = PositionGetDouble(POSITION_PROFIT);
         int    ptype  = (int)PositionGetInteger(POSITION_TYPE);
         string typeStr = (ptype == POSITION_TYPE_BUY) ? "long" : "short";

         if(posJson != "") posJson += ",";
         posJson += StringFormat(
            "{\"ticket\":%llu,\"symbol\":\"%s\",\"type\":\"%s\","
            "\"volume\":%.2f,\"open_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"profit\":%.2f}",
            ticket, sym, typeStr, vol, openP, sl, tp, pnl
         );
      }
   }

   string json = StringFormat(
      "{\"status\":\"%s\",\"login\":%lld,\"balance\":%.2f,\"equity\":%.2f,"
      "\"margin\":%.2f,\"free_margin\":%.2f,\"profit\":%.2f,"
      "\"currency\":\"%s\",\"server\":\"%s\","
      "\"positions_total\":%d,\"positions\":[%s],\"time\":\"%s\"}",
      status, login, balance, equity, margin, freeMargin, profit,
      currency, server, total, posJson,
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS)
   );

   int fh = FileOpen(STATE_FILE, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(fh != INVALID_HANDLE) { FileWriteString(fh, json); FileClose(fh); }
}

//--- Lee y ejecuta comando del archivo JSON
void ReadAndExecuteCommand()
{
   if(!FileIsExist(CMD_FILE, FILE_COMMON)) return;

   int fh = FileOpen(CMD_FILE, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(fh == INVALID_HANDLE) return;

   string raw = "";
   while(!FileIsEnding(fh)) raw += FileReadString(fh);
   FileClose(fh);

   if(raw == "") return;

   // Parsear campos clave del JSON minimalista
   string action = ExtractJsonStr(raw, "action");
   int    cmdId  = (int)ExtractJsonNum(raw, "id");

   if(cmdId == lastCmdId) return;   // Ya procesado
   lastCmdId = cmdId;

   Print("Comando recibido: ", action, " id=", cmdId);

   if(action == "open_long" || action == "open_short")
   {
      string symbol = ExtractJsonStr(raw, "symbol");
      double volume = ExtractJsonNum(raw, "volume");
      double sl     = ExtractJsonNum(raw, "sl");
      double tp     = ExtractJsonNum(raw, "tp");

      if(symbol == "") symbol = "XAUUSD";
      if(volume <= 0)  volume = 0.01;

      ENUM_ORDER_TYPE otype = (action == "open_long") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      bool ok = trade.PositionOpen(symbol, otype, volume, 0, sl, tp, "BotGold");
      WriteDone(cmdId, action, ok ? "ok" : "error", trade.ResultRetcode());
   }
   else if(action == "modify_sl")
   {
      ulong  ticket = (ulong)ExtractJsonNum(raw, "ticket");
      double newSL  = ExtractJsonNum(raw, "sl");
      bool ok = trade.PositionModify(ticket, newSL, 0);
      WriteDone(cmdId, action, ok ? "ok" : "error", trade.ResultRetcode());
   }
   else if(action == "close")
   {
      ulong ticket = (ulong)ExtractJsonNum(raw, "ticket");
      bool ok = trade.PositionClose(ticket);
      WriteDone(cmdId, action, ok ? "ok" : "error", trade.ResultRetcode());
   }
   else if(action == "close_all")
   {
      for(int i = PositionsTotal()-1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t > 0) trade.PositionClose(t);
      }
      WriteDone(cmdId, action, "ok", 0);
   }
   else if(action == "ping")
   {
      WriteDone(cmdId, "ping", "pong", 0);
   }
}

void WriteDone(int id, string action, string result, uint retcode)
{
   string json = StringFormat(
      "{\"id\":%d,\"action\":\"%s\",\"result\":\"%s\",\"retcode\":%u,\"time\":\"%s\"}",
      id, action, result, retcode,
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS)
   );
   int fh = FileOpen(DONE_FILE, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(fh != INVALID_HANDLE) { FileWriteString(fh, json); FileClose(fh); }
   Print("Comando ejecutado: ", action, " → ", result, " retcode=", retcode);
}

//--- Helpers parseo JSON simple
string ExtractJsonStr(string json, string key)
{
   string search = "\"" + key + "\":\"";
   int pos = StringFind(json, search);
   if(pos < 0) return "";
   pos += StringLen(search);
   int end = StringFind(json, "\"", pos);
   if(end < 0) return "";
   return StringSubstr(json, pos, end - pos);
}

double ExtractJsonNum(string json, string key)
{
   string search = "\"" + key + "\":";
   int pos = StringFind(json, search);
   if(pos < 0) return 0;
   pos += StringLen(search);
   string rest = StringSubstr(json, pos, 30);
   return StringToDouble(rest);
}
//+------------------------------------------------------------------+
