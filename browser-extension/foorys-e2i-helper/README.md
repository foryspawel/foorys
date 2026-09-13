# Foorys E2i Helper

Rozszerzenie Chrome/Edge dla **E2iPlayera**. Nie rozwiązuje CAPTCHA i nie omija Cloudflare. Po ręcznym ukończeniu weryfikacji przekazuje wyłącznie cookie `cf_clearance` oraz identyfikator przeglądarki do aktywnej sesji E2iPlayera na prywatnym adresie dekodera albo do jednorazowej sesji Foorys Relay.

## Instalacja

1. Otwórz `chrome://extensions` albo `edge://extensions`.
2. Włącz **Tryb programisty**.
3. Wybierz **Załaduj rozpakowane**.
4. Wskaż ten katalog `foorys-e2i-helper`.
5. Adres dekodera jest potrzebny tylko w starszym, lokalnym trybie. Przy pracy przez Relay nie trzeba go wpisywać.

## Użycie

1. W E2iPlayerze otwórz host wymagający weryfikacji.
2. Otwórz adres pokazany w kodzie QR w Chrome/Edge.
3. Przejdź weryfikację ręcznie.
4. Po zakończeniu Cloudflare rozszerzenie przekazuje sesję do dekodera; E2iPlayer sam kontynuuje operację.

## Przechwycenie przez Foorys Relay

1. Zaloguj się do panelu Relay i przy właściwym dekoderze kliknij **Otwórz CAPTCHA zdalnie**.
2. Otwórz skopiowany link Relay w Chrome. Karta może przez chwilę czekać — agent szuka aktywnej sesji MyE2iPlayera na dekoderze.
3. Gdy sesja będzie gotowa, Relay otworzy właściwy serwis i rozszerzenie rozpozna zadanie automatycznie.
4. Ręcznie potwierdź CAPTCHA. Rozszerzenie prześle wynik do Relay, a agent dostarczy go lokalnemu E2iPlayerowi.

Starszy tryb pozostaje dostępny: w panelu wygeneruj kod awaryjny, wpisz go w rozszerzeniu i otwórz stronę MyE2iPlayera z dekodera. W nowym trybie nie trzeba wpisywać adresu IP ani portu 9001.

Rozszerzenie odmawia przekazania cookie do adresów publicznych — akceptuje wyłącznie `localhost` oraz prywatne zakresy IPv4 (`10.x`, `172.16-31.x`, `192.168.x`).
