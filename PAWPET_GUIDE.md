# PawPet - Kumpletong Gabay (folder, code, paliwanag, command)

## 1. Mapa ng mga folder

```
PawPet_Final
|-- README_START_HERE.txt      maikling steps
|-- PAWPET_GUIDE.md            ang gabay na ito
|
|-- LAPTOP2_Server             SERVER + DATABASE (Laptop 2)
|   |-- app.py                 ang Flask REST API (lahat ng endpoint)
|   |-- db.py                  koneksyon sa MySQL + definition ng mga table
|   |-- requirements.txt       Flask, PyMySQL
|   |-- database/schema.sql    SQL ng 10 tables (para sa phpMyAdmin)
|   |-- send_reminders.py      nagpapadala ng appointment reminders
|   |-- start_server.bat       double-click para i-run ang server
|   |-- send_reminders.bat     double-click para magpadala ng reminders
|   `-- install_scheduler.bat  gumagawa ng Task Scheduler tasks (Run as administrator)
|
|-- LAPTOP1_Desktop            DESKTOP APP (Laptop 1) - admin at staff
|   |-- admin.py               Flet app: login, menu, auto-refresh, dialogs
|   |-- pages.py               ang mga screen (Dashboard, Appointments, ...)
|   |-- ui.py                  mga reusable na bahagi (kulay, card, table, button)
|   |-- api_client.py          taga-tawag sa server (requests)
|   |-- admin_tkinter_old.py   lumang Tkinter na bersyon (backup lang)
|   |-- requirements.txt       flet==1.0.5 at requests
|   `-- start_admin.bat        double-click para i-run ang desktop app
|
|-- PHONE_Mobile               MOBILE APP (Ionic) - customer
|   |-- src/                   ang code ng app
|   |-- setup_mobile.bat       isang beses lang: gumagawa ng pawpet-app at kinokopya ang src
|   `-- start_mobile.bat       nagpapatakbo ng ionic serve
|
`-- DOCUMENTATION
    |-- PawPet_Documentation.pdf   ang PDF na isusubmit
    `-- tests/, test_api.py        mga test (para sa sanggunian)
```

## 2. Saan makikita ang code at bakit nandoon

### Server (LAPTOP2_Server) - ang nag-uugnay ng lahat
Ayon sa requirement, **ang desktop at mobile ay hindi direktang kumokonekta sa database. Dumadaan sila sa server.**

| File | Ano ang laman | Bakit nandito |
|---|---|---|
| `db.py` | MySQL connection, listahan ng 10 tables (`MYSQL_TABLES`) | Isang lugar lang ang database code |
| `app.py` | Login/register, tokens, products, batches, services, vets, appointments, sales, notifications, dashboard, reminders. 39 endpoints | Dito dumadaan ang lahat ng request ng desktop at mobile |
| `database/schema.sql` | `CREATE TABLE` ng lahat ng table | Para sa ERD/dictionary at para pwedeng i-import sa phpMyAdmin |
| `send_reminders.py` | Nagla-login bilang staff at tumatawag sa `/api/reminders/send` | Para tumakbo ang reminders sa Task Scheduler |

Mga bahagi ng `app.py` (hanapin gamit ang Ctrl+F):
- `migrate_batches`: nag-aayos ng lumang database para magkaroon ng batch.
- `deduct_stock`, `add_batch`: stock at batch na unang-mag-expire ang unang bawas (FEFO).
- `/api/login`, `/api/register`: pag-login ng customer at staff.
- `/api/products`, `/api/batches`: inventory at expiry.
- `/api/vets/.../availability`: mga bakanteng oras para sa booking, para walang double booking.
- `/api/appointments`: booking at pagbabago ng status.
- `/api/dashboard`: numbers para sa admin dashboard.
- `/api/reminders/send`: nagpapadala ng notifications.

### Desktop (LAPTOP1_Desktop)
Ang desktop app ay gawa sa **Flet** (modern UI, `pip install flet`). Ang `admin.py` ang login, menu at auto-refresh; ang `pages.py` ay may isang class bawat screen:

| Class | Screen |
|---|---|
| `Dashboard` | Dashboard: appointments ngayon, pending requests, expiry alerts |
| `Appointments` | Daily list, confirm, complete, no-show, cancel, follow-up |
| `Customers` | Mga customer |
| `Inventory` | Products, stock, **Receive new batch** |
| `Batches` | Batches at expiry, discard |
| `Vets` | Availability ng vet (araw at oras) |
| `Services` | Mga serbisyo |
| `Sales` | Benta |
| `App` (sa `admin.py`) | Login, menu, auto-refresh kada 8 segundo |

`api_client.py` ang tumatawag sa server (`get`, `post`, `put`, `delete`, `login`). Kaya ito lang ang may alam ng URL.

### Mobile (PHONE_Mobile\src)
| Path | Ano ang laman |
|---|---|
| `main.ts` | Simula ng app (kasama ang zone.js) |
| `app/config.ts` | **API_URL: dito mo ilalagay ang IP ng server** |
| `app/app.routes.ts` | Listahan ng mga page at ang login guard |
| `app/services/api.service.ts` | Lahat ng tawag sa server |
| `app/services/auth.interceptor.ts` | Nagdadagdag ng token sa bawat request |
| `app/guards/auth.guard.ts` | Hindi makakapasok kung hindi naka-login |
| `app/tabs/tabs.page.ts` | Ang tab bar sa ibaba |
| `app/pages/login` | Login at register |
| `app/pages/home` | Home: susunod na appointment, mga alaga |
| `app/pages/shop` | Products at services |
| `app/pages/book` | Booking: alaga, serbisyo, vet, petsa, oras |
| `app/pages/appointments` | Mga appointment ko, cancel |
| `app/pages/notifications` | Alerts |
| `app/pages/profile` | Profile at mga alaga |

### Paano buksan ang code
- Sa File Explorer, buksan ang folder at i-right-click ang file, tapos "Open with" Notepad o VS Code.
- Sa cmd, mula sa folder: `code .` (kung may VS Code) o `notepad app.py`.
- Para maghanap ng text sa lahat ng file: `findstr /s /i "batches" *.py` (sa server o desktop folder).

## 3. Lahat ng command

Buksan muna ang **MySQL sa XAMPP**.

### LAPTOP 2 (Server at MySQL)
```
cd PawPet_Final\LAPTOP2_Server
py -m pip install -r requirements.txt     (isang beses lang)
py setup_database.py                      (isang beses lang: database, tables, sample data)
py app.py                                  (iwan lang bukas)
ipconfig                                   (kunin ang IPv4 address)
py send_reminders.py                       (magpadala ng reminders ngayon; kailangan ng reminders_login.txt, tingnan sa baba)
```
Task Scheduler (Run as administrator, isang beses lang):
```
install_scheduler.bat
schtasks /Run /TN "PawPet Reminders"       (subukan ngayon)
schtasks /Query /TN "PawPet Reminders"     (tingnan)
schtasks /Delete /F /TN "PawPet Server"
schtasks /Delete /F /TN "PawPet Reminders"
```
Environment variables, kung may password ang MySQL (sa cmd bago ang `py app.py`):
```
set PAWPET_DB_PASSWORD=iyong_password
set PAWPET_DB_HOST=localhost
set PAWPET_DB_USER=root
set PAWPET_DB_NAME=pawpet
```

### LAPTOP 1 (Desktop app)
```
cd PawPet_Final\LAPTOP1_Desktop
py -m pip install -r requirements.txt     (isang beses lang - ini-install nito ang flet)
py admin.py
```
Kung ayaw ma-install ang `flet==1.0.5`, subukan `py -m pip install flet` (pinakabago). Server URL: `http://<IP NG LAPTOP 2>:5000` (`http://localhost:5000` kung iisang laptop). Login: `admin` o `staff` gamit ang password sa `FIRST_RUN_PASSWORDS.txt`.

### MOBILE APP
Una, i-edit ang `PHONE_Mobile\src\app\config.ts`:
```
export const API_URL = 'http://<IP NG LAPTOP 2>:5000/api';
```
Isang beses lang:
```
cd PawPet_Final\PHONE_Mobile
setup_mobile.bat
```
Pagpapatakbo:
```
cd PawPet_Final\PHONE_Mobile\pawpet-app
ionic serve --host=0.0.0.0
```
Kung binago mo ulit ang `config.ts` sa `PHONE_Mobile\src`, kopyahin sa `pawpet-app`:
```
xcopy /E /Y /I PawPet_Final\PHONE_Mobile\src PawPet_Final\PHONE_Mobile\pawpet-app\src
```
Gagana rin ito:
```
ionic cap run android                      (para sa Android phone na naka-USB, kailangan ng Android Studio)
```

### PHONE
```
http://<IP NG LAPTOP 2>:5000/api/health   (i-check muna ang server)
http://<IP NG LAPTOP NA NAGPAPATAKBO NG IONIC>:8100   (ang app)
```
Customer login: `megan` o `lester` gamit ang password sa `FIRST_RUN_PASSWORDS.txt`, o mag-register.

### Pang-check at pag-ayos
```
py --version                  (dapat Python 3)
node --version                (dapat may Node.js)
ionic --version
netstat -ano | findstr :5000  (tingnan kung tumatakbo ang server)
netstat -ano | findstr :8100  (tingnan kung tumatakbo ang ionic)
ipconfig                      (IP ng laptop)
```
Para i-reset ang database: buksan ang phpMyAdmin (`http://localhost/phpmyadmin`), i-drop ang `pawpet`, tapos i-run ulit ang `py app.py`. Bubuuin nito ang database at sample data na may batches.

## 4. Mga sample na account at password
Wala nang `admin123` / `staff123` / `pass123`. Sa **unang takbo ng server** gumagawa ito ng mga sample account (admin, staff, megan, lester) na may **random na password**. Makikita mo ito sa cmd window ng server at sa file na `LAPTOP2_Server\FIRST_RUN_PASSWORDS.txt`.

- **admin at staff** ay **kailangang magpalit** ng password pagka-login (lalabas ang "Choose a new password"). Hindi sila makakagamit ng iba pang feature hangga't hindi nagpapalit.
- Pagkatapos mong isulat ang mga password, **burahin ang `FIRST_RUN_PASSWORDS.txt`**.
- **Nakalimutan ng customer ang password?** Sa desktop app: Customers, piliin ang customer, **Reset password**. Bibigyan ka ng temporary password na ibibigay mo sa customer; kailangan niya itong palitan sa unang login.
- **Customer na ginawa ng staff** (Add customer): kapag blangko ang password, gagawa ng temporary password na ipapakita sa iyo.
- **Magpalit ng sariling password:** desktop, button na "Password" sa taas; mobile, Profile, "Change password".
- Rules ng password: 8 hanggang 128 characters, may letra at numero, hindi ang mismong username, hindi ang mga dating default.
- Lumang database na may `admin123` / `staff123` / `pass123`: hihingan ng bagong password sa susunod na login.
- Pitong maling login sa iisang username: hinaharang ng 10 minuto. Mag-expire ang session pagkatapos ng 30 araw.

## 5. Kapag may problema
| Problema | Gawin |
|---|---|
| `'py' is not recognized` | I-install ang Python at i-check ang "Add to PATH" |
| Cannot reach the server | Tingnan kung tumatakbo ang `py app.py`, at ang URL/IP. Pindutin ang Enter sa server cmd kung na-pause (QuickEdit) |
| Phone hindi mag-load | Iisang Wi-Fi, tamang IP, i-allow ang Python at Node.js sa Firewall |
| Walang laman ang Shop o Alerts | Hard refresh (Ctrl+Shift+R) pagkatapos kopyahin ang bagong `src`, at tingnan ang `config.ts` |
| Hindi lumalabas ang batch | I-restart ang server (`py app.py`). Kusang gagawin nito ang `batches` table |

## 6. Seguridad at pagiging maaasahan (bago mag-launch)
**Ayos na sa code:** walang double booking, walang oversell ng stock, validation ng lahat ng input (JSON error, hindi crash), salted PBKDF2 na password, lockout sa maling login, token na nag-e-expire, kailangang palitan ang default/temporary password, may timeout ang mobile at desktop, hindi na nagfi-freeze ang desktop kapag patay ang server, at hindi nakikita ng customer ang internal na stock.

**Para sa reminders sa Task Scheduler:** gumawa ng `LAPTOP2_Server\reminders_login.txt` na may dalawang linya (1: staff username, 2: password nito), o i-set ang `PAWPET_STAFF_USER` at `PAWPET_STAFF_PASS`. Pribado ang file na ito.

**Kailangan mong gawin bago ang totoong paggamit (hindi ko magagawa mula rito):**
1. **Password ng MySQL.** Ang XAMPP ay walang root password. Buksan ang `LAPTOP2_Server\database\secure_mysql.sql`, palitan ang mga password, patakbuhin, at i-set ang `PAWPET_DB_USER` at `PAWPET_DB_PASSWORD`. Ilagay din ang `bind-address=127.0.0.1` sa `my.ini` ng MySQL.
2. **HTTPS.** Plain HTTP ang gamit ng lahat (kita ng iba sa Wi-Fi ang password). Para sa school demo sa pribadong Wi-Fi, ok lang. Para sa totoong gamit, ilagay ang server sa likod ng HTTPS (halimbawa Caddy o nginx na may domain at certificate), o i-set ang `PAWPET_SSL_CERT` at `PAWPET_SSL_KEY` kung may certificate ka na. Palitan din ang `API_URL` sa `config.ts` ng `https://...`.
3. **Android APK (Capacitor).** Kung gagawa ka ng APK at HTTP ang server, i-set sa `capacitor.config.ts`: `server: { androidScheme: 'http', cleartext: true }` (para sa demo lang). Hindi ko ito nasubukan.
4. **Isang server process lang.** Ang lock laban sa double booking ay para sa iisang proseso. Huwag magpatakbo ng dalawang `py app.py` nang sabay.
5. **Mas matibay na server (opsyonal).** `py -m pip install waitress`, tapos `set PAWPET_WAITRESS=1` bago `py app.py`. Hindi ko pa ito nasubukan.
6. **Backup.** Gumawa ng regular na backup ng database (phpMyAdmin, Export).

## 7. Mga test
```
cd PawPet_Final\DOCUMENTATION
py audit_regression_test.py       (107 checks; gumagamit ng pansamantalang SQLite, hindi kailangan ng MySQL)
```
Ang `test_api.py` at `tests\admin_logic_test.py` ay para sa lumang fixed-password mode: patakbuhin ang server na may `set PAWPET_TEST_FIXED_PASSWORDS=1` at `set PAWPET_DB=sqlite` (para sa test lang, huwag gamitin sa totoong server).


## Hindi makakonekta? (Cannot reach the server / This site can't be reached)
1. Sa **LAPTOP 2**, tingnan ang banner ng server window - nandoon ang address na gagamitin ng ibang device.
2. Sa **LAPTOP 2**: right-click `LAPTOP2_Server\open_firewall.bat` -> **Run as administrator** (isang beses lang).
3. Sa **LAPTOP 1**: double-click `LAPTOP1_Desktop\check_connection.bat`, ilagay ang IP ng LAPTOP 2. Sasabihin nito kung tama, naka-block ng firewall, magkaibang network, o hindi tumatakbo ang server.
4. `localhost` = sariling computer lang. Sa ibang laptop o phone, IP ng LAPTOP 2 ang gamitin.
5. Dapat **parehong Wi-Fi** (parehong simula ang IP, halimbawa `192.168.100.`). Ang school/guest Wi-Fi ay madalas nagba-block ng device-to-device; gumamit ng phone hotspot.
6. Ang desktop app ay nagsa-save ng huling gumaganang server address (`server_address.txt`), kaya hindi mo na uulitin ang IP.


## Walang FIRST_RUN_PASSWORDS.txt / nakalimutan ang password
Ang file ay ginagawa lang kapag **bago pa ang database** (walang users). Kung may database ka na, hindi na ito gagawa ng bago.
Ayusin: sa LAPTOP 2 (naka-Start ang MySQL) i-double-click ang `LAPTOP2_Server\reset_password.bat`, ilagay ang username (`admin`), ang bagong username kung gusto mong palitan (halimbawa `admin_luie`), at ang bagong password (8+ karakter, letra AT numero). Hindi nito binubura ang data.


## Database: paano ito gumagana (para sa panelis)
- **`database/schema.sql`** ang nag-iisang source ng mga table (11 tables + indexes). Payak na `CREATE TABLE`, walang `IF NOT EXISTS`.
- **`setup_database.py`** (o `setup_database.bat`) ang gumagawa ng database **isang beses lang**:
  - walang laman na database -> gagawin ang lahat ng table, tapos sample data at first-run passwords;
  - database mula sa lumang PawPet -> idadagdag lang ang kulang, **walang binubura**;
  - kumpleto na -> sasabihin lang na "Nothing to do";
  - `py setup_database.py --reset` -> buburahin ang LAHAT at uulitin (magtatanong muna).
- **`app.py` (ang server) ay hindi gumagawa o nagbabago ng table.** Chine-check lang nito ang `schema_version`; kapag hindi pa na-setup, hihinto ito at sasabihin kung ano ang gagawin.
- Ang `schema_version` table ang nagsasabi kung anong bersyon ang database, para ligtas ang susunod na mga pagbabago (`UPGRADES` sa `db.py`).
- Hindi ko pa nasubukan ang setup sa totoong MySQL/XAMPP; sa SQLite ko lang nasubukan (14 tests sa `DOCUMENTATION/tests/database_setup_test.py`).

## Para sa mga page na blangko / kulay abo sa desktop (Flet)
Naayos na sa bagong bersyon: inalis ang mga "wrapping Row" na nagiging sanhi ng kulay abong kahon sa Flet, at ang mga table ay gumagamit na ng sarili nilang row/column na pumupuno sa buong lapad. Para sa bagong sample data na tugma sa petsa ngayon (mga appointment sa araw na may vet), patakbuhin ang `py setup_database.py --reset` (BUBURAHIN ang lahat ng data).
