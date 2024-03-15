import arcade
import random


class Spiel(arcade.Window):
    def __init__(self, breite, höhe, titel):
        super().__init__(breite, höhe, titel)
        
        arcade.set_background_color(arcade.color.AMAZON)

        self.spielstart()

    def spielstart(self):
        
        self.startscreen_liste = arcade.SpriteList()
        self.button_liste = arcade.SpriteList()
        self.gegenstand_liste = arcade.SpriteList()
        self.hide_liste = arcade.SpriteList()
        self.end_liste = arcade.SpriteList()
        self.rebutton_liste = arcade.SpriteList()
        self.total_time = 0
        self.counter_text = 0 
        self.timer_text_2 = arcade.Text(text= ("/6"), start_x = 714, start_y = 570, color= arcade.color.BLACK, font_size=20)      
        self.counter_text = arcade.Text(text = str(self.counter_text), start_x = 375, start_y = 490)
        self.timer_text = arcade.Text(text = str(self.total_time), start_x = 700, start_y = 540, color= arcade.color.BLACK, font_size= 20)
        self.counter = 0

        dot = arcade.Sprite("liste.png")
        dot.center_x = 0
        dot.center_y = 0
        self.gegenstand_liste.append(dot)
        
        start = arcade.Sprite("start.png")
        start.center_x = 400
        start.center_y = 300
        self.startscreen_liste.append(start)

        startbutton = arcade.Sprite("startbutton.png")
        startbutton.center_x = 400
        startbutton.center_y = 300
        self.button_liste.append(startbutton)

    def setup(self):
        
        Baum = arcade.Sprite("Baum.png")
        Baum.center_x = random.randrange(800)
        Baum.center_y = random.randrange(600) 
        
        pizza = arcade.Sprite("pizza.png")
        pizza.center_x = random.randrange(800)
        pizza.center_y = random.randrange(600)
    
        kiste = arcade.Sprite("kiste.png")
        kiste.center_x = random.randrange(800)
        kiste.center_y = random.randrange(600)

        schlüssel = arcade.Sprite("schlüssel.png", 1.3)
        schlüssel.center_x = random.randrange(800)
        schlüssel.center_y = random.randrange(600)
        
        coin3 = arcade.Sprite("coin3.png")
        coin3.center_x = random.randrange(800)
        coin3.center_y = random.randrange(600)

        fuchs = arcade.Sprite("fuchs.png")
        fuchs.center_x = random.randrange(800)
        fuchs.center_y = random.randrange(600)
        
        gameboy = arcade.Sprite("gameboy.png", 0.5)
        gameboy.center_x = random.randrange(800)
        gameboy.center_y = random.randrange(600)
        
        x = 1
        while x < 400:
            Baum = arcade.Sprite("Baum.png")
            Baum.center_x = random.randrange(800)
            Baum.center_y = random.randrange(600)
            self.hide_liste.append(Baum)
            
            busch = arcade.Sprite("busch.png", 0.6)
            busch.center_x = random.randrange(800)
            busch.center_y = random.randrange(600)
            self.hide_liste.append(busch)
            
            x = x + 1
          
        self.gegenstand_liste.append(pizza)
        self.gegenstand_liste.append(gameboy)
        self.gegenstand_liste.append(fuchs)
        self.gegenstand_liste.append(kiste)
        self.gegenstand_liste.append(schlüssel)
        self.gegenstand_liste.append(coin3)
        self.gegenstand_liste[0].kill()

    def rebutton(self):

        rebutton = arcade.Sprite("restart.png")
        rebutton.center_x = 400
        rebutton.center_y = 250
        self.rebutton_liste.append(rebutton)    

    def on_update(self, delta_time):
        if len(self.button_liste) == 0 and len(self.gegenstand_liste) > 0:
            self.total_time += delta_time
            seconds = int(self.total_time)
            seconds_100s = int((self.total_time - seconds) * 100)
            self.timer_text.text = f"{seconds:02d}:{seconds_100s:02d}"
            if self.total_time >= 100:
                self.gegenstand_liste.clear()
    
    def on_mouse_press(self, x, y, taste, modifiers):  
        pseudosprite = arcade.Sprite()
        pseudosprite.center_x = x
        pseudosprite.center_y = y
        pseudosprite.set_hit_box([(-1, -1), (-1, 1), (1, 1), (1, -1)])

        gegenstand_hitliste = arcade.check_for_collision_with_list(pseudosprite, self.gegenstand_liste)
        for gegenstand in gegenstand_hitliste:
            gegenstand.kill()
            self.counter_text = self.counter
            self.counter = self.counter + 1

        button_hitliste = arcade.check_for_collision_with_list(pseudosprite, self.button_liste)
        for button in button_hitliste:
            button.kill()
            self.startscreen_liste.clear()
            self.setup()
        
        rebutton_hitliste = arcade.check_for_collision_with_list(pseudosprite, self.rebutton_liste)
        for rebutton in rebutton_hitliste:
            rebutton.kill()
            self.end_liste.clear()
            self.spielstart()

    def on_key_press(self, key, modifiers):
        if key == arcade.key.R:
            self.neustart()

    def neustart(self):

        self.gegenstand_liste = arcade.SpriteList()
        self.hide_liste = arcade.SpriteList()
        self.end_liste = arcade.SpriteList()
        self.total_time = 0
        self.counter_text = 0
        self.counter = 0

        start = arcade.Sprite("start.png")
        start.center_x = 400
        start.center_y = 300
        self.startscreen_liste.append(start)

        startbutton = arcade.Sprite("startbutton.png")
        startbutton.center_x = 400
        startbutton.center_y = 300
        self.button_liste.append(startbutton)

        self.rebutton_liste = arcade.SpriteList()

    def on_key_press_E(self, key, modifiers):      
        if key == arcade.key.E:
            self.hebe_gegenstaende_hervor()

    def hebe_gegenstaende_hervor(self):
        outline_color = arcade.color.WHITE

        for gegenstand in self.gegenstand_liste:
            gegenstand.outline_color = outline_color
            gegenstand.outline_width = 3

        arcade.schedule(self.zuruecksetzen_umrandung, 2.0)

    def zuruecksetzen_umrandung(self, delta_time):
        for gegenstand in self.gegenstand_liste:
            gegenstand.outline_color = None
            gegenstand.outline_width = 0

    def ende(self):
        ende = arcade.Sprite("End.png")
        ende.center_x = 400   
        ende.center_y = 300
        self.end_liste.append(ende)
        self.rebutton()
   
    def on_draw(self):
        self.clear()
        
        self.startscreen_liste.draw()
        self.gegenstand_liste.draw()
        self.hide_liste.draw()
        self.button_liste.draw()

        if len(self.button_liste) == 0:

            self.timer_text.draw()
            self.timer_text_2.draw()

            arcade.draw_text(str(self.counter), start_x = 700, start_y = 570, color = arcade.color.BLACK, font_size = 20)
        if len(self.gegenstand_liste) == 0:
            self.ende()
            self.end_liste.draw()
            self.rebutton_liste.draw()
            arcade.draw_text(str(self.total_time), start_x = 700, start_y = 570, color = arcade.color.BLACK, font_size = 20)

spiel = Spiel(800, 600, "Suchspiel")
arcade.run()