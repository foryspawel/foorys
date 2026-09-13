# E2-Foorys

Wersja 0.4.1 pluginu dla Enigma2 do zarządzania listami kanałów,
pakietami pluginów, piconami oraz plikiem `oscam.dvbapi`.

## Co działa w wersji 0.4.1

- pobieranie katalogu z manifestu JSON przez HTTP(S),
- lista dostępnych list kanałów i instalacja archiwum `.tar.*` lub `.zip`,
- zapis wyłącznie rozpoznanych plików Enigma2 (`lamedb`, `bouquets.*`,
  `userbouquet.*`, `satellites.xml` itd.),
- automatyczna kopia zapasowa przed podmianą,
- pobieranie i instalacja pakietów `.ipk`/`.deb` przez `opkg`,
- aktualizacja `oscam.dvbapi` przez zapis atomowy,
- akcja pełnej instalacji E2iPlayer dla Python 3 z OE-Mirrors,
- osobna akcja patcha E2iPlayer `hosttorrentyts`,
- akcja instalacji `enigma2-plugin-softcams-oscam-stable` z feedu OEA,
- logo Foorys używane jako ikona w menu Enigma2 i znak nagłówka panelu,
- weryfikacja SHA-256 każdego pobieranego pliku,
- walidacja ścieżek w archiwach, aby uniknąć zapisu poza katalogiem staging.
- główny ekran E2-Foorys w formie siatki kafelków oraz osobne ekrany czynności:
  listy kanałów, aktualizacje, IPTV, Softcam/OSCam, pluginy, kopie, system i diagnostyka,
- domyślne połączenie z `foryspawel/foorys` przez `manifest.json` na GitHubie,
- aktualizacja samego E2-Foorys przez pobranie pakietu IPK z GitHuba,
- odczyt CPU, RAM, flasha, magazynu, temperatury, uptime i zainstalowanych
  pakietów bez zmiany systemu,
- przycisk aktualnego `oscam.dvbapi`, zapisujący wyłącznie `P:1884`, `P:0B01`
  i `P:1861`.
- osobna zakładka **EPG / Picony** z centralnymi mirrorami Chocholousek dla
  13.0E i 19.2E,
- aktualizacja piconów tylko przez kopiowanie nowych plików PNG — stare,
  nieobjęte paczką picony nie są kasowane,
- konsola instalacji z postępem pobierania, wynikiem SHA-256 i wyraźnym
  komunikatem **POWODZENIE** albo **BŁĄD**,
- rzeczywiste chwilowe użycie CPU z `/proc/stat` zamiast błędnego przeliczania
  load average na procent CPU,
- pokazanie wolnego miejsca na **RootFS**; gdy `/media/hdd` nie jest
  zamontowany, cache i kopie przechodzą do `/etc/enigma2/e2foorys`.

Lista kanałów, pluginy i picony są dostarczane wyłącznie przez centralny
manifest właściciela repozytorium — użytkownik dekodera nie może dopisywać
własnych pozycji do katalogu. W instalacji produkcyjnej używaj HTTPS:
SHA-256 chroni pobrany plik przed przypadkowym uszkodzeniem, ale sam manifest
powinien być dostarczany z zaufanego źródła.

Układ pluginu jest przygotowany do dalszej rozbudowy: lekki entry point,
osobne moduły operacji i bezpieczeństwa oraz warstwa UI, a logo
znajduje się w paczce jako `foorys.png`.

## Budowanie IPK

W katalogu projektu:

```text
  python tools/build_ipk.py --version 0.4.1
```

Powstanie `dist/enigma2-plugin-extensions-e2foorys_0.4.1_all.ipk`. Pakiet
można skopiować na dekoder i zainstalować:

```text
scp dist/enigma2-plugin-extensions-e2foorys_0.4.1_all.ipk root@DEKODER:/tmp/
ssh root@DEKODER opkg install /tmp/enigma2-plugin-extensions-e2foorys_0.4.1_all.ipk
```

Po instalacji plugin znajduje się w menu wtyczek jako `E2-Foorys`.

## Manifest repozytorium

Przykładowy format znajduje się w [manifest.example.json](manifest.example.json).
Minimalny wpis listy kanałów wygląda tak:

```json
{
  "id": "foorys-standard",
  "name": "Foorys Standard",
  "version": "2026.09.13",
  "url": "channels/foorys-standard.tar.gz",
  "sha256": "64-znakowa-suma-sha256"
}
```

Manifest może używać URL-i względnych. Archiwum listy powinno zawierać pliki
bezpośrednio lub w podkatalogu; plugin znajdzie tylko dozwolone nazwy plików.
`oscam_dvbapi` i `plugin_update` są pojedynczymi obiektami w głównym JSON-ie,
a `plugins` jest tablicą pakietów instalowanych przez `opkg`. Tablica `picons`
opisuje archiwa 7z, które są rozpakowywane przez `7za`/`7z`/`7zz` i kopiowane
do katalogu ustawionego w `Katalog piconów`. Aktualizacja jest inkrementalna.
Pole `plugin_update` wskazuje pakiet IPK następnej wersji pluginu. W zakładce
`E2-Foorys / Aktualizacje` pojawi się przycisk tylko wtedy, gdy wersja z
GitHuba jest wyższa od aktualnie uruchomionej.

W dekoderze otwórz `E2-Foorys -> Ustawienia`. Domyślnie plugin łączy się z
`https://raw.githubusercontent.com/foryspawel/foorys/main/manifest.json`.
Własny URL manifestu jest opcjonalny. Domyślne
ścieżki można zmienić, ponieważ obrazy Enigma2 różnią się miejscem instalacji
Oscama:

- listy kanałów: `/etc/enigma2`,
- `oscam.dvbapi`: `/etc/tuxbox/config/oscam-emu/oscam.dvbapi`,
- dane i kopie: `/media/hdd/e2foorys` (jeżeli HDD/USB jest zamontowany),
- awaryjny cache i kopie: `/etc/enigma2/e2foorys`, gdy magazyn zewnętrzny nie
  jest zamontowany,
- picony: `/usr/share/enigma2/picon`.

Repozytorium zawiera pakiety XStreamity i Chocholousek Picons. Są to mirrory
publikowane z zachowaniem informacji o źródle w manifeście. Picony 13.0E i
19.2E są odświeżane centralnie przez `.github/workflows/update-picons.yml`
co tydzień albo ręcznie przez **Actions → Aktualizuj picony → Run workflow**.
Workflow pobiera archiwa ze strony [picon.cz](https://picon.cz/download-picons/picon-transparent-220x132/),
sprawdza format 7z, wylicza SHA-256 i aktualizuje manifest.

W **Opcjach/Ustawieniach pluginu** pozostaje także pole `Akcja instalacyjna` z
akcjami E2iPlayer i Oscam stable. Wymagają one dodatkowego potwierdzenia,
działają jako `root` i korzystają z zewnętrznych
instalatorów/feedów. Patch E2iPlayer wymaga wcześniejszej instalacji wersji
zgodnej z Pythonem 3. Przed użyciem sprawdź, czy obraz ma działające `wget`,
`/bin/sh`, `bash`, `opkg` i dostęp do internetu.

## Testy lokalne

```text
python -m unittest discover -s tests -v
```

Testy obejmują walidację manifestu, SHA-256, wykrywanie plików kanałów i
ochronę przed traversal w archiwum.

Baza jest przygotowana dla współczesnych obrazów Enigma2 z Pythonem 3. Dla
starszych dekoderów z Pythonem 2 trzeba będzie przygotować osobny wariant.

## Następne kroki

Najważniejsze dane do dopasowania wersji produkcyjnej to model dekodera,
obraz Enigma2 (np. OpenATV/OpenPLi), wersja Python/opkg oraz dokładny format
publikowanych list. Na tej bazie można dodać panel WWW do wysyłania plików na
dekoder, logowanie repozytorium, rollback kopii, harmonogram aktualizacji i
automatyczne przeładowanie usług.
