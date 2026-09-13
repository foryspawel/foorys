# Foorys Relay

Relay działa jako pośrednik dla sparowanych dekoderów. Dekoder inicjuje wyłącznie połączenia wychodzące; serwer nie łączy się bezpośrednio z siecią domową.

Panel administratora używa oddzielnego hasła, a dekodery osobnych tokenów. Relay nie przechowuje haseł root i udostępnia wyłącznie białą listę akcji: stan, diagnostyka sieci i prędkości, katalog, listy Foorys/Bzyk83, IPTV, picony, E2iPlayer, publiczne pakiety softcam, oscam.dvbapi, aktualizacja E2-Foorys oraz kontrolowany restart GUI. Nie ma zdalnego, dowolnego terminala root.

W produkcji usługa ma być dostępna wyłącznie przez Nginx TLS na porcie 9443 pod domeną `raport.forys.pro`. Rekord DNS `raport.forys.pro` musi wskazywać na adres VPS `169.58.3.89`; nie zmieniaj przy tym rekordu używanego przez aplikację firmową. Certyfikat i klucz prywatny należy trzymać tylko na serwerze, a hasło administratora w pliku `.env` z uprawnieniami `600`.

Po sparowaniu wtyczka E2-Foorys pracuje w tle: wysyła heartbeat co minutę i pobiera zadania co 20 sekund. Kod parowania jest jednorazowy i ważny 15 minut. Token urządzenia jest przechowywany tylko na dekoderze.
