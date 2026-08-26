# Thrustmaster → SimRail

Program pozwalający sterować pociągami w **SimRail – The Railway Simulator** za pomocą
przepustnicy **Thrustmaster TCA** (np. TCA Captain Pack X Airbus Edition — kwadrant
przepustnicy + sidestick).

SimRail nie obsługuje natywnie osi analogowych joysticków, więc program działa jako
„mostek": odczytuje położenie dźwigni i przycisków kontrolera i wysyła do gry
odpowiednie naciśnięcia klawiszy (przez `SendInput` ze scancode'ami sprzętowymi,
które gra widzi tak samo jak prawdziwą klawiaturę).

## Możliwości

- **Tryb `notched` (skokowy)** — oś podzielona na N pozycji, jak nastawnik jazdy
  EU07. Przesunięcie dźwigni o 3 pozycje = 3 naciśnięcia klawisza `Num +`.
  Histereza eliminuje „dzwonienie" na granicy pozycji.
- **Tryb `zones` (strefowy)** — dopóki dźwignia jest w danej strefie, trzymany jest
  wciśnięty klawisz (np. dźwignia do przodu = trzymaj `Num +`, do tyłu = `Num -`,
  środek = nic). Dobry do płynnych zadajników (EN76 Elf) i kranów hamulca.
- **Przyciski i przełączniki** — pojedyncze naciśnięcie (`tap`), przytrzymanie
  (`hold`, np. syrena), przełącznik dwustanowy (`switch`, np. pantograf: włącz →
  klawisz A, wyłącz → klawisz B) oraz `resync` (patrz niżej).
- **Kalibracja** — kreator zapisuje rzeczywisty zakres i kierunek każdej osi do
  profilu.
- **Profile** — osobne pliki JSON dla różnych lokomotyw (`config/eu07.json`,
  `config/en76.json`); łatwo dodać własne.
- **Tryb testowy** (`--dry-run`) — wypisuje zdarzenia klawiszy zamiast je wysyłać.

## Wymagania

- Windows 10/11 (wysyłanie klawiszy działa tylko na Windows; na innych systemach
  program działa w trybie `--dry-run`)
- Python 3.9 lub nowszy — <https://www.python.org/downloads/> (przy instalacji
  zaznacz „Add Python to PATH")
- Podłączona przepustnica Thrustmaster TCA

## Instalacja

```bat
git clone https://github.com/LukaszTM/Thrustmaster-train-control.git
cd Thrustmaster-train-control
pip install -r requirements.txt
```

## Pierwsze uruchomienie — krok po kroku

**1. Sprawdź, czy kontroler jest widoczny:**

```bat
python -m simrail_tca devices
```

Powinno pokazać coś w stylu `[0] TCA Q-Eng 1&2` / `TCA Quadrant Airbus Edition`.
Jeśli nazwa nie zawiera „TCA", wpisz jej fragment w polu `device.name_contains`
w pliku profilu.

**2. Zidentyfikuj numery osi i przycisków** (poruszaj dźwigniami, wciskaj przyciski):

```bat
python -m simrail_tca monitor --config config/eu07.json
```

Wpisz właściwe numery w polach `axis` / `button` profilu.

**3. Skalibruj osie:**

```bat
python -m simrail_tca calibrate --config config/eu07.json
```

Dla każdej osi: przesuń dźwignię w pełnym zakresie, zostaw ją w pozycji
minimalnej (jałowej) i naciśnij Enter. Wynik zapisuje się do pliku profilu.

**4. Przetestuj bez gry:**

```bat
python -m simrail_tca run --config config/eu07.json --dry-run -v
```

**5. Uruchom SimRail i mostek:**

```bat
python -m simrail_tca run --config config/eu07.json
```

albo po prostu `run.bat` (opcjonalnie `run.bat config\en76.json`).

> **Ważne:** w trybie `notched` program nie wie, gdzie faktycznie stoi nastawnik
> w grze — zaczyna od pozycji 0. Przed startem ustaw nastawnik w grze na 0
> (albo użyj przycisku z akcją `resync`, która zeruje licznik po tym, jak sam
> ustawisz nastawnik na 0 w grze).

## Konfiguracja profilu

Przykład (`config/eu07.json`):

```json
{
  "device": { "name_contains": "TCA" },
  "poll_hz": 60,
  "key_tap_ms": 40,
  "key_gap_ms": 60,
  "axes": [
    {
      "axis": 0,
      "name": "nastawnik",
      "mode": "notched",
      "positions": 44,
      "increase_key": "num_add",
      "decrease_key": "num_subtract",
      "hysteresis": 0.2,
      "calibration": { "min": -1.0, "max": 1.0, "invert": true }
    },
    {
      "axis": 1,
      "name": "hamulec_zespolony",
      "mode": "zones",
      "zones": [
        { "from": 0.0,  "to": 0.35, "key": "num9" },
        { "from": 0.35, "to": 0.65, "key": null },
        { "from": 0.65, "to": 1.0,  "key": "num3" }
      ]
    }
  ],
  "buttons": [
    { "button": 0, "name": "czuwak_shp", "action": "tap",  "key": "space" },
    { "button": 1, "name": "syrena",     "action": "hold", "key": "q" },
    { "button": 3, "name": "resync_nastawnika", "action": "resync",
      "resync_axis": "nastawnik", "resync_notch": 0 }
  ]
}
```

| Pole | Znaczenie |
|---|---|
| `poll_hz` | częstotliwość odczytu kontrolera |
| `key_tap_ms` / `key_gap_ms` | czas wciśnięcia klawisza i przerwa między kolejnymi naciśnięciami (zwiększ, jeśli gra „gubi" naciśnięcia) |
| `positions` | liczba pozycji nastawnika w trybie `notched` |
| `hysteresis` | część szerokości pozycji (0–0.4) tłumiąca drgania osi |
| `zones` | strefy 0.0–1.0 po kalibracji; `key: null` = strefa martwa |
| `calibration` | wypełnia kreator `calibrate`; `invert` odwraca kierunek osi |

### Nazwy klawiszy

`a`–`z`, `0`–`9`, `f1`–`f12`, `space`, `enter`, `tab`, `esc`, `lshift`, `lctrl`,
`lalt`, strzałki (`up`, `down`, `left`, `right`), `home`, `end`, `pageup`,
`pagedown`, `insert`, `delete` oraz klawiatura numeryczna: `num0`–`num9`,
`num_add`, `num_subtract`, `num_multiply`, `num_divide`, `num_decimal`,
`num_enter`. Pełna lista: `simrail_tca/keysender.py`.

### Dopasowanie do klawiszy w grze

Domyślne profile zakładają typowe bindy SimRail (nastawnik: `Num +` / `Num -`,
kran hamulca: `Num 3` / `Num 9`, czuwak/SHP: `Spacja`). **Sprawdź własne
ustawienia w grze** (Ustawienia → Sterowanie) i w razie różnic popraw nazwy
klawiszy w profilu — każdy klawisz jest w pełni konfigurowalny.

## Rozwiązywanie problemów

- **Gra nie reaguje na klawisze** — uruchom program *jako administrator*, jeśli
  SimRail działa z uprawnieniami administratora (Windows blokuje wysyłanie
  klawiszy do procesów o wyższych uprawnieniach). Upewnij się też, że okno gry
  jest aktywne.
- **Gra gubi część naciśnięć** przy szybkim ruchu dźwignią — zwiększ
  `key_tap_ms` i `key_gap_ms` (np. 60/80).
- **Nastawnik „rozjechał się" z grą** — ustaw nastawnik w grze na 0 i wciśnij
  przycisk z akcją `resync` (albo zrestartuj program).
- **Dźwignia działa odwrotnie** — zmień `calibration.invert` albo powtórz
  kalibrację.
- **Program nie widzi kontrolera** — sprawdź `python -m simrail_tca devices`;
  w Steam wyłącz Steam Input dla SimRail, żeby nie przechwytywał urządzenia.

## Testy

```bat
python -m unittest discover -s tests -v
```

## Jak to działa

```
TCA (pygame/SDL) → normalizacja osi (kalibracja) → mapowanie
  ├─ notched: śledzenie pozycji + kolejka pojedynczych naciśnięć
  ├─ zones:   trzymanie klawisza, dopóki dźwignia jest w strefie
  └─ przyciski: tap / hold / switch / resync
→ SendInput (scancode, jak fizyczna klawiatura) → SimRail
```
