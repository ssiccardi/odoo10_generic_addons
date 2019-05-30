=====================================
Sistemazioni Area Contabilità, rel.10
=====================================

----------------
Fatture Proforma
----------------

Potenziamento della configurazione "Proforma" già presente nel rel. Community:

* aggiunto campo Numero Proforma su fatture/note credito clienti, invisibile su fatture in bozza
* aggiunto sequenza PF per proforma indipendente da numerazione standard
* bottone assegnazione numero Proforma, visibile solo se fattura in bozza e senza numero proforma

**Configurazione**

* attivare "Consenti fatture proforma" su Configurazione/Contabilità
* tutti gli utenti vengono aggiunti in automatico al gruppo "Fatture Pro-forma"
* gli utenti che non appartengono al gruppo non vedono il bottone ed il numero Proforma

----------------------------------------------
Conto bancario default per ricezione pagamenti
----------------------------------------------

Portate funzionalita del modulo "customer_default_company_bank" (rel.8) per avere conto bancario default su cui ricevere pagamenti da clienti.

**Configurazione**

* creare le proprie banche in Vendite/Contatti/Conti Bancari/Banche
* creare i propri conti bancari dalla tabella Conti Bancari del partner legato all'azienda
* è possibile flaggare un conto bancario di default
* impostare il "Conto bancario per ricezione pagamenti" sulla scheda dei clienti
* alla creazione della fattura, quando si seleziona un cliente con conto impostato, questo viene riportato subito in fattura
* al momento della creazione fattira (SOLO IN CREAZIONE) quando si clicca Salva, se il conto è vuoto, viene riempito con il conto flaggato default (se presente)

------------------------------------------------
Creazione ex-novo Note Credito con menu apposito
------------------------------------------------

Creati due punti menu apposito per note di credito clienti e fornitori:

* modifica al filtro "Fatture": mostra tutte le fatture (indipendentemente dallo stato)
* nel menu Fatture Clienti/Fornitori viene aggiunto il filtro dinamico "Fatture" (togliendolo vengono mostrate anche le note credito)

-------------------------------------
Escludi da controllo su aliquota IVA
-------------------------------------

Aggiunto sul Sezionale l'opzione "No Tax Check" che esclude le righe della fattura, collegata a tale sezionale, dal controllo sull'aliquota IVA.

E' necessario per il corretto funzionamento dell'iter delle bolle doganali: in tale caso, infatti, la fattura fornitore non dve riportare aliquota.

