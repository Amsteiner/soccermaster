const CHANGELOG = [
  { v: '0.7.36', de: [
    'Persische Sprachunterstützung (فارسی) hinzugefügt',
    'Sprachauswahl im Profil-Dropdown erkennt automatisch alle verfügbaren Sprachdateien',
    'Flaggen-Buttons werden dynamisch aus i18n/-Ordner generiert',
    'Changelog und Hilfedateien jetzt als externe Dateien im i18n/-Ordner',
  ], en: [
    'Persian (فارسی) language support added',
    'Language selector in profile automatically detects all available language files',
    'Flag buttons are now generated dynamically from the i18n/ folder',
    'Changelog and help files now as external files in the i18n/ folder',
  ], fa: [
    'پشتیبانی از زبان فارسی (فارسی) اضافه شد',
    'انتخاب‌گر زبان در پروفایل به‌طور خودکار تمام فایل‌های زبان موجود را شناسایی می‌کند',
    'دکمه‌های پرچم اکنون به‌صورت پویا از پوشه i18n/ تولید می‌شوند',
    'Changelog و فایل‌های راهنما اکنون به‌صورت فایل‌های خارجی در پوشه i18n/ هستند',
  ]},
  { v: '0.7.35', de: [
    'Standardsprache in settings.cfg konfigurierbar (standard_sprache = de/en/...)',
    'Nach Sprachwechsel wird die WebSocket-Verbindung automatisch neu aufgebaut',
    'LIESMICH.txt (Deutsch) und README.md (Englisch) auf aktuellen Stand gebracht',
  ], en: [
    'Default language configurable in settings.cfg (standard_sprache = de/en/...)',
    'WebSocket connection automatically re-established after language switch',
    'LIESMICH.txt (German) and README.md (English) updated to current state',
  ], fa: [
    'زبان پیش‌فرض در settings.cfg قابل تنظیم است (standard_sprache = de/en/...)',
    'اتصال WebSocket پس از تغییر زبان به‌طور خودکار دوباره برقرار می‌شود',
    'LIESMICH.txt (آلمانی) و README.md (انگلیسی) به وضعیت فعلی به‌روز شدند',
  ]},
  { v: '0.7.34', de: [
    'Hilfe als externe Sprachdateien (i18n/help.de.html, i18n/help.en.html)',
    'Spracheinstellung wird im Profil gespeichert und nach Login wiederhergestellt',
  ], en: [
    'Help as external language files (i18n/help.de.html, i18n/help.en.html)',
    'Language preference saved in profile and restored after login',
  ], fa: [
    'راهنما به‌صورت فایل‌های زبانی خارجی (i18n/help.de.html, i18n/help.en.html)',
    'تنظیمات زبان در پروفایل ذخیره شده و پس از ورود بازیابی می‌شود',
  ]},
  { v: '0.7.33', de: [
    'News-Ticker: Strukturierte Ereignisse statt vorgebauter Strings – Texte werden sprachabhängig generiert',
    'Alle UI-Texte, Tabellenabkürzungen und Spielstärken vollständig übersetzt',
  ], en: [
    'News ticker: Structured events instead of pre-built strings – texts are generated language-dependently',
    'All UI texts, table abbreviations and player strengths fully translated',
  ], fa: [
    'تیکر اخبار: رویدادهای ساختاریافته به‌جای رشته‌های از پیش ساخته‌شده – متن‌ها به‌صورت وابسته به زبان تولید می‌شوند',
    'تمام متن‌های رابط کاربری، اختصارات جدول و سطح توانایی بازیکنان به‌طور کامل ترجمه شد',
  ]},
  { v: '0.7.32', de: [
    'Mehrsprachige Oberfläche: Deutsch und Englisch (externe JSON-Sprachdateien)',
    'Flaggen-Buttons (🇩🇪 🇬🇧) immer sichtbar am Rand des Bildschirms',
    'Bilingualer Changelog mit Einträgen auf Deutsch und Englisch',
  ], en: [
    'Multilingual interface: German and English (external JSON language files)',
    'Flag buttons (🇩🇪 🇬🇧) always visible at the screen edge',
    'Bilingual changelog with entries in German and English',
  ], fa: [
    'رابط کاربری چندزبانه: آلمانی و انگلیسی (فایل‌های JSON زبانی خارجی)',
    'دکمه‌های پرچم (🇩🇪 🇬🇧) همیشه در لبه صفحه نمایش قابل مشاهده هستند',
    'Changelog دوزبانه با ورودی‌ها به آلمانی و انگلیسی',
  ]},
  { v: '0.7.31', de: [
    'Multimedia-Tasten (Play/Pause/Weiter/Zurück) steuern das Radio wieder korrekt, nachdem man zu SoccerMaster zurückwechselt',
  ], en: [
    'Media keys (Play/Pause/Next/Previous) now correctly control the radio again after switching back to SoccerMaster',
  ], fa: [
    'کلیدهای رسانه (Play/Pause/Next/Previous) پس از بازگشت به SoccerMaster دوباره رادیو را به‌درستی کنترل می‌کنند',
  ]},
  { v: '0.7.30', de: [
    'Rote Karten im Pokal und Europapokalen führen nicht mehr zu einer Ligasperre',
    'Spieler mit Sonderzeichen im Namen konnten nicht verpflichtet werden – behoben',
    'Saisons im Minus wurde nach dem Laden eines Spielstands falsch angezeigt – behoben',
  ], en: [
    'Red cards in cup and European competitions no longer trigger a league suspension',
    'Players with special characters in their name could not be signed – fixed',
    'Seasons in deficit were displayed incorrectly after loading a save – fixed',
  ], fa: [
    'کارت‌های قرمز در جام و مسابقات اروپایی دیگر منجر به محرومیت در لیگ نمی‌شوند',
    'بازیکنانی که نام آن‌ها شامل کاراکترهای خاص بود قابل جذب نبودند – برطرف شد',
    'فصل‌هایی که در منفی بودند پس از بارگذاری ذخیره به‌اشتباه نمایش داده می‌شدند – برطرف شد',
  ]},
  { v: '0.7.29', de: [
    'Es wurden Änderungen an der Steuerung für das Radio vorgenommen',
  ], en: [
    'Changes were made to the radio controls',
  ], fa: [
    'تغییراتی در کنترل‌های رادیو اعمال شد',
  ]},
  { v: '0.7.28', de: [
    'Einstellungen (Theme, Radio) können jetzt auch während einer laufenden Partie geändert werden – eigenen Namen in der Online-Liste anklicken',
    'Spielstand-Anzeige zeigt jetzt Verein, Saison und Spieltag',
  ], en: [
    'Settings (theme, radio) can now be changed during an active game – click your name in the online list',
    'Save display now shows club, season and matchday',
  ], fa: [
    'تنظیمات (تم، رادیو) اکنون می‌توانند در حین بازی فعال هم تغییر کنند – روی نام خود در لیست آنلاین کلیک کنید',
    'نمایش ذخیره اکنون باشگاه، فصل و روز بازی را نشان می‌دهد',
  ]},
  { v: '0.7.27', de: [
    'Reservierter Nickname löst Easter Egg aus',
  ], en: [
    'Reserved nickname triggers an Easter egg',
  ], fa: [
    'نام‌مستعار رزروشده یک Easter egg را فعال می‌کند',
  ]},
  { v: '0.7.25', de: [
    'AFK-Modus: Inaktive Spieler werden in der Online-Liste mit gelbem Punkt und [AFK]-Status markiert',
    'AFK-Spieler werden beim Weiter-Button automatisch als bereit gezählt',
  ], en: [
    'AFK mode: Inactive players are marked with a yellow dot and [AFK] status in the online list',
    'AFK players are automatically counted as ready when the Next button is pressed',
  ], fa: [
    'حالت AFK: بازیکنان غیرفعال در لیست آنلاین با یک نقطه زرد و وضعیت [AFK] مشخص می‌شوند',
    'بازیکنان AFK هنگام فشردن دکمه ادامه به‌طور خودکار آماده محسوب می‌شوند',
  ]},
  { v: '0.7.24', de: [
    'Saison-Abschluss: Gelistete Spieler werden vor der Insolvenzprüfung zwangsverkauft – Erlös zählt noch zur laufenden Saison',
    'In Woche 34 neu gelistete Spieler kehren bei Saisonende in den Kader zurück',
  ], en: [
    'Season wrap-up: Listed players are force-sold before the insolvency check – proceeds count towards the current season',
    'Players newly listed in week 34 return to the squad at season end',
  ], fa: [
    'پایان فصل: بازیکنان لیست‌شده پیش از بررسی ورشکستگی به‌اجبار فروخته می‌شوند – درآمد حاصل به فصل جاری تعلق می‌گیرد',
    'بازیکنانی که در هفته ۳۴ تازه لیست شده‌اند در پایان فصل به ترکیب بازمی‌گردند',
  ]},
  { v: '0.7.22', de: [
    'Relegationsspiel: Ohne Managerbeteiligung wird das Spiel instant im Hintergrund berechnet',
  ], en: [
    'Relegation play-off: If no manager is involved, the match is calculated instantly in the background',
  ], fa: [
    'بازی پلی‌آف سقوط: اگر هیچ مدیری درگیر نباشد، بازی فوری در پس‌زمینه محاسبه می‌شود',
  ]},
  { v: '0.7.21', de: [
    'DFB-Pokal: Folgerunden werden jetzt korrekt als Einzelspiele (KO) ausgelost, nicht als Hin/Rückspiel',
  ], en: [
    'DFB-Pokal: Later rounds are now correctly drawn as single-leg knockout ties, not home-and-away',
  ], fa: [
    'DFB-Pokal: دورهای بعدی اکنون به‌درستی به‌صورت بازی‌های تک‌مرحله‌ای حذفی قرعه‌کشی می‌شوند، نه رفت و برگشت',
  ]},
  { v: '0.7.20', de: [
    'Pokal-CPU-Runden (kein Manager beteiligt) laufen jetzt sofort durch',
    'VORSPULEN im Pokal funktioniert jetzt korrekt: alle parallelen CPU-Spiele skippen mit',
  ], en: [
    'Cup CPU rounds (no manager involved) now run through instantly',
    'FAST FORWARD in cup mode now works correctly: all parallel CPU matches skip together',
  ], fa: [
    'دورهای CPU در جام (بدون مشارکت مدیر) اکنون فوری اجرا می‌شوند',
    'جلو بردن سریع در حالت جام اکنون به‌درستی کار می‌کند: تمام بازی‌های موازی CPU با هم جهش می‌کنند',
  ]},
  { v: '0.7.19', de: [
    'Spieler-Listing: mindestens 11 Spieler müssen im Kader bleiben',
  ], en: [
    'Player listing: at least 11 players must remain in the squad',
  ], fa: [
    'لیست بازیکنان: حداقل ۱۱ بازیکن باید در ترکیب باقی بمانند',
  ]},
  { v: '0.7.18', de: [
    'Versionsnummer anklickbar: zeigt diesen Changelog',
    'Neue Retro-Themes: ZX Spectrum, CGA, Macintosh, Commodore PET, C64 BASIC',
    'Statusleiste überarbeitet: einheitlicheres Erscheinungsbild',
  ], en: [
    'Version number is now clickable: shows this changelog',
    'New retro themes: ZX Spectrum, CGA, Macintosh, Commodore PET, C64 BASIC',
    'Status bar redesigned: more consistent appearance',
  ], fa: [
    'شماره نسخه اکنون قابل کلیک است: این Changelog را نمایش می‌دهد',
    'تم‌های رترو جدید: ZX Spectrum، CGA، Macintosh، Commodore PET، C64 BASIC',
    'نوار وضعیت بازطراحی شد: ظاهر یکنواخت‌تر',
  ]},
  { v: '0.7.16', de: [
    'Vorspulen: Ereignisse (Tore, Karten, Verletzungen) werden nach dem Spiel im Ticker angezeigt',
    'Pokal-Vorspulen: Spielzusammenfassung inklusive Verlängerungsereignisse',
  ], en: [
    'Fast forward: events (goals, cards, injuries) are shown in the ticker after the match',
    'Cup fast forward: match summary including extra time events',
  ], fa: [
    'جلو بردن سریع: رویدادها (گل‌ها، کارت‌ها، مصدومیت‌ها) پس از بازی در تیکر نمایش داده می‌شوند',
    'جلو بردن سریع جام: خلاصه بازی شامل رویدادهای وقت اضافه',
  ]},
  { v: '0.7.15', de: [
    'Internationale Vereinsspieler: Zufallsnamen bleiben länderspezifisch, auch wenn die Namensliste erschöpft ist',
  ], en: [
    'International club players: random names remain country-specific even when the name list is exhausted',
  ], fa: [
    'بازیکنان باشگاه‌های بین‌المللی: نام‌های تصادفی حتی پس از اتمام لیست نام‌ها، کشورمحور باقی می‌مانند',
  ]},
  { v: '0.7.14', de: [
    'Internationale Vereinsspieler erhalten länderspezifische Namen (18 Nationen, Ära 1983/84)',
  ], en: [
    'International club players now receive country-specific names (18 nations, 1983/84 era)',
  ], fa: [
    'بازیکنان باشگاه‌های بین‌المللی اکنون نام‌های کشورمحور دریافت می‌کنند (۱۸ کشور، دوره ۱۹۸۳/۸۴)',
  ]},
  { v: '0.7.13', de: [
    'Bereit-Status: Anzeige wer bereits bestätigt hat und auf wen noch gewartet wird',
  ], en: [
    'Ready status: display shows who has confirmed and who is still being waited for',
  ], fa: [
    'وضعیت آمادگی: نمایش اینکه چه کسی تأیید کرده و منتظر چه کسی هستیم',
  ]},
  { v: '0.7.12', de: [
    'Spieltag starten: Jeder Manager kann sich bereit melden – Spieltag beginnt, sobald alle bereit sind',
  ], en: [
    'Starting a matchday: each manager can mark themselves ready – matchday starts once everyone is ready',
  ], fa: [
    'شروع روز بازی: هر مدیری می‌تواند خود را آماده اعلام کند – روز بازی زمانی شروع می‌شود که همه آماده باشند',
  ]},
  { v: '0.7.11', de: [
    'Tabellen 1. und 2. Bundesliga auf- und zuklappbar',
    'Ligen ohne eigenen Manager-Verein werden automatisch eingeklappt',
  ], en: [
    'Bundesliga 1 and 2 tables are now collapsible',
    'Leagues without your own club are collapsed automatically',
  ], fa: [
    'جداول BL1 و BL2 اکنون قابل جمع‌وباز شدن هستند',
    'لیگ‌هایی که باشگاه خودتان در آن‌ها نیست به‌طور خودکار جمع می‌شوند',
  ]},
  { v: '0.7.10', de: [
    'Pokal-Ansicht: Nur das eigene Spiel wird angezeigt, bei Rückspielen mit Hinspiel-Ergebnis',
  ], en: [
    'Cup view: only your own match is shown, with first-leg result for return legs',
  ], fa: [
    'نمای جام: فقط بازی خودتان نمایش داده می‌شود، با نتیجه بازی رفت برای بازی‌های برگشت',
  ]},
  { v: '0.7.9', de: [
    'Tabellen-Ansicht: Box „Nächste Spiele" zeigt alle Begegnungen des aktuellen Spieltags',
    'Pokal-Ansicht: Aktuelle Paarungen mit Hinspiel-Ergebnis bei Rückspielen',
  ], en: [
    'Table view: "Next Matches" box shows all fixtures of the current matchday',
    'Cup view: current pairings with first-leg result for return legs',
  ], fa: [
    'نمای جدول: باکس «بازی‌های بعدی» تمام دیدارهای روز بازی جاری را نشان می‌دهد',
    'نمای جام: جفت‌بندی‌های جاری با نتیجه بازی رفت برای بازی‌های برگشت',
  ]},
  { v: '0.7.8', de: [
    'Avatar-Upload: Bild kann vor dem Hochladen zugeschnitten, verschoben und gezoomt werden',
    'Avatar-Vorschau im Schnellprofil in voller Größe',
  ], en: [
    'Avatar upload: image can be cropped, moved and zoomed before uploading',
    'Avatar preview in quick profile shown at full size',
  ], fa: [
    'آپلود آواتار: تصویر می‌تواند پیش از آپلود برش داده، جابجا و زوم شود',
    'پیش‌نمایش آواتار در پروفایل سریع در اندازه کامل نمایش داده می‌شود',
  ]},
  { v: '0.7.7', de: [
    'Radio: Pause/Weiter über Medientasten auch bei SID- und MOD-Formaten',
  ], en: [
    'Radio: pause/play via media keys now also works for SID and MOD formats',
  ], fa: [
    'رادیو: توقف/پخش از طریق کلیدهای رسانه اکنون برای فرمت‌های SID و MOD هم کار می‌کند',
  ]},
  { v: '0.7.6', de: [
    'Relegations-Zuschauer: Managers ohne eigenes Relegationsspiel können das Spiel mitverfolgen',
  ], en: [
    'Relegation spectators: managers without their own relegation match can watch another manager\'s game live',
  ], fa: [
    'تماشاگران پلی‌آف سقوط: مدیرانی که بازی پلی‌آف خودشان را ندارند می‌توانند بازی مدیر دیگری را زنده تماشا کنند',
  ]},
  { v: '0.7.5', de: [
    'Marktwert: wird wöchentlich neu berechnet und variiert leicht um den Spielerwert',
    'News-Ticker: Anzeigeposition bleibt beim Ausblenden erhalten',
  ], en: [
    'Market value: recalculated weekly and varies slightly around player value',
    'News ticker: display position is preserved when hidden',
  ], fa: [
    'ارزش بازار: هر هفته دوباره محاسبه می‌شود و اندکی حول ارزش بازیکن تغییر می‌کند',
    'تیکر اخبار: موقعیت نمایش هنگام پنهان شدن حفظ می‌شود',
  ]},
  { v: '0.7.4', de: [
    'Saison-Abschluss: Auf- und Absteiger werden im Tabellenabschluss farblich hervorgehoben',
    'Relegationsergebnis sichtbar im Saison-Abschluss',
  ], en: [
    'Season wrap-up: promoted and relegated teams are colour-highlighted in the final table',
    'Relegation result now visible in the season wrap-up',
  ], fa: [
    'پایان فصل: تیم‌های صعودکرده و سقوط‌کرده در جدول نهایی با رنگ مشخص می‌شوند',
    'نتیجه پلی‌آف سقوط اکنون در پایان فصل نمایش داده می‌شود',
  ]},
  { v: '0.7.3', de: [
    'Game-Over-Bildschirm: Karriere-Ende zeigt Abschlussübersicht und Vergleich mit anderen Managern',
    'Pokal-Zuschauer sehen das Spiel eines anderen Managers live mit',
  ], en: [
    'Game Over screen: career end shows final summary and comparison with other managers',
    'Cup spectators can watch another manager\'s match live',
  ], fa: [
    'صفحه Game Over: پایان کارنامه، خلاصه نهایی و مقایسه با سایر مدیران را نشان می‌دهد',
    'تماشاگران جام می‌توانند بازی مدیر دیگری را به‌صورت زنده تماشا کنند',
  ]},
  { v: '0.7.2', de: [
    'Gelbe Karten: Anzeige als Gesamt (Zyklus) wenn Pokalkarten die Ligawertung aufblähen',
    'Spielabbruch: Ergebnis wird zugunsten des nicht-schuldigen Teams gewertet',
  ], en: [
    'Yellow cards: shown as Total (Cycle) when cup cards inflate the league count',
    'Match abandonment: result awarded in favour of the non-offending team',
  ], fa: [
    'کارت‌های زرد: به‌صورت مجموع (چرخه) نمایش داده می‌شوند وقتی کارت‌های جام آمار لیگ را بالا می‌برند',
    'توقف بازی: نتیجه به نفع تیم بی‌گناه اعلام می‌شود',
  ]},
  { v: '0.7.1', de: [
    'Europapokale: ECL, Pokalsieger-Cup und UEFA-Pokal vollständig spielbar',
    'DFB-Pokal: vollständiger Turniermodus mit Hin- und Rückspielen, Verlängerung, Elfmeterschießen',
    'Relegation: Auf-/Abstieg zwischen 1. und 2. Bundesliga',
  ], en: [
    'European cups: ECL, Cup Winners\' Cup and UEFA Cup fully playable',
    'DFB-Pokal: full tournament mode with home and away legs, extra time, penalty shootouts',
    'Relegation: promotion/relegation between Bundesliga 1 and 2',
  ], fa: [
    'جام‌های اروپایی: ECL، جام برندگان جام و UEFA-Pokal به‌طور کامل قابل بازی هستند',
    'DFB-Pokal: حالت کامل تورنمنت با بازی‌های رفت و برگشت، وقت اضافه و ضربات پنالتی',
    'پلی‌آف سقوط: صعود/سقوط بین BL1 و BL2',
  ]},
  { v: '0.7.0', de: [
    'Spieler-Entwicklung: Inländer verbessern/verschlechtern sich saisonal',
    'Mehrspielermodus: 2–4 Manager in einer Lobby',
  ], en: [
    'Player development: domestic players improve or decline each season',
    'Multiplayer mode: 2–4 managers in one lobby',
  ], fa: [
    'توسعه بازیکنان: بازیکنان داخلی هر فصل پیشرفت یا افت می‌کنند',
    'حالت چندنفره: ۲ تا ۴ مدیر در یک لابی',
  ]},
];
