# Foorys Relay

Relay działa jako pośrednik dla sparowanych dekoderów. Dekoder inicjuje wyłącznie połączenia wychodzące; serwer nie łączy się bezpośrednio z siecią domową.

Panel administratora i dekodery używają osobnych tokenów. Relay nie przechowuje haseł root i udostępnia jedynie stałą listę bezpiecznych akcji: stan, diagnostyka, odświeżenie katalogu i aktualizacja E2-Foorys.

W produkcji usługa ma być dostępna wyłącznie przez Nginx TLS na porcie 9443. Token administratora należy utworzyć na serwerze i przechowywać w pliku `.env` z uprawnieniami `600`.
