# Foorys E2i Helper

Rozszerzenie Chrome/Edge dla **E2iPlayera**. Nie rozwiązuje CAPTCHA i nie omija Cloudflare. Po ręcznym ukończeniu weryfikacji przekazuje wyłącznie cookie `cf_clearance` oraz identyfikator przeglądarki do aktywnej sesji E2iPlayera na prywatnym adresie dekodera albo do jednorazowej sesji Foorys Relay.

## Instalacja

1. Otwórz `chrome://extensions` albo `edge://extensions`.
2. Włącz **Tryb programisty**.
3. Wybierz **Załaduj rozpakowane**.
4. Wskaż ten katalog `foorys-e2i-helper`.
5. Zostaw domyślny adres dekodera `192.168.18.177:9001` lub zmień go w oknie rozszerzenia.

## Użycie

1. W E2iPlayerze otwórz host wymagający weryfikacji.
2. Otwórz adres pokazany w kodzie QR w Chrome/Edge.
3. Przejdź weryfikację ręcznie.
4. Po zakończeniu Cloudflare rozszerzenie przekazuje sesję do dekodera; E2iPlayer sam kontynuuje operację.

## Przechwycenie przez Foorys Relay

1. Zaloguj się do panelu Relay i przy właściwym dekoderze kliknij **CAPTCHA E2iPlayer**.
2. Skopiuj wyświetlony 6-cyfrowy kod do pola **Kod przechwycenia CAPTCHA** w rozszerzeniu i kliknij **Aktywuj przechwycenie przez Relay**.
3. Otwórz adres z QR E2iPlayera, przejdź weryfikację ręcznie i poczekaj na komunikat powodzenia.
4. Kod jest jednorazowy i wygasa po 10 minutach. Po pomyślnym wysłaniu rozszerzenie usuwa go automatycznie.

Rozszerzenie odmawia przekazania cookie do adresów publicznych — akceptuje wyłącznie `localhost` oraz prywatne zakresy IPv4 (`10.x`, `172.16-31.x`, `192.168.x`).
