from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.window import Window

class DosidicusApp(App):
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.2, 1)  # Dark blue background
        
        layout = BoxLayout(orientation='vertical', padding=20)
        
        # Title
        label = Label(
            text="Dosidicus Mobile", 
            size_hint=(1, 0.2), 
            font_size='30sp',
            bold=True
        )
        layout.add_widget(label)
        
        # Squid Image
        # Using a default image if squid.png is missing to prevent crashes
        try:
            squid_image = Image(source='squid.png', size_hint=(1, 0.6))
        except:
            squid_image = Label(text="Squid image not found")
            
        layout.add_widget(squid_image)
        
        # Footer
        footer = Label(
            text="Mobile Visualizer", 
            size_hint=(1, 0.2),
            color=(0.5, 0.5, 0.8, 1)
        )
        layout.add_widget(footer)
        
        return layout

if __name__ == '__main__':
    DosidicusApp().run()
