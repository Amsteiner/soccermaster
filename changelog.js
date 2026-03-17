const CHANGELOG = [
  { v: '0.7.27', einträge: [
    'Dev-Admin-Erkennung läuft jetzt über die hinterlegte E-Mail-Adresse statt hardcoded Werten',
    'Reservierter Nickname löst Easter Egg aus – egal welcher Nickname reserviert ist',
  ]},
  { v: '0.7.26', einträge: [
    'Dev-Admin und reservierte Nicknames sind jetzt über die Konfiguration einstellbar statt hardcoded',
  ]},
  { v: '0.7.25', einträge: [
    'AFK-Modus: Inaktive Spieler werden in der Online-Liste mit gelbem Punkt und [AFK]-Status markiert',
    'AFK-Spieler werden beim Weiter-Button automatisch als bereit gezählt',
    'Inaktivitäts-Timeout für Admins konfigurierbar',
  ]},
  { v: '0.7.24', einträge: [
    'Saison-Abschluss: Gelistete Spieler werden vor der Insolvenzprüfung zwangsverkauft – Erlös zählt noch zur laufenden Saison',
    'In Woche 34 neu gelistete Spieler kehren bei Saisonende in den Kader zurück',
  ]},
  { v: '0.7.23', einträge: [
    'Pokal VORSPULEN: Nach Elfmeter-Ergebnis wurden parallele Spiele nicht mehr blockiert',
  ]},
  { v: '0.7.22', einträge: [
    'AFK-Erkennung: Nach 5 Min. Inaktivität werden Spieler in der Online-Liste als [AFK] mit gelbem Punkt markiert',
    'AFK-Spieler zählen automatisch als bereit und blockieren die Management-Phase nicht',
    'Inaktivitäts-Timeout für Admins konfigurierbar',
    'Relegationsspiel: Ohne Managerbeteiligung wird das Spiel instant im Hintergrund berechnet',
  ]},
  { v: '0.7.21', einträge: [
    'DFB-Pokal: Folgerunden werden jetzt korrekt als Einzelspiele (KO) ausgelost, nicht als Hin/Rückspiel',
  ]},
  { v: '0.7.20', einträge: [
    'Pokal-CPU-Runden (kein Manager beteiligt) laufen jetzt sofort statt in Echtzeit → kein 40s-Hänger nach Weiter',
    'VORSPULEN im Pokal funktioniert jetzt korrekt: alle parallelen CPU-Spiele skippen mit',
  ]},
  { v: '0.7.19', einträge: [
    'VORSPULEN-Button jetzt nur für Admins/Tester sichtbar (war versehentlich für alle sichtbar)',
    'Weiter-Timer bei Reconnect: zeigt korrekte Restzeit statt immer 60 Sekunden',
    'Spieler-Listing: mindestens 11 Spieler müssen im Kader bleiben',
  ]},
  { v: '0.7.18', einträge: [
    'Versionsnummer anklickbar: zeigt diesen Changelog',
    'Neue Retro-Themes: ZX Spectrum, CGA, Macintosh, Commodore PET, C64 BASIC',
    'Statusleiste überarbeitet: einheitlicheres Erscheinungsbild',
  ]},
  { v: '0.7.17', einträge: [
    'Spielsimulation: Weitere Balance-Parameter über das Admin-Panel einstellbar',
    'Malus für Rote Karten, Eigentor-Chance und weitere Faktoren anpassbar',
  ]},
  { v: '0.7.16', einträge: [
    'Vorspulen: Ereignisse (Tore, Karten, Verletzungen) werden nach dem Spiel im Ticker angezeigt',
    'Pokal-Vorspulen: Spielzusammenfassung inklusive Verlängerungsereignisse',
  ]},
  { v: '0.7.15', einträge: [
    'Internationale Vereinsspieler: Zufallsnamen bleiben länderspezifisch, auch wenn die Namensliste erschöpft ist',
  ]},
  { v: '0.7.14', einträge: [
    'Internationale Vereinsspieler erhalten länderspezifische Namen (18 Nationen, Ära 1983/84)',
  ]},
  { v: '0.7.13', einträge: [
    'Bereit-Status: Anzeige wer bereits bestätigt hat und auf wen noch gewartet wird',
  ]},
  { v: '0.7.12', einträge: [
    'Spieltag starten: Jeder Manager kann sich bereit melden – Spieltag beginnt, sobald alle bereit sind',
  ]},
  { v: '0.7.11', einträge: [
    'Tabellen 1. und 2. Bundesliga auf- und zuklappbar',
    'Ligen ohne eigenen Manager-Verein werden automatisch eingeklappt',
  ]},
  { v: '0.7.10', einträge: [
    'Pokal-Ansicht: Nur das eigene Spiel wird angezeigt, bei Rückspielen mit Hinspiel-Ergebnis',
  ]},
  { v: '0.7.9', einträge: [
    'Tabellen-Ansicht: Box „Nächste Spiele" zeigt alle Begegnungen des aktuellen Spieltags',
    'Pokal-Ansicht: Aktuelle Paarungen mit Hinspiel-Ergebnis bei Rückspielen',
  ]},
  { v: '0.7.8', einträge: [
    'Avatar-Upload: Bild kann vor dem Hochladen zugeschnitten, verschoben und gezoomt werden',
    'Avatar-Vorschau im Schnellprofil in voller Größe',
  ]},
  { v: '0.7.7', einträge: [
    'Radio: Pause/Weiter über Medientasten auch bei SID- und MOD-Formaten',
  ]},
  { v: '0.7.6', einträge: [
    'Relegations-Zuschauer: Managers ohne eigenes Relegationsspiel können das Spiel mitverfolgen',
  ]},
  { v: '0.7.5', einträge: [
    'Marktwert: wird wöchentlich neu berechnet und variiert leicht um den Spielerwert',
    'News-Ticker: Anzeigeposition bleibt beim Ausblenden erhalten',
  ]},
  { v: '0.7.4', einträge: [
    'Saison-Abschluss: Auf- und Absteiger werden im Tabellenabschluss farblich hervorgehoben',
    'Relegationsergebnis sichtbar im Saison-Abschluss',
  ]},
  { v: '0.7.3', einträge: [
    'Game-Over-Bildschirm: Karriere-Ende zeigt Abschlussübersicht und Vergleich mit anderen Managern',
    'Pokal-Zuschauer sehen das Spiel eines anderen Managers live mit',
  ]},
  { v: '0.7.2', einträge: [
    'Gelbe Karten: Anzeige als Gesamt (Zyklus) wenn Pokalkarten die Ligawertung aufblähen',
    'Auslandsmarkt: Mindeststärke auf Sehr stark / Weltklasse angehoben',
    'Spielabbruch: Wertung Liga 2:0, international 3:0 – nur wenn Ergebnis nicht bereits besser',
  ]},
  { v: '0.7.1', einträge: [
    'Europapokale: ECL, Pokalsieger-Cup und UEFA-Pokal vollständig spielbar',
    'DFB-Pokal: vollständiger Turniermodus mit Hin- und Rückspielen, Verlängerung, Elfmeterschießen',
    'Relegation: Auf-/Abstieg zwischen 1. und 2. Bundesliga',
  ]},
  { v: '0.7.0', einträge: [
    'Spieler-Entwicklung: Inländer verbessern/verschlechtern sich saisonal',
    'Mehrspielermodus: 2–4 Manager in einer Lobby',
  ]},
];
