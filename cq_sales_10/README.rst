===================================
Sistemazioni Area Vendite, rel.10
===================================

------------------
Note Installazione
------------------

Eliminare il template email degli ordini di vendita "Sales Order - Send by Email" in modo che venga ricaricato il nostro presente nei data di questo modulo.
Per la gestione degli sconti seguire le istruzioni qui sotto.

---------------------------------
Gestione Cessione Gratuita art. 2
---------------------------------

Per la gestione della cessione gratuita il modulo, all'installazione, aggiunge il prodotto "Merce in Cessione Gratuita art 2" di tipo 'servizio' e tipo speciale 'cessione gratuita'. (vedi sale_data.xml per dettagli)
Sulla scheda di questo prodotto vanno configurati il 'conto di ricavo' e le 'imposte cliente'.
Sul conto di ricavo inserire il conto (ad es 411100) che verra riportato in fattura e su cui verra registrato l'imponibile della cessione gratuita.
Sulle imposte va inserita l'esente articolo 2 e altre imposte articolo 2 con percentuali non nulle (dovrebbe bastare solo una al 22%, vedi db_zero). Tra quelle inserite sul prodotto, in fattura viene riportata l'imposta allo 0% se sulla riga dell'ordine di vendita si seleziona 'con rivalsa IVA', altrimenti, selezionando 'senza rivalsa IVA', viene riportata l'imposta con aliquota pari all'aliquota presente sulla riga dell'ordine di vendita, in modo da annullare l'ammontare dell'IVA.

---------------------
Gestione Sconto Cassa
---------------------

Per la gestione dello Sconto Cassa il modulo, all'installazione, aggiunge il prodotto "Sconto Cassa" di tipo 'servizio', tipo speciale 'sconto cassa' e con metodo di fatturazione 'quantita ordinate'. (vedi sale_data.xml per dettagli)
Sulla scheda di questo prodotto va configurato il 'conto di ricavo' desiderato, su cui andra a registrarsi lo sconto (ad es 411100). Le tasse sulle righe vengono aggiunte dinamicamente.

----------------------------------------------------
Gestione Filtri su Indirizzi Spedizione/Fatturazione
----------------------------------------------------

Aggiunta possibilita di scegliere come filtrare i campi *Indirizzo di Spedizione* ed *Indirizzo di Consegna* sull'ordine di vendita. In *Vendite > Configurazioe > Filtri su Indirizzi* scegliere una delle due modalita:

* Mostra tutti i partner con flag cliente: possibilita di fatturare/consegnare anche a clienti che non siano legati gerarchicamente al Cliente dell'ordine
* Mostra solo i partner con flag cliente e figli del Cliente (default): possibilita di fatturare/consegnare solo a clienti che siano legati gerarchicamente al Cliente dell'ordine

-------------------------
Gestione Saldo Imponibile
-------------------------

Aggiunta possibilita di mostrare la colonna Saldo Imponibile nella vista lista degli Ordini Vendita, dall'area Vendite > Configurazione:

* Non mostrare il saldo imponibile nella vista lista degli ordini vendita
* Mostrare il saldo imponibile nella vista lista degli ordini vendita

Vengono considerate solo fatture validate: i casi il fatturato sia maggiore del venduto, il saldo viene azzerato.
