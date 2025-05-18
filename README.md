# Műsorfigyelő Alkalmazás

Ez egy Flask alapú webalkalmazás, amely lehetővé teszi a felhasználók számára, hogy különböző eseményeket (színház, mozi, koncert stb.) keressenek, megtekintsenek és később akár személyes listákba rendezzenek. Az alkalmazás mostantól támogatja a felhasználói regisztrációt, bejelentkezést és az eseményadatok adatbázis-alapú kezelését. Az azonos című események csoportosítva jelennek meg, és a filmposzterek is láthatók. A felhasználók létrehozhatnak, kezelhetnek és exportálhatnak saját eseménylistákat.

## Jellemzők

* Események adatbázis-alapú listázása és keresése (cím alapján csoportosítva).
* Csoportosított eseményrészletező oldal, ami egy adott címhez tartozó összes helyszínt és időpontot listázza.
* Filmposzterek megjelenítése a kártyákon és a részletező oldalon.
* Felhasználói listák kezelése:
    * Listák létrehozása, megtekintése, törlése.
    * Filmek/előadások hozzáadása listákhoz és eltávolítása onnan.
    * Listák exportálása `.ics` (iCalendar) és `.pdf` formátumba.
* Felhasználói regisztráció és bejelentkezés.
* Védett "Irányítópult" oldal bejelentkezett felhasználóknak.
* Kijelentkezés funkció.
* Adminisztrátori funkció az események adatbázisának frissítésére (scraperek által).
* Külső linkek a jegyvásárlási oldalakra.

## Telepítés és Futtatás

### Előfeltételek

* Python 3.7+
* pip (Python package installer)
* (Opcionális, PDF-hez) Egy UTF-8 képes betűtípus, pl. DejaVuSansCondensed.ttf. Ha nincs a rendszeren, vagy az FPDF2 nem találja, az ékezetek hibásan jelenhetnek meg a PDF-ben. A kódban van egy próbálkozás a `static/fonts/` mappából betölteni.

### Telepítés

1.  Projekt Letöltése/Klónozása: Szerezd be a projekt fájljait.
2.  Virtuális Környezet (Ajánlott):
    ```bash
    python -m venv venv
    ```
    Aktiválás:
    * Windows: `venv\Scripts\activate`
    * macOS/Linux: `source venv/bin/activate`
3.  Függőségek Telepítése:
    ```bash
    pip install -r requirements.txt
    ```
    Ez telepíti az összes szükséges csomagot, beleértve a `pytest`-et is a teszteléshez.
4.  (Opcionális PDF-hez) Betűtípus: Hozz létre egy `musorfigyelo_app/static/fonts` mappát, és másold bele a `DejaVuSansCondensed.ttf` fájlt.

### Adatbázis Inicializálása
Az alkalmazás első futtatásakor (`python app.py`) automatikusan létrehozza a `musorfigyelo.db` SQLite adatbázisfájlt és a szükséges táblákat. Ha a séma változik (pl. új oszlopok), a `musorfigyelo.db` törlése és az alkalmazás újraindítása újragenerálja az adatbázist.

### Futtatás
```bash
python app.py
```
Ezután nyisd meg a böngésződben a `http://127.0.0.1:5000/` címet.

### Események Frissítése és Exportálás
1.  Regisztrálj egy felhasználót az `admin@example.com` email címmel.
2.  Jelentkezz be ezzel a felhasználóval.
3.  Az "Adatok Frissítése" gombbal töltsd fel az eseményeket.
4.  Adj hozzá eseményeket a listáidhoz a film/előadás részletező oldalán.
5.  A "Listáim" oldalon, egy konkrét lista megnyitása után találod az exportáló gombokat.

## Tesztelés

A projekt tartalmaz unit teszteket a `tests` mappában. A tesztek futtatásához a `pytest` könyvtárat használjuk.

1.  Győződj meg róla, hogy a `pytest` telepítve van (a `requirements.txt` tartalmazza).
2.  Futtatás a projekt gyökérmappájából:
    ```bash
    pytest
    ```
    Vagy egy konkrét tesztfájl futtatása:
    ```bash
    pytest tests/test_app.py
    ```
    A tesztek egy külön `test_musorfigyelo.db` adatbázist hoznak létre és törölnek a futás során.

## Csomagolás és Telepítés

A projekt csomagolható és telepíthető a `setup.py` fájl segítségével.

1.  **Csomag Építése (Wheel)**:
    A projekt gyökérmappájában (ahol a `setup.py` van) futtasd:
    ```bash
    python setup.py sdist bdist_wheel
    ```
    Ez létrehoz egy `dist` mappát, benne a telepíthető `.whl` fájllal (pl. `MusorfigyeloApp-0.1.0-py3-none-any.whl`).

2.  **Telepítés a Csomagból**:
    * Telepítés közvetlenül a projekt mappájából (fejlesztői mód, a változások azonnal látszanak):
        ```bash
        pip install -e .
        ```
    * Telepítés a generált wheel fájlból:
        ```bash
        pip install dist/MusorfigyeloApp-0.1.0-py3-none-any.whl 
        ```
        (Cseréld le a fájlnevet a ténylegesen generáltra.)

**Megjegyzés a csomagoláshoz**: A jelenlegi `setup.py` alapvető csomagolást tesz lehetővé. Egy komplexebb alkalmazásnál vagy PyPI-ra való feltöltésnél további konfigurációra (pl. `MANIFEST.in` a `templates` és `static` mappák pontosabb kezelésére) és lépésekre lehet szükség. A `find_packages()` helyett a `py_modules` használata is megfontolandó lehet, ha a projekt struktúrája egyszerűbb.

## Projekt Struktúra

```
musorfigyelo_app/            # Fő alkalmazás mappa (vagy a projekt gyökere, ha nem külön csomag)
├── app.py                     # Fő Flask alkalmazás, modellek, űrlapok, útvonalak
├── scrapers.py                # Web scraping függvények
├── templates/                 # HTML sablonok
│   ├── layout.html            
│   ├── index.html             
│   ├── search_results.html    
│   ├── event_detail_grouped.html  
│   ├── my_lists.html          
│   ├── list_detail.html       
│   ├── login.html             
│   ├── register.html          
│   └── dashboard.html         
├── static/                    # Statikus fájlok
│   ├── css/                   
│   │   └── style.css          
│   └── fonts/                 # Opcionális: .ttf fájlok PDF generáláshoz
│       └── DejaVuSansCondensed.ttf 
├── tests/                     # Tesztek mappája
│   └── test_app.py            # Unit tesztek
├── musorfigyelo.db            # SQLite adatbázis fájl (automatikusan generálódik)
├── requirements.txt           # Python függőségek listája
├── setup.py                   # Csomagoláshoz szükséges fájl
└── README.md                  # Ez a fájl
```
