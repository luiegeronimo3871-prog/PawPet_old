PAWPET - ANO ANG GAGAMITIN SA BAWAT DEVICE

LAPTOP 1  (Desktop app - Admin/Staff)   -> folder: LAPTOP1_Desktop
   cd LAPTOP1_Desktop
   py -m pip install -r requirements.txt
   py admin.py          (Flet - gumagamit ng 'pip install flet', kasama na sa requirements.txt)
   Server URL sa login: http://<IP NG LAPTOP 2>:5000     (admin/staff: password sa FIRST_RUN_PASSWORDS.txt, ipapapalit sa unang login)

LAPTOP 2  (Server + MySQL)              -> folder: LAPTOP2_Server
   1. Start MySQL sa XAMPP
   2. cd LAPTOP2_Server
      py -m pip install -r requirements.txt
      py setup_database.py      <- ISANG BESES LANG: gumagawa ng database, tables at sample data (setup_database.bat)
      py app.py                 <- ang server; hindi na ito gumagawa ng tables, chine-check lang
   3. ipconfig  -> kunin ang IPv4 Address (yan ang <IP NG LAPTOP 2>)
   4. Allow Python sa Windows Firewall (Private network)
   Test: http://<IP>:5000/api/health
   SA setup_database.py: may lalabas na RANDOM na password ng mga sample account sa cmd at sa LAPTOP2_Server\FIRST_RUN_PASSWORDS.txt

PHONE / EMULATOR (Ionic customer app)   -> folder: PHONE_Mobile
   npm install -g @ionic/cli
   ionic start pawpet-app blank --type=angular
   cd pawpet-app
   npm install zone.js
   Kopyahin ang LAHAT sa PHONE_Mobile\src papunta sa pawpet-app\src (replace)
   Edit src\app\config.ts ->  http://<IP NG LAPTOP 2>:5000/api
   ionic serve   (o: ionic cap run android)
   Customer login: megan / lester (password sa FIRST_RUN_PASSWORDS.txt) o Create account

Lahat ng device: SAME Wi-Fi. Huwag gamitin ang localhost sa ibang device.
DOCUMENTATION = PDF at tests.

CANNOT CONNECT? ("This site can't be reached" / "Cannot reach the server")
   1. LAPTOP 2: tingnan ang banner sa server window - nandoon ang tamang address (http://<IP>:5000)
   2. LAPTOP 2: right-click LAPTOP2_Server\open_firewall.bat -> Run as administrator (isang beses)
   3. LAPTOP 1: double-click LAPTOP1_Desktop\check_connection.bat, ilagay ang IP ng LAPTOP 2 - sasabihin nito kung bakit
   4. 'localhost' ay para sa SARILING computer lang. Sa ibang laptop/phone, gamitin ang IP ng LAPTOP 2.
   5. Dapat SAME Wi-Fi (192.168.100.x ang simula ng dalawa). Kung school/guest Wi-Fi, gumamit ng phone hotspot.

BATCH FILES (double-click)
   LAPTOP2_Server\setup_database.bat     - ONE-TIME: create the database, tables and sample data (safe to run again)
   LAPTOP2_Server\start_server.bat        - start server
   LAPTOP2_Server\reset_password.bat      - nakalimutan ang admin password? maglagay ng bago (hindi nabubura ang data)
   LAPTOP2_Server\open_firewall.bat       - RUN AS ADMINISTRATOR once: opens port 5000 in the firewall
   LAPTOP1_Desktop\check_connection.bat   - tells you why the desktop app cannot reach the server
   LAPTOP2_Server\send_reminders.bat      - send reminders now
   LAPTOP2_Server\install_scheduler.bat   - RUN AS ADMINISTRATOR once: Task Scheduler auto-starts the
                                              server at logon and sends reminders daily at 07:00
   LAPTOP1_Desktop\start_admin.bat        - start desktop app
   PHONE_Mobile\setup_mobile.bat          - ONE-TIME: creates pawpet-app, installs zone.js, copies src
   PHONE_Mobile\start_mobile.bat          - copy into pawpet-app folder, starts ionic serve

BASAHIN ANG PAWPET_GUIDE.md (seksyon 4 at 6) para sa password, MySQL password, HTTPS at iba pang kailangang gawin bago ang totoong paggamit.
