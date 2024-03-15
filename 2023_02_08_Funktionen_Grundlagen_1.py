# Schreibe eine Funktion namens funktion1, die einen einzigen Parameter namens parameter1 besitzt.
def funktion1(parameter1):
    pass

# Schreibe eine Funktion namens begrüßung, die einen einzigen Parameter namens grußformel besitzt.
def begrüßung(grußformel):
    pass

# Schreibe eine Funktion namens produkt_vorbereitung, die zwei Parameter namens zahl1 und zahl2 besitzt.
def produkt_vorbereitung(zahl1, zahl2):
    pass

# Schreibe eine Funktion namens hallo, die keinen Parameter besitzt und "Hallo" ausgibt.
def hallo():
    print("Hallo")

# Schreibe eine Funktion namens doppeltes, die einen einzigen Parameter namens zahl besitzt und das Doppelte von zahl ausgibt.
def doppeltes(zahl):
    print(zahl * 2)

# Schreibe eine Funktion namens summe, die zwei Parameter namens zahl1 und zahl2 besitzt und die Summe dieser Zahlen ausgibt.
def summe(zahl1, zahl2):
    print(zahl1 + zahl2)

# Schreibe eine Funktion namens differenz, die zwei Parameter namens zahl1 und zahl2 besitzt und die Differenz dieser Zahlen ausgibt.
def differenz(zahl1, zahl2):
    print(zahl1 - zahl2)

# Schreibe eine Funktion namens produkt, die zwei Parameter namens zahl1 und zahl2 besitzt und das Produkt dieser Zahlen ausgibt.
def produkt(zahl1, zahl2):
    print(zahl1 * zahl2)

# Schreibe eine Funktion namens positiv, die einen einzigen Parameter namens zahl besitzt und "Positiv" ausgibt, falls zahl größer 0 ist, ansonsten "Nicht positiv".
def positiv(zahl):
    if zahl > 0:
        print("Positiv")
    else:
        print("Nicht positiv")

# Schreibe eine Funktion namens größer, die zwei Parameter namens zahl1 und zahl2 besitzt und 1 ausgibt, falls zahl1 größer ist als zahl2, ansonsten 2.
def größer(zahl1, zahl2):
    if zahl1 > zahl2:
        print(1)
    else:
        print(2)

# Schreibe eine Funktion namens größere, die zwei Parameter namens zahl1 und zahl2 besitzt und den maximalen Wert der beiden Zahlen ausgibt.
def größre(zahl1, zahl2):
    if zahl1 > zahl2:
        print(zahl1)
    else:
        print(zahl2)

# Schreibe eine Funktion namens größte, die drei Parameter namens zahl1, zahl2 und zahl3 besitzt und den maximalen Wert der drei Zahlen ausgibt.
def größte(zahl1, zahl2, zahl3):
    if zahl1 > zahl2 and zahl1 > zahl3:
        print(zahl1)
    elif zahl2 > zahl1 and zahl2 > zahl3:
        print(zahl2)
    else:
        print(zahl3)

# Schreibe eine Funtion namens quadratOderMal10, die einen einzigen Parameter namens zahl besitzt und den maximalen Wert unter dessen Quadrat und dessen Zehnfachem ausgibt.
def quadratOderMal10(zahl):
    if zahl * zahl > zahl * 10:
        print(zahl * zahl)
    else:
        print(zahl * 10)

# Schreibe eine Funktion namens summe_oder_differenz, die zwei Parameter namens zahl1 und zahl2 besitzt und den maximalen Wert unter dessen Summe und dessen Differenz ausgibt.
def summe_oder_diferenz(zahl1, zahl2):
    if zahl1 + zahl2 > zahl1 - zahl2:
        print(zahl1 + zahl2)
    else:
        print(zahl1 - zahl2)