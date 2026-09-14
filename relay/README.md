# Foorys Relay

Relay działa jako pośrednik dla sparowanych dekoderów. Dekoder inicjuje wyłącznie połączenia wychodzące; serwer nie łączy się bezpośrednio z siecią domową.

Panel administratora używa oddzielnego hasła, a dekodery osobnych tokenów. Relay nie przechowuje haseł root i udostępnia wyłącznie białą listę akcji: stan, diagnostyka sieci i prędkości, katalog, listy Foorys/Bzyk83, IPTV, picony, E2iPlayer, publiczne pakiety softcam, oscam.dvbapi, aktualizacja E2-Foorys oraz kontrolowany restart GUI. Nie ma zdalnego, dowolnego terminala root.

W panelu można usunąć dekoder wyłącznie wtedy, gdy ma status offline. Operacja usuwa również jego oczekujące zadania i sesje CAPTCHA; aktywny dekoder jest chroniony przez API.

W produkcji usługa ma być dostępna wyłącznie przez Nginx TLS na porcie 9443 pod domeną `raport.forys.pro`. Rekord DNS `raport.forys.pro` musi wskazywać na adres VPS `169.58.3.89`; nie zmieniaj przy tym rekordu używanego przez aplikację firmową. Certyfikat i klucz prywatny należy trzymać tylko na serwerze, a hasło administratora w pliku `.env` z uprawnieniami `600`.

Po sparowaniu wtyczka E2-Foorys pracuje w tle: wysyła heartbeat co minutę i pobiera zadania co 20 sekund. Nowy kod parowania ma 4 cyfry, jest jednorazowy i ważny 15 minut. Token urządzenia jest przechowywany tylko na dekoderze. Nazwę sparowanego dekodera można zmienić w panelu Relay; nazwa jest zapisywana w stanie serwera, a token nigdy nie jest wyświetlany w panelu.

Panel może również utworzyć jednorazową sesję „Otwórz CAPTCHA zdalnie” dla wybranego dekodera. Link otwarty w Chrome czeka na aktywną stronę MyE2i na porcie 9001 (agent sprawdza wyłącznie lokalne interfejsy dekodera), po czym otwiera właściwy serwis z jednorazowym tokenem sesji. Rozszerzenie Foorys E2i Helper po ręcznym przejściu weryfikacji Cloudflare przekazuje sesję do Relay, a agent dostarcza ją wyłącznie do lokalnego adresu callbacku E2iPlayera. Sesja wygasa po 10 minutach i jest usuwana po wykorzystaniu. Relay nie rozwiązuje CAPTCHA automatycznie.

Przepływ zdalny:

1. W panelu przy dekoderze kliknij **Otwórz CAPTCHA zdalnie**.
2. Otwórz skopiowany link w Chrome z zainstalowanym Foorys E2i Helper.
3. Uruchom w tym czasie żądanie CAPTCHA w E2iPlayerze na dekoderze; karta Relay poczeka i przekieruje do serwisu.
4. Potwierdź CAPTCHA ręcznie. Wynik trafia przez Relay do oczekującego E2iPlayera.

Adres 9001 nie jest wystawiany do Internetu, a kod awaryjny 6-cyfrowy pozostaje dla starszego trybu.
