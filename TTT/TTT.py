import arcade
import arcade.color
import random

class TTT(arcade.Window):
    def __init__(self):
        super().__init__(600, 600, "Tik Tak Toe")
        self.reset()
        arcade.set_background_color(arcade.color.BLACK)
        

    def reset(self):
        self.arena = {(0, 0): "", (1, 0): "", (2, 0): "", (0, 1): "", (1, 1): "", (2, 1): "", (0, 2): "", (1, 2): "", (2, 2): ""}
        self.spieler = "X"
        self.freie_felder = list(self.arena.keys())

    def _gewinnprüfung(self):
        # Horizontale Linien
        for i in range(3):
            if self.arena[(i, 0)] == self.arena[(i, 1)] == self.arena[(i, 2)] != "":
                return True
        # Vertikale Linien
        for i in range(3):
            if self.arena[(0, i)] == self.arena[(1, i)] == self.arena[(2, i)] != "":
                return True
        # Diagonalen
        if self.arena[(0, 0)] == self.arena[(1, 1)] == self.arena[(2, 2)] != "":
            return True
        if self.arena[(0, 2)] == self.arena[(1, 1)] == self.arena[(2, 0)] != "":
            return True
        return False
    
    def on_mouse_press(self, x, y, button, modifiers):
        x_arena = x // 200
        y_arena = y // 200

        if self.arena[(x_arena, y_arena)] == "" and not self._gewinnprüfung():
            self.arena[(x_arena, y_arena)] = self.spieler
            self.freie_felder.remove((x_arena, y_arena))
            if not self._gewinnprüfung():
                self.spieler = "O" if self.spieler == "X" else "X"
       
    def zufälliges_freies_feld(self):
        return random.choice(self.freie_felder)
        
    def _freie_felder(self):
        freie_felder_liste = [feld for feld, inhalt in self.arena.items() if inhalt == ""]
        return freie_felder_liste
                    
    def _gewinnendes_feld(self, symbol):
        for feld in self.freie_felder:
            self.arena[feld] = symbol
            if self._gewinnprüfung():
                self.arena[feld] = ""
                return feld
            self.arena[feld] = ""
        return None

    def _schlaues_feld(self):
        if (feld := self._gewinnendes_feld(self.spieler)) is not None:
            return feld    
        if (feld := self._gewinnendes_feld("X" if self.spieler == "O" else "O")) is not None:
            return feld   
        return self.zufälliges_freies_feld()

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.R:
            self.reset() 
        if symbol == arcade.key.Q:
            arcade.exit()

    def on_update(self, delta_time):
        if self.spieler == "O":
            if not self._gewinnprüfung() and len(self.freie_felder) > 0:
                feld = self._schlaues_feld()
                self.arena[feld] = self.spieler
                self.freie_felder.remove(feld)
                self.spieler = "X"

    def on_draw(self):
        self.clear()
        arcade.draw_line(20, 200, 580, 200, arcade.color.GOLD, 12)
        arcade.draw_line(20, 400, 580, 400, arcade.color.GOLD, 12)
        arcade.draw_line(200, 20, 200, 580, arcade.color.GOLD, 12)
        arcade.draw_line(400, 20, 400, 580, arcade.color.GOLD, 12)

        for koordinaten, feld_inhalt in self.arena.items():
            x_arena = koordinaten[0]
            x_fenster = x_arena * 200 + 100
            y_arena = koordinaten[1]
            y_fenster = y_arena * 200 + 100 + 6
            arcade.draw_text(feld_inhalt, x_fenster, y_fenster, font_size=120, font_name="Garamond", anchor_x="center", anchor_y="center", color=arcade.color.GOLD)

        if self._gewinnprüfung():
            arcade.draw_rectangle_filled(self.width / 2, self.height / 2, self.width, self.height, arcade.make_transparent_color(arcade.color.BLACK, 150))
            arcade.draw_text("Spieler " + ("X" if self.spieler == "O" else "O") + " hat gewonnen", self.width / 2, self.height / 2, color=arcade.color.WHITE, font_size=90, font_name="Garamond", width=self.width, align="center", anchor_x="center", anchor_y="center", multiline=True)
        elif len(self.freie_felder) == 0:
            arcade.draw_rectangle_filled(self.width / 2, self.height / 2, self.width, self.height, arcade.make_transparent_color(arcade.color.BLACK, 150))
            arcade.draw_text("Es Ist Unentschieden", self.width / 2, self.height / 2, color=arcade.color.WHITE, font_size=60, font_name="Garamond", width=self.width, align="center", anchor_x="center", anchor_y="center", multiline=True)

TTT()
arcade.run()
