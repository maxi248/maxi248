import arcade

class TTT(arcade.Window):
    def __init__(self):
        super().__init__(600, 600, "Tik Tak Toe", )
        self.arena = {(0, 0): "", (1, 0): "", (2, 0): "", (0, 1): "", (1, 1): "", (2, 1): "", (0, 2): "", (1,  2): "", (2, 2): "" }
        arcade.set_background_color(arcade.color.BLACK)
        self.spieler = "X"
    def on_mouse_press(self, x, y, button, modifiers):
        x_arena = x // 200
        y_arena = y // 200

        if self.arena[(x_arena,y_arena)] == "":
            self.arena[(x_arena,y_arena)] = self.spieler
        self.spieler = "O" if self.spieler == "X" else "X"




    
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
TTT()   
arcade.run()