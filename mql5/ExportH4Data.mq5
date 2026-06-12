//+------------------------------------------------------------------+
//| ExportH4Data.mq5                                                  |
//| Exporta XAUUSD H4 a CSV en Common/Files para el backtest Python  |
//+------------------------------------------------------------------+
#property script_show_inputs

input datetime StartDate = D'2024.01.01 00:00';
input datetime EndDate   = D'2026.06.10 23:59';
input string   FileName  = "xauusd_h4_data.csv";

void OnStart()
  {
   Print("Exportando datos XAUUSD H4...");

   // Abrir archivo en Common/Files
   int fh = FileOpen(FileName, FILE_WRITE | FILE_CSV | FILE_COMMON, ',');
   if(fh == INVALID_HANDLE)
     {
      Print("ERROR: No se pudo crear el archivo ", FileName);
      return;
     }

   // Cabecera
   FileWrite(fh, "datetime", "open", "high", "low", "close", "volume");

   // Copiar barras H4 de XAUUSD
   MqlRates rates[];
   int copied = CopyRates("XAUUSD", PERIOD_H4, StartDate, EndDate, rates);

   if(copied <= 0)
     {
      Print("ERROR: No se copiaron barras. Codigo: ", GetLastError());
      Print("Verifica que XAUUSD H4 este cargado en el terminal.");
      FileClose(fh);
      return;
     }

   Print("Barras obtenidas: ", copied);

   for(int i = 0; i < copied; i++)
     {
      string dt = TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES);
      FileWrite(fh,
                dt,
                DoubleToString(rates[i].open,  2),
                DoubleToString(rates[i].high,  2),
                DoubleToString(rates[i].low,   2),
                DoubleToString(rates[i].close, 2),
                IntegerToString(rates[i].tick_volume));
     }

   FileClose(fh);
   Print("Exportacion completada: ", copied, " velas H4 guardadas en Common/Files/", FileName);
   MessageBox("Exportacion exitosa!\n" + IntegerToString(copied) + " velas H4\nArchivo: " + FileName,
              "Export H4 Data", MB_OK | MB_ICONINFORMATION);
  }
//+------------------------------------------------------------------+
