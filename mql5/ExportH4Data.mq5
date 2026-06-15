//+------------------------------------------------------------------+
//| ExportH4Data.mq5                                                  |
//| Exporta XAUUSD H4 a CSV en Common/Files para el backtest Python  |
//+------------------------------------------------------------------+
#property script_show_inputs

input string   Symbol_   = "XAUUSD";                 // Simbolo: XAUUSD, XAGUSD, USOIL, etc.
input datetime StartDate = D'2024.01.01 00:00';
input datetime EndDate   = D'2026.06.10 23:59';
input string   FileName  = "";                       // Vacio => <simbolo>_h4_data.csv

void OnStart()
  {
   string sym = Symbol_;
   string fname = FileName;
   if(fname == "")
     {
      string low = sym; StringToLower(low);
      fname = low + "_h4_data.csv";
     }
   Print("Exportando datos ", sym, " H4...");

   // Abrir archivo en Common/Files
   int fh = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(fh == INVALID_HANDLE)
     {
      Print("ERROR: No se pudo crear el archivo ", fname);
      return;
     }

   // Cabecera
   FileWrite(fh, "datetime", "open", "high", "low", "close", "volume");

   // Copiar barras H4 del simbolo
   MqlRates rates[];
   int copied = CopyRates(sym, PERIOD_H4, StartDate, EndDate, rates);

   if(copied <= 0)
     {
      Print("ERROR: No se copiaron barras. Codigo: ", GetLastError());
      Print("Verifica que ", sym, " H4 este cargado en el terminal (abre un grafico).");
      FileClose(fh);
      return;
     }

   Print("Barras obtenidas: ", copied);

   int dig = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   if(dig <= 0) dig = 2;

   for(int i = 0; i < copied; i++)
     {
      string dt = TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES);
      FileWrite(fh,
                dt,
                DoubleToString(rates[i].open,  dig),
                DoubleToString(rates[i].high,  dig),
                DoubleToString(rates[i].low,   dig),
                DoubleToString(rates[i].close, dig),
                IntegerToString(rates[i].tick_volume));
     }

   FileClose(fh);
   Print("Exportacion completada: ", copied, " velas H4 guardadas en Common/Files/", fname);
   MessageBox("Exportacion exitosa!\n" + sym + " - " + IntegerToString(copied) + " velas H4\nArchivo: " + fname,
              "Export H4 Data", MB_OK | MB_ICONINFORMATION);
  }
//+------------------------------------------------------------------+
