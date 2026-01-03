import toga
from toga.style import Pack
from toga.style.pack import COLUMN, CENTER

class DosidicusApp(toga.App):
    def startup(self):
        # Create the main box with dark blue background
        main_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                padding=20,
                background_color=(0.1, 0.1, 0.2, 1),  # Dark blue background
                alignment=CENTER
            )
        )

        # Title
        title_label = toga.Label(
            "Dosidicus Mobile",
            style=Pack(
                flex=0.2,
                font_size=30,
                font_weight='bold',
                text_align=CENTER
            )
        )
        main_box.add(title_label)

        # Squid Image
        # Using a default label if squid.png is missing to prevent crashes
        try:
            squid_image = toga.Image('squid.png', style=Pack(flex=0.6))
        except:
            squid_image = toga.Label("Squid image not found", style=Pack(flex=0.6, text_align=CENTER))

        main_box.add(squid_image)

        # Footer
        footer_label = toga.Label(
            "Mobile Visualizer",
            style=Pack(
                flex=0.2,
                color=(0.5, 0.5, 0.8, 1),
                text_align=CENTER
            )
        )
        main_box.add(footer_label)

        # Create the main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

def main():
    return DosidicusApp()

if __name__ == '__main__':
    app = main()
    app.main_loop()
