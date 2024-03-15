#schreibe eine funktion namens hallo die unendlich oft Hallo ausgibt
#verwende keine schleife
#def hallo():
 #   print("hallo")
 #   hallo()
# hallo()

#schreibe eine funktion namens Hallo_n, die eine Parameter n besitzt und n mal "Hallo" ausgibt
#def hallo_n(n):
   # if n <= 0:
   #     return
   # print("hallo")
   # hallo_n(n - 1)
#hallo_n(5)

#schreibe eine funktion namens n_bis_1_ausgabe, die einen Parameter n besitzt und alle Zahlen von n bis 1 ausgibt (von groß nach klein) 
#def n_bis_1_ausgabe(n):
#    if n <= 0:
#    return
 #   print(n)
  #  n_bis_1_ausgabe(n - 1)
#n_bis_1_ausgabe(5)

#schreibe eine fuktion namens eins_bis_n_ausgabe, die ein parameter n besitzt und alle Zahlen von 1 bis n ausgibt (von klein nach groß)
#def eins_bis_n_ausgabe(n):
   # if n <= 0:
    #    return
    #eins_bis_n_ausgabe(n - 1)
    #print(n)
#eins_bis_n_ausgabe(5)
#schreibe eine funktion namens n_bis_m_ausgabe, die zwei parameter m und n besitzt und alle zahlen von m bis n ausgibt(von groß nach klein)
#def n_bis_m_ausgabe(m, n):
#    if m >= n:
 #       return
  #  print(n)
   # n_bis_m_ausgabe(m, n - 1)
#n_bis_m_ausgabe(5, 10)



#schreibe eine funktion namens m_bis_n_ausgabe, die zwei parameter m und n besitzt und alle zahlen von m bis n ausgibt(von klein nach groß)
#def n_bis_m_ausgabe(m, n):
#    if m > n:
 #       return
  #  print(m)
   # n_bis_m_ausgabe(m + 1, n)
#n_bis_m_ausgabe(5, 10)

# schreibe eine Funktion namens n_zufallszahlen_ausgabe, die einen Parameter n besitzt und n Zufallszahlen zwischen 1 und 100 ausgibt 
#import random
#def n_zufallszahlen_ausgabe(n):
    #if n <= 0:
    #    return
    #zufallszahlen = random.randint(1, 100)
    #print(zufallszahlen)
    #n_zufallszahlen_ausgabe(n - 1)
#n_zufallszahlen_ausgabe(20)


# schreibe eine Funktion namens zwei_hoch, die einen Paramete n besitzt und die n´te potenz von 2 zurückgibt(ohne **)
#def zwei_hoch(n):
    #if  n == 0:
        #return 1
    #vorgängerergebnis = zwei_hoch(n - 1)
    #ergebnis = vorgängerergebnis * 2
    #return ergebnis
#print (zwei_hoch(5))

#schreibe eine Funktion namens m_mal_n, die zwei Parameter m und n besitzt und m mal n zurückgibt (ohne *)
#def m_mal_n(m, n):
 #   if n <= 0:
  #      return 0
   # vorgängerergebnis =m_mal_n()
    #return n_mal_m(m, n - 1)
#print(m_mal_b(3, 4))

#schreibe eine funktion namens fakultät, die einen prameter n besitzt und die Fakultät von n zurückgibt
#def fakultät(n):
#    if n == 0:
 #       return 1
  #  vorgängerergebnis = fakultät(n - 1)
   # ergebnis = vorgängerergebnis * n
    #return ergebnis 
#print(fakultät(5))
    

#schreibe eine Funktion namens m_hoch_n, die zwei parameter m und n besitzt und m hoch n zurückgibt(ohne **)
#def m_hoch_n(m, n):
#    if n <= 0:
 #       return 1
  #  vorgängerergebnis = m_hoch_n(m, n - 1)
   # ergebnis = vorgängerergebnis * m
    #return ergebnis



#schreibe eine funktion fibonacci, die einen parameter n besitzt und die n´te Fibonacci zurückgibt
#def fibonacci(n):
 #   if n <= 0:
  #      return 0
   # elif n == 1:
    #    return 1
    #fibonacci_n = fibonacci(n-1) + fibonacci(n-2)
    #return fibonacci_n
#print(fibonacci(39))



#schreibe eine funktion liste_n_1, die einen parameter n besitzt und eine liste mit n mal der Zahl 1 zurückgibt

#def liste_n_1(n):
#    if n == 0:
 #       return []
  #  vorgängerergebnis = liste_n_1(n - 1)
   # vorgängerergebnis.append(1)
    #return vorgängerergebnis
#print(liste_n_1(4))

      
#Schreibe eine Funktion liste_n_zufallszahlen, die ein parameter n besitzt und eine liste mit n Zufallszahlen zwischen 1 und 100 zurückgibt
#def liste_n_zufallszahlen(n):
#    if n == 0:
 #       return []
  #  vorgängerergebnis = liste_n_zufallszahlen(n - 1)
   # vorgängerergebnis.append(random.randint(1, 100))
    #return vorgängerergebnis
#print(liste_n_zufallszahlen(5))
    
    


#schreibe eine funktion liste_1_bis_n, die einen parameter n besitzt und eine liste aller Zahlen von 1 bis n zurückgibt
#def liste_1_bis_n(n):
#    if n == 0:
 #       return []
  #  vorgängerergebnis = liste_1_bis_n (n - 1)
   # vorgängerergebnis.append(n)
    #return vorgängerergebnis
#print(liste_1_bis_n(5))
