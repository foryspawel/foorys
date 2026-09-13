# Lokalny podgląd E2-Foorys

Podgląd działa bez Enigma2 i bez połączenia z dekoderem. Kliknięcia instalacji,
zmiany hasła oraz aktualizacji są symulowane w konsoli przeglądarki.

Uruchom z katalogu głównego repozytorium:

```powershell
node preview/server.js
```

Następnie otwórz:

```text
http://localhost:8765/preview/
```

Podgląd pobiera lokalny `manifest.json`, więc po zmianie katalogu można odświeżyć
stronę bez łączenia z dekoderem. Klawiatura: strzałki, Enter, G, B, M i Escape.
