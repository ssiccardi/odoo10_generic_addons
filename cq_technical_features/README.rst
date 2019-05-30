========================================
Miglioramenti vari funzionalità tecniche
========================================

È presente il file it.po che contiene le traduzioni dei moduli standard di base


Accesso alle "Funzionalità tecniche" senza attivare la modalità sviluppatore
============================================================================

Il gruppo *Technical feature (w/o debug mode)* permette di accedere alle 
funzionalità tecniche senza attivare la modalità sviluppatore.


Gestione Crea e Modifica da pannello
====================================

All'installazione del modulo vengono nascosti tutto i crea e modifica dai campi di relazione.
Andare in Configurazione --> Struttura Database --> Campi e flaggare "Mostra crea e modifica" per i campi in cui si vuole mostrarlo.

È obbligatorio inserire il flag per i campi 'attribute_id' e 'value_ids' del modello 'product.attribute.line' per poter creare nuovi attributi dal template nella tabella delle varianti.

Può essere necessario dover aggiornare la pagina per visualizzare le modifiche.


Gruppo utenti Importazione files CSV
====================================

Il gruppo *Importazione files CSV* permette di rendere visibile il bottone 'Importa'
per l'importazione di files CSV/Excel a tutti gli utenti che appartengono al gruppo.

All'installazione del modulo, l'utente Admin viene aggiunto automaticamente al gruppo.

Gli utenti che non appartengono a questo gruppo:

* non vedono questo bottone
* hanno inibita la funzionalita' "Importa" anche nel codice Python (metodo ORM "load"), in modo da prevenire anche chiamate XML-RPC

Gruppo utenti Esportazione files CSV/Excel
==========================================

Il gruppo *Esportazione files CSV/Excel* permette di rendere visibile il bottone 'Esporta'
per l'esportazione di files CSV/Excel a tutti gli utenti che appartengono al gruppo.

All'installazione del modulo, l'utente Admin viene aggiunto automaticamente al gruppo.

Gli utenti che non appartengono a questo gruppo:

* non vedono questo bottone


Menu e classe apposita per raccogliere wizard di ricalcolo/sovrascrittura di campi
===================================================================================

Aggiunta la classe transient *cq.ricalcola.campi*, dentro la quale si potranno definire
ogni volta dei metodi specifici per poter sovrascrivere o forzare il ricalcolo di vari campi.
All'occorrenza si potrà ereditare questa classe nel modulo di lavoro e lì definire:

* il metodo (codice python)
* la vista popup con il bottone collegato al metodo, l'azione vista e il menu collegato all'azione (codice xml)
* nel modulo id lavoro sarà necesario aggiungere *cq_technical_features* tra le dipendenze

Aggiunto menu Configurazione/Funzioni Tecniche/Wizard Ricalcolo Campi in cui raccogliere i sottomenu
collegati ai vari metodi. L'obiettivo è quello di avere questi wizard raccolti in un unico punto.

Per avere un esempio di come fare vedere il modulo *cq_products_10/wizard/cq_ricalcola_campi (.py, .xml)*
