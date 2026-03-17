#!/usr/bin/env python3
"""
Generiert eine erweiterte spieler.csv mit:
- Echten historischen Spielern 1975-1999
- Deutsche max "Sehr stark" (KEIN Weltklasse)
- Ausländer mindestens "Stark" (Weltklasse erlaubt)
- 1000+ Spieler realistische Verteilung
"""

import csv
import random

# Historische deutsche Top-Spieler und Legenden
DEUTSCHE_LEGENDEN = [
    # Bayern München Legenden
    ("Sepp Maier", "T", "Sehr stark"),
    ("Franz Beckenbauer", "A", "Sehr stark"),
    ("Gerd Müller", "S", "Sehr stark"),
    ("Karl-Heinz Rummenigge", "S", "Sehr stark"),
    ("Bernd Schuster", "M", "Sehr stark"),
    ("Paul Breitner", "M", "Sehr stark"),
    ("Stefan Effenberg", "M", "Sehr stark"),
    ("Oliver Kahn", "T", "Sehr stark"),
    ("Katja Raith", "T", "Stark"),

    # Fortuna Düsseldorf/HSV/andere
    ("Lothar Matthäus", "M", "Sehr stark"),
    ("Jürgen Klinsmann", "S", "Sehr stark"),
    ("Rudi Völler", "S", "Sehr stark"),
    ("Andreas Brehme", "A", "Sehr stark"),
    ("Thomas Häßler", "M", "Sehr stark"),
    ("Harald Schumacher", "T", "Sehr stark"),
    ("Hans-Peter Briegel", "A", "Sehr stark"),
    ("Manfred Kaltz", "A", "Sehr stark"),
    ("Karl-Heinz Förster", "A", "Sehr stark"),

    # Weitere Klassiker
    ("Toni Schumacher", "T", "Stark"),
    ("Guido Buchwald", "A", "Stark"),
    ("Jürgen Kohler", "A", "Stark"),
    ("Thomas Berthold", "A", "Stark"),
    ("Klaus Augenthaler", "A", "Stark"),
    ("Wolfgang Rolff", "A", "Stark"),
    ("Markus Babbel", "A", "Stark"),

    # Mittelfeld/Stürmer Deutsche Legenden
    ("Felix Magath", "M", "Stark"),
    ("Hansi Müller", "M", "Stark"),
    ("Uwe Bein", "M", "Stark"),
    ("Rainer Bonhof", "M", "Stark"),
    ("Heinz Flohe", "M", "Stark"),
    ("Michael Zorc", "M", "Stark"),
    ("Mario Basler", "M", "Stark"),
    ("Andreas Möller", "M", "Stark"),
    ("Mehmet Scholl", "M", "Stark"),
    ("Christian Ziege", "M", "Stark"),

    # Stürmer
    ("Klaus Fischer", "S", "Stark"),
    ("Horst Hrubesch", "S", "Stark"),
    ("Dieter Hoeneß", "S", "Stark"),
    ("Manfred Burgsmüller", "S", "Stark"),
    ("Stefan Kuntz", "S", "Stark"),
    ("Oliver Bierhoff", "S", "Stark"),
    ("Ulf Kirsten", "S", "Stark"),
    ("Roland Wohlfarth", "S", "Stark"),
    ("Heiko Herrlich", "S", "Stark"),
]

# Internationale Top-Spieler aus den Clubs in vereine.csv
AUSLAENDER_LEGENDEN = [
    # England - Liverpool, Man United, Arsenal, etc.
    ("Kenny Dalglish", "S", "Weltklasse"),
    ("John Aldridge", "S", "Sehr stark"),
    ("Ray Clemence", "T", "Weltklasse"),
    ("Alan Hansen", "A", "Weltklasse"),
    ("Graeme Souness", "M", "Weltklasse"),
    ("Bruce Grobbelaar", "T", "Sehr stark"),
    ("Ian Callaghan", "M", "Stark"),

    ("Alex Ferguson", "M", "Sehr stark"),  # Als Spieler früher
    ("Eric Cantona", "S", "Weltklasse"),
    ("Roy Keane", "M", "Weltklasse"),
    ("Peter Schmeichel", "T", "Weltklasse"),
    ("George Best", "S", "Weltklasse"),
    ("Bobby Charlton", "M", "Weltklasse"),
    ("Denis Law", "S", "Weltklasse"),

    ("Thierry Henry", "S", "Weltklasse"),
    ("Ian Wright", "S", "Sehr stark"),
    ("Patrick Vieira", "M", "Weltklasse"),

    ("Dwight Yorke", "S", "Sehr stark"),
    ("Marcus Stewart", "S", "Stark"),

    ("Alan Shearer", "S", "Weltklasse"),

    ("Didier Drogba", "S", "Weltklasse"),
    ("John Terry", "A", "Weltklasse"),
    ("Frank Lampard", "M", "Weltklasse"),
    ("Peter Cech", "T", "Weltklasse"),

    ("Gary Lineker", "S", "Sehr stark"),
    ("Paul Gascoigne", "M", "Sehr stark"),
    ("Stuart Pearce", "A", "Stark"),

    # Spanien - Real Madrid, Barcelona
    ("Alfredo Di Stéfano", "S", "Weltklasse"),
    ("Paco Gento", "S", "Weltklasse"),
    ("Carlos Santillana", "S", "Sehr stark"),
    ("Uli Stielike", "M", "Stark"),

    ("Luis Suárez", "M", "Weltklasse"),
    ("Samuel Eto'o", "S", "Weltklasse"),
    ("Ronaldinho", "M", "Weltklasse"),
    ("Xavi", "M", "Weltklasse"),
    ("Andrés Iniesta", "M", "Weltklasse"),
    ("Carles Puyol", "A", "Weltklasse"),

    ("Luis Aragonés", "M", "Stark"),
    ("Gento López", "S", "Stark"),

    # Italien - Juventus, AC Milan, Inter
    ("Giancarlo Antognoni", "M", "Weltklasse"),
    ("Roberto Platini", "M", "Weltklasse"),
    ("Marco Tardelli", "M", "Sehr stark"),

    ("Franco Baresi", "A", "Weltklasse"),
    ("Paolo Maldini", "A", "Weltklasse"),
    ("Marco van Basten", "S", "Weltklasse"),
    ("Ruud Gullit", "M", "Weltklasse"),
    ("Frank Rijkaard", "M", "Weltklasse"),
    ("Carlo Ancelotti", "M", "Sehr stark"),

    ("Giancarlo Marocchino", "A", "Stark"),
    ("Roberto Boninsegna", "S", "Sehr stark"),
    ("Sandro Mazzola", "M", "Weltklasse"),
    ("Javier Zanetti", "A", "Weltklasse"),

    ("Dino Zoff", "T", "Weltklasse"),
    ("Gianluigi Buffon", "T", "Weltklasse"),
    ("Francesco Totti", "M", "Weltklasse"),

    # Niederlande - Ajax, PSV
    ("Johan Cruyff", "S", "Weltklasse"),
    ("Marco van Basten", "S", "Weltklasse"),
    ("Dennis Bergkamp", "S", "Weltklasse"),
    ("Jan Molby", "M", "Sehr stark"),
    ("Ronald Koeman", "A", "Weltklasse"),
    ("Frank de Boer", "A", "Sehr stark"),
    ("Jaap Stam", "A", "Weltklasse"),
    ("Edwin van der Sar", "T", "Sehr stark"),

    ("Wim van Hanegem", "M", "Sehr stark"),
    ("Coen Dillen", "A", "Stark"),

    # Belgien
    ("Enzo Scifo", "M", "Sehr stark"),
    ("Jan Ceulemans", "S", "Sehr stark"),
    ("Wilfried Van Moer", "M", "Stark"),

    # Frankreich
    ("Michel Platini", "M", "Weltklasse"),
    ("Thierry Henry", "S", "Weltklasse"),
    ("Zinédine Zidane", "M", "Weltklasse"),
    ("Patrick Vieira", "M", "Weltklasse"),
    ("Fabrice Barthez", "T", "Sehr stark"),
    ("Lilian Thuram", "A", "Sehr stark"),
    ("Didier Drogba", "S", "Weltklasse"),

    # Portugal
    ("Eusébio da Silva Ferreira", "S", "Weltklasse"),
    ("Benfica", "A", "Stark"),
    ("Neno", "M", "Stark"),

    # Schottland
    ("Kenny Dalglish", "S", "Weltklasse"),
    ("Graeme Souness", "M", "Weltklasse"),
    ("Paul McStay", "M", "Sehr stark"),

    # Skandinavien
    ("Sören Lerby", "M", "Sehr stark"),
    ("Jan Mølby", "M", "Stark"),
    ("Preben Elkjær", "S", "Sehr stark"),

    # Schweiz
    ("Chapuisat", "S", "Sehr stark"),
    ("Stéphane Chapuisat", "S", "Stark"),

    # Österreich
    ("Toni Polster", "S", "Stark"),
    ("Hansi Krankl", "S", "Stark"),

    # Osteuropa
    ("Oleg Blokhin", "S", "Weltklasse"),
    ("Anatoli Davydenko", "M", "Sehr stark"),
    ("Igor Protasov", "S", "Stark"),

    # Balkan
    ("Dragan Dzajic", "S", "Weltklasse"),
    ("Goran Pandev", "S", "Sehr stark"),
    ("Savo Milosevic", "S", "Stark"),

    # Polen
    ("Zbigniew Boniek", "M", "Weltklasse"),
    ("Grzegorz Lato", "S", "Sehr stark"),

    # Südamerika
    ("Diego Maradona", "M", "Weltklasse"),
    ("Ronaldo Nazário", "S", "Weltklasse"),
    ("Pelé", "S", "Weltklasse"),
    ("Neymar", "S", "Weltklasse"),
    ("Ronaldinho", "M", "Weltklasse"),
    ("Carlos Valderrama", "M", "Sehr stark"),
    ("Ángel Labruna", "S", "Sehr stark"),
    ("Garrincha", "S", "Weltklasse"),
    ("Zé Maria", "S", "Stark"),
    ("Socrates", "M", "Weltklasse"),
]

def generate_random_deutsche(count=900):
    """Generiert fiktive deutsche Spieler"""
    first_names_d = [
        "Michael", "Andreas", "Peter", "Klaus", "Jürgen", "Thomas", "Markus",
        "Stefan", "Frank", "Hans", "Walter", "Dieter", "Werner", "Karl",
        "Hermann", "Otto", "Fritz", "Rolf", "Günter", "Helmut", "Bernd",
        "Hans-Peter", "Karl-Heinz", "Bert", "Rainer", "Heiner", "Udo", "Ingo",
        "Gerd", "Toni", "Helmuth", "Joseph", "Wilhelm", "Johann", "Ludwig",
        "Eduard", "Siegfried", "Egon", "Norbert", "Viktor", "Leopold", "Erwin",
    ]
    last_names_d = [
        "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
        "Becker", "Schulz", "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter",
        "Klein", "Neumann", "Krämer", "Krause", "Kaiser", "Kirsch", "Beck",
        "Lange", "Stark", "Bauer", "Gruber", "Krüger", "Braun", "Sauer",
        "Kaufmann", "Huber", "Hartmann", "Walter", "Förster", "Bergmann",
        "Schröder", "Kramer", "Koller", "Seiler", "Vogel", "Gross", "Klein",
    ]

    positions = ["T", "A", "M", "S"]
    strengths = ["Sehr stark", "Stark", "Durchschnitt", "Schwach", "Sehr schwach"]
    strength_weights = [5, 20, 40, 25, 10]  # Verteilung für Deutsche

    deutsche_spieler = []
    used_names = set()

    attempts = 0
    while len(deutsche_spieler) < count and attempts < count * 3:
        first = random.choice(first_names_d)
        last = random.choice(last_names_d)
        name = f"{first} {last}"
        attempts += 1

        if name not in used_names:
            used_names.add(name)
            pos = random.choice(positions)
            staerke = random.choices(strengths, weights=strength_weights)[0]
            deutsche_spieler.append((name, pos, staerke, "D"))

    return deutsche_spieler

def generate_random_auslaender(count=200):
    """Generiert fiktive ausländische Spieler"""
    first_names_intl = [
        "John", "Carlos", "Mauro", "José", "Luis", "Jean", "Marco", "Sergio",
        "Diego", "Pablo", "Roberto", "Antonio", "Alessandro", "Omar", "Karim",
        "Giovanni", "Francesc", "Pierre", "Henri", "André", "Michel", "Philippe",
        "João", "Manuel", "Ricardo", "Miguel", "Fernando", "Gustavo", "Raul",
        "Claudio", "Mauricio", "Daniel", "Jorge", "Francisco", "Victor", "Iván",
        "Andrés", "Cristian", "Alejandro", "Diego", "Mario", "Héctor",
    ]
    last_names_intl = [
        "Silva", "García", "González", "López", "Fernández", "Rossi", "Ferrari",
        "Devereaux", "Blanc", "Durand", "Moreau", "Bernard", "Laurent", "Martin",
        "Hassan", "Ahmed", "Costa", "Santos", "Oliveira", "Pereira", "Souza",
        "Gómez", "Rodríguez", "Martínez", "Jiménez", "Vázquez", "Mendes",
        "Couto", "Martins", "Alves", "Lopes", "Monteiro", "Vieira", "Teixeira",
        "Schulz", "Werner", "Schuster", "Hoffman", "Lehmann", "Wohlfahrt",
    ]

    positions = ["T", "A", "M", "S"]
    strengths = ["Weltklasse", "Sehr stark", "Stark"]
    strength_weights = [15, 35, 50]  # Ausländer müssen min "Stark" sein!

    auslaender_spieler = []
    used_names = set()

    attempts = 0
    while len(auslaender_spieler) < count and attempts < count * 3:
        first = random.choice(first_names_intl)
        last = random.choice(last_names_intl)
        name = f"{first} {last}"
        attempts += 1

        if name not in used_names:
            used_names.add(name)
            pos = random.choice(positions)
            staerke = random.choices(strengths, weights=strength_weights)[0]
            auslaender_spieler.append((name, pos, staerke, "A"))

    return auslaender_spieler

def main():
    """Hauptfunktion zum Generieren der spieler.csv"""

    all_players = []

    # Legenden hinzufügen
    for name, pos, staerke in DEUTSCHE_LEGENDEN:
        all_players.append((name, pos, staerke, "D"))

    for name, pos, staerke in AUSLAENDER_LEGENDEN:
        all_players.append((name, pos, staerke, "A"))

    # Zufällige Spieler generieren
    random_deutsche = generate_random_deutsche(920)  # Weniger, da wir Legenden haben
    random_auslaender = generate_random_auslaender(200)

    all_players.extend(random_deutsche)
    all_players.extend(random_auslaender)

    # Schreibe CSV
    csv_path = "data/spieler.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "position", "staerke", "nationalitaet"])
        for player in all_players:
            writer.writerow(player)

    # Validiere
    deutsch_count = 0
    ausland_count = 0
    staerken_deutsch = {}
    staerken_ausland = {}
    positions_count = {"T": 0, "A": 0, "M": 0, "S": 0}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['nationalitaet'] == 'D':
                deutsch_count += 1
            else:
                ausland_count += 1

            pos = row['position']
            positions_count[pos] = positions_count.get(pos, 0) + 1

            staerke = row['staerke']
            if row['nationalitaet'] == 'D':
                staerken_deutsch[staerke] = staerken_deutsch.get(staerke, 0) + 1
            else:
                staerken_ausland[staerke] = staerken_ausland.get(staerke, 0) + 1

    print(f"✓ Neue spieler.csv erstellt: {len(all_players)} Spieler")
    print(f"\n📊 SPIELER STATISTIK:")
    print(f"   Deutsche: {deutsch_count}")
    print(f"   Ausländer: {ausland_count}")
    print(f"   Gesamt: {deutsch_count + ausland_count}")

    print(f"\n📍 POSITIONEN:")
    for pos in ["T", "A", "M", "S"]:
        print(f"   {pos}: {positions_count[pos]}")

    print(f"\n⚡ DEUTSCHE SPIELER STÄRKEN:")
    strength_order = ["Weltklasse", "Sehr stark", "Stark", "Durchschnitt", "Schwach", "Sehr schwach"]
    for s in strength_order:
        if s in staerken_deutsch:
            print(f"   {s:15}: {staerken_deutsch[s]}")

    print(f"\n⚡ AUSLÄNDISCHE SPIELER STÄRKEN:")
    for s in strength_order:
        if s in staerken_ausland:
            print(f"   {s:15}: {staerken_ausland[s]}")

    print(f"\n✓ REGEL-CHECK:")
    if "Weltklasse" in staerken_deutsch:
        print(f"   ⚠ FEHLER: Deutsche haben Weltklasse! ({staerken_deutsch['Weltklasse']})")
    else:
        print(f"   ✓ Deutsche max 'Sehr stark' OK")

    if staerken_ausland.get("Schwach", 0) > 0 or staerken_ausland.get("Sehr schwach", 0) > 0:
        print(f"   ⚠ FEHLER: Ausländer unter 'Stark'!")
    else:
        print(f"   ✓ Ausländer min 'Stark' OK")

if __name__ == "__main__":
    main()
