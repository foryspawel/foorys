# Feed opkg E2-Foorys

Konfiguracja feeda dla dekodera znajduje się w `foorys-feed.conf`.
Po skopiowaniu jej do `/etc/opkg/` można zainstalować plugin standardowym
mechanizmem `opkg`:

```sh
opkg update
opkg install enigma2-plugin-extensions-e2foorys
```

Feed jest publikowany z repozytorium GitHub pod adresem:

```text
https://raw.githubusercontent.com/foryspawel/foorys/main/feed
```

Indeks `Packages.gz` jest generowany skryptem `tools/build_opkg_feed.py`.
