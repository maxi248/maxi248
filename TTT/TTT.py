import arcade
import arcade.color


class TTT(arcade.Window):
    def __init__(self):
        super().__init__(600, 600, "Tik Tak Toe", )
        self.arena = {(0, 0): "", (1, 0): "", (2, 0): "", (0, 1): "", (1, 1): "", (2, 1): "", (0, 2): "", (1,  2): "", (2, 2): "" }
        arcade.set_background_color(arcade.color.BLACK)
        self.spieler = "X"
        self.reset()
        

    def reset(self):
        self.arena = {(0, 0): "", (1, 0): "", (2, 0): "", (0, 1): "", (1, 1): "", (2, 1): "", (0, 2): "", (1,  2): "", (2, 2): "" }
        self.spieler = "X"
        self.freie_felder = []

    def _gewinnprüfung(self):

        if self.arena[(0, 0)] == self.arena[(1, 0)] == self.arena[(2, 0)] != "":
            return True
        if self.arena[(0, 1)] == self.arena[(1, 1)] == self.arena[(2, 1)] != "":
            return True
        if self.arena[(0, 2)] == self.arena[(1, 2)] == self.arena[(2, 2)] != "":
            return True
        if self.arena[(0, 0)] == self.arena[(0, 1)] == self.arena[(0, 2)] != "":
            return True
        if self.arena[(1, 0)] == self.arena[(1, 1)] == self.arena[(1, 2)] != "":
            return True
        if self.arena[(2, 0)] == self.arena[(2, 1)] ==  self.arena[(2, 2)] != "":
            return True
        if self.arena[(0, 0)] == self.arena[(1, 1)] ==  self.arena[(2, 2)] != "":
            return True
        if self.arena[(0, 2)] == self.arena[(1, 1)] ==  self.arena[(2, 0)] != "":
            return True
        
        return False

    def on_mouse_press(self, x, y, button, modifiers):
        self.x_arena = x // 200
        self.y_arena = y // 200

        if self.arena[(self.x_arena, self.y_arena)] == "" and not self._gewinnprüfung():
            self.arena[(self.x_arena, self.y_arena)] = self.spieler
            self.spieler = "O" if self.spieler == "X" else "X"
       

    def freie_felder(self):
        freie_felder_liste = []
        for i in range(3):
            for j in range(3):
                if self.arena[(i, j)] == "":
                    freie_felder_liste.append((i, j))
        return freie_felder_liste
                    

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.R:
            self.reset() 
        if symbol == arcade.key.Q:
            arcade.exit()

    def on_update(self, delta_time):
        ...

    def on_draw(self):
        self.clear()
        arcade.draw_line(20, 200, 580, 200, arcade.color.GOLD, 12)
        arcade.draw_line(20, 400, 580, 400, arcade.color.GOLD, 12)
        arcade.draw_line(200, 20, 200, 580, arcade.color.GOLD, 12)
        arcade.draw_line(400, 20, 400, 580, arcade.color.GOLD, 12)

        for koordinaten in self.arena:
            x_arena = koordinaten[0]
            x_fenster = x_arena * 200 +100
            y_arena = koordinaten[1]
            y_fenster = y_arena * 200 +100 + 6
            feld_inhalt = self.arena[koordinaten]
            arcade.draw_text(feld_inhalt, x_fenster, y_fenster, font_size=120, font_name="Garamond", anchor_x="center", anchor_y="center", color = arcade.color.GOLD)
        if self._gewinnprüfung():
            if self.spieler == "O":
                arcade.draw_rectangle_filled(self.width / 2, self.height / 2, self.width, self.height, arcade.make_transparent_color(arcade.color.BLACK, 150))
                arcade.draw_text("Du hast Gewonnen, Spieler " + ("X" if self.spieler == "O" else "O"), self.width / 2, self.height /2 , color=arcade.color.WHITE , font_size= 90 , font_name="Garamond", width=self.width, align="center" , anchor_x ="center", anchor_y="center", multiline=True)
        elif self.freie_felder == []:
            arcade.draw_rectangle_filled(self.width / 2, self.height / 2, self.width, self.height, arcade.make_transparent_color(arcade.color.BLACK, 150))
            arcade.draw_text("Es Ist Unentschieden", self.width / 2, self.height /2 , color=arcade.color.WHITE , font_size= 60 , font_name="Garamond", width=self.width, align="center" , anchor_x ="center", anchor_y="center", multiline=True)
TTT()   
arcade.run()