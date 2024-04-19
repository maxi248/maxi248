import arcade

class TTT(arcade.Window):
    def __init__(self):
        super().__init__(300, 300, "Tik Tak Toe")

    def on_mouse_press(self, x, y, button, modifiers):
        ...
    
    def on_update(self, delta_time):
        ...

    def on_draw(self):
        ...
TTT()
arcade.run()