==================================
Modifiche dell'anagrafica prodotti
==================================

Disaccoppiamento descrizioni template - variante e relativo wizard di sovrascrittura
====================================================================================

Aggiunto wizard Configurazione/Wizard Ricalcolo Campi/Descrizione Varianti. Serve per copiare
i valori dei campi *description, description_sale, description_purchase, description_picking* (e le loro traduzioni)
di product.template in quelli di product.product.

Necessario per quei databases in cui ci siano dei prodotti pre-esistenti prima di avere inserito il disaccoppiamento.
In tal caso andrà lanciato una sola volta, subito dopo aver aggiornato il modulo (a regime, non sarà necessario).
