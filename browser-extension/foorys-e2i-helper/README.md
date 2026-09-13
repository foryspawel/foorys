# Foorys E2i Helper

Rozszerzenie Chrome/Edge dla **E2iPlayera**. Nie rozwiązuje CAPTCHA i nie omija Cloudflare. Po ręcznym ukończeniu weryfikacji przekazuje wyłącznie cookie `cf_clearance` oraz identyfikator przeglądarki do aktywnej sesji E2iPlayera na prywatnym adresie dekodera.

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

Rozszerzenie odmawia przekazania cookie do adresów publicznych — akceptuje wyłącznie `localhost` oraz prywatne zakresy IPv4 (`10.x`, `172.16-31.x`, `192.168.x`).
