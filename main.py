import os
import subprocess
import config
import threading
import time
import re
import pygame

WIDTH, HEIGHT = 1200, 750
FPS = 60

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

WHITE = (245, 245, 245)
BLACK = (20, 20, 20)
DARK_BG = (30, 30, 40)
PANEL_BG = (45, 45, 60)
PANEL_BORDER = (70, 70, 90)
BTN_BG = (80, 200, 120)
BTN_HOVER = (100, 230, 140)
BTN_DISABLED = (100, 100, 100)
BTN_TEXT = (255, 255, 255)
BUBBLE_BG = (255, 255, 255)
BUBBLE_BORDER = (200, 200, 200)
ACCENT = (0, 180, 255)
IMPOSTOR_RED = (255, 50, 50)
TITLE_COLOR = (255, 255, 255)

PLAYER_COLORS = {
    "Cristina": (120, 61, 210),    # Purple
    "Andrei": (80, 150, 255),     # Blue
    "Alessia": (80, 220, 80),  # Green
    "Stefan": (255, 220, 80),    # Yellow
}

PLAYER_SPRITES = {
    "Cristina": "Purple.png",
    "Andrei": "Blue.png",
    "Alessia": "Green.png",
    "Stefan": "Yellow.png",
}

TESTIMONIES = {
    "Cristina": "I was in Navigation and saw Andrei in Security.",
    "Andrei": "I was in Shields and saw Cristina in Electrical.",
    "Alessia": "I was in Navigation with Cristina.",
    "Stefan": "I was in Security with Andrei.",
}

ROOMS = ["Electrical", "Navigation", "Shields", "Security"]
PLAYERS = ["Cristina", "Andrei", "Alessia", "Stefan"]

def parse_testimony_to_fact(speaker: str, testimony: str) -> str:
    t = testimony.strip()

    m = re.fullmatch(r"I was in (\w+) and saw (\w+) in (\w+)\.", t)
    if m:
        r_speaker, other, r_other = m.groups()
        return f"(room({speaker}, {r_speaker}) & room({other}, {r_other}))"

    m = re.fullmatch(r"I was in (\w+) with (\w+)\.", t)
    if m:
        r_speaker, other = m.groups()
        return f"(room({speaker}, {r_speaker}) & room({other}, {r_speaker}))"

    raise ValueError(f"Unrecognized testimony format for {speaker}: {testimony!r}")


def generate_scenario_in_from_testimonies(testimonies: dict[str, str], out_path: str = "scenario.in") -> None:
    players = [p for p in PLAYERS if p in testimonies]
    if len(players) != 4:
        raise ValueError(f"Expected testimonies for 4 players {PLAYERS}, got: {players}")

    # players distinct
    player_neq_parts = []
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            player_neq_parts.append(f"{players[i]} != {players[j]}")
    player_neq = " & ".join(player_neq_parts) + "."

    # rooms distinct
    room_neq_parts = []
    for i in range(len(ROOMS)):
        for j in range(i + 1, len(ROOMS)):
            room_neq_parts.append(f"{ROOMS[i]} != {ROOMS[j]}")
    room_neq = " & ".join(room_neq_parts) + "."

    # at least one impostor
    at_least_one = " | ".join(f"impostor({p})" for p in players) + "."

    # at most one impostor
    at_most_one_lines = []
    for p in players:
        others = [o for o in players if o != p]
        rhs = " & ".join(f"-impostor({o})" for o in others)
        at_most_one_lines.append(f"    impostor({p}) -> {rhs}.")

    # testimonies
    testimony_lines = []
    for speaker in players:
        fact = parse_testimony_to_fact(speaker, testimonies[speaker])
        testimony_lines.append(f"    (crewmate({speaker}) -> {fact}).")
        testimony_lines.append(f"    (impostor({speaker}) -> -{fact}).")
        testimony_lines.append("")

    content_lines = [
        "formulas (assumptions).",
        "    all x (crewmate(x) <-> -impostor(x)).",
        f"    {player_neq}",
        f"    {room_neq}",
        f"    {at_least_one}",
        "    all x all r1 all r2 (room(x, r1) & room(x, r2) -> r1 = r2).",
        *at_most_one_lines,
        "",
        *testimony_lines,
        "end_of_list.",
        "",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content_lines))

class Button:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.enabled = True
        self.hovered = False

    def draw(self, surface):
        if not self.enabled:
            color = BTN_DISABLED
        elif self.hovered:
            color = BTN_HOVER
        else:
            color = BTN_BG

        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=12)

        text_surface = self.font.render(self.text, True, BTN_TEXT)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos) and self.enabled:
                return True
        return False


class AmongUsGame:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Among Us - Who is the Impostor?")
        self.clock = pygame.time.Clock()
        self.running = True
        self.emergency_sound = self.load_sounds()
        self.reveal_sound = pygame.mixer.Sound(os.path.join(ASSETS_DIR, "sounds", "among-us-sound.mp3"))
        self.scan_sound = pygame.mixer.Sound(os.path.join(ASSETS_DIR, "sounds", "scanning.mp3"))
        self.scan_sound.set_volume(0.3)

        self.title_font = pygame.font.SysFont("Arial", 42, bold=True)
        self.subtitle_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.text_font = pygame.font.SysFont("Arial", 16)
        self.bubble_font = pygame.font.SysFont("Arial", 14)
        self.btn_font = pygame.font.SysFont("Arial", 28, bold=True)
        self.result_font = pygame.font.SysFont("Arial", 32, bold=True)

        self.sprites = {}
        self.load_sprites()

        self.solving = False
        self.solve_result = None
        self.impostor = None
        self.animation_frame = 0
        self.animation_dots = 0
        self.selected_player = None

        btn_width, btn_height = 200, 60
        btn_x = (WIDTH - btn_width) // 2
        btn_y = HEIGHT - 100
        self.solve_button = Button(btn_x, btn_y, btn_width, btn_height, "SOLVE", self.btn_font)

        self.player_positions = self.calculate_player_positions()
        self.sprite_rects = {}

        self.emergency_meeting_img = self.load_emergency_meeting()
        self.background_img = self.load_background()

    def load_emergency_meeting(self):
        path = os.path.join(ASSETS_DIR, "Green_calls_emergency_meeting.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img_width = int(img.get_width() * (HEIGHT / img.get_height()))
            return pygame.transform.scale(img, (img_width, HEIGHT))
        return None

    def load_background(self):
        path = os.path.join(ASSETS_DIR, "background.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img_width = int(img.get_width() * (HEIGHT / img.get_height()))
            return pygame.transform.scale(img, (img_width, HEIGHT))
        return None

    def load_sounds(self):
        path = os.path.join(ASSETS_DIR, "sounds", "alarm_emergencymeeting.mp3")
        if os.path.exists(path):
            return pygame.mixer.Sound(path)
        return None

    def show_emergency_meeting(self):
        if not self.emergency_meeting_img:
            return

        if self.emergency_sound:
            self.emergency_sound.play()
        
        start_time = time.time()
        while time.time() - start_time < 4:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return
            
            self.screen.fill(DARK_BG)
            img_rect = self.emergency_meeting_img.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            self.screen.blit(self.emergency_meeting_img, img_rect)
            pygame.display.flip()
            self.clock.tick(FPS)

    def load_sprites(self):
        for player, sprite_file in PLAYER_SPRITES.items():
            path = os.path.join(ASSETS_DIR, sprite_file)
            if os.path.exists(path):
                sprite = pygame.image.load(path).convert_alpha()
                sprite = pygame.transform.scale(sprite, (100, 120))
                self.sprites[player] = sprite

    def calculate_player_positions(self):

        game_area_start = 320
        game_area_width = WIDTH - game_area_start - 40
        spacing = game_area_width // 4
        start_x = game_area_start + spacing // 2

        positions = {}
        players = ["Cristina", "Andrei", "Alessia", "Stefan"]
        for i, player in enumerate(players):
            x = start_x + i * spacing
            y = 380
            positions[player] = (x, y)
        return positions

    def draw_speech_bubble(self, surface, text, x, y, color):

        words = text.split()
        lines = []
        current_line = ""
        max_width = 150

        for word in words:
            test_line = current_line + " " + word if current_line else word
            if self.bubble_font.size(test_line)[0] < max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        line_height = 20
        padding = 12
        bubble_width = max(self.bubble_font.size(line)[0] for line in lines) + padding * 2
        bubble_height = len(lines) * line_height + padding * 2

        bubble_x = x - bubble_width // 2
        bubble_y = y - bubble_height - 30

        bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_width, bubble_height)
        pygame.draw.rect(surface, BUBBLE_BG, bubble_rect, border_radius=10)
        pygame.draw.rect(surface, color, bubble_rect, 2, border_radius=10)

        tail_points = [
            (x - 8, bubble_y + bubble_height),
            (x + 8, bubble_y + bubble_height),
            (x, bubble_y + bubble_height + 15)
        ]
        pygame.draw.polygon(surface, BUBBLE_BG, tail_points)
        pygame.draw.lines(surface, color, False, [tail_points[0], tail_points[2], tail_points[1]], 2)

        for i, line in enumerate(lines):
            text_surface = self.bubble_font.render(line, True, BLACK)
            text_x = bubble_x + padding
            text_y = bubble_y + padding + i * line_height
            surface.blit(text_surface, (text_x, text_y))

    def draw_statement_panel(self, surface):
        panel_rect = pygame.Rect(20, 100, 280, 500)
        pygame.draw.rect(surface, PANEL_BG, panel_rect, border_radius=15)
        pygame.draw.rect(surface, PANEL_BORDER, panel_rect, 2, border_radius=15)

        title_surface = self.subtitle_font.render("TESTIMONIES", True, WHITE)
        surface.blit(title_surface, (40, 115))

        pygame.draw.line(surface, PANEL_BORDER, (40, 150), (280, 150), 2)

        y_offset = 170
        for player, testimony in TESTIMONIES.items():
            color = PLAYER_COLORS[player]
            pygame.draw.circle(surface, color, (50, y_offset + 8), 8)

            name_surface = self.text_font.render(f"{player}:", True, color)
            surface.blit(name_surface, (70, y_offset))

            words = testimony.split()
            lines = []
            current_line = ""
            max_width = 220

            for word in words:
                test_line = current_line + " " + word if current_line else word
                if self.text_font.size(test_line)[0] < max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            for i, line in enumerate(lines):
                text_surface = self.text_font.render(line, True, WHITE)
                surface.blit(text_surface, (50, y_offset + 25 + i * 20))

            y_offset += 35 + len(lines) * 20 + 15

    def draw_players(self, surface):
        for player, (x, y) in self.player_positions.items():
            sprite = self.sprites[player]
            sprite_rect = sprite.get_rect(center=(x, y))
            self.sprite_rects[player] = sprite_rect

            if self.impostor == player:
                glow_surface = pygame.Surface((140, 160), pygame.SRCALPHA)
                pygame.draw.ellipse(glow_surface, (*IMPOSTOR_RED, 100), (0, 0, 140, 160))
                surface.blit(glow_surface, (x - 70, y - 80))

            surface.blit(sprite, sprite_rect)

            name_color = IMPOSTOR_RED if self.impostor == player else PLAYER_COLORS[player]
            name_surface = self.subtitle_font.render(player, True, name_color)
            name_rect = name_surface.get_rect(center=(x, y + 80))
            surface.blit(name_surface, name_rect)

            if self.selected_player == player:
                self.draw_speech_bubble(surface, TESTIMONIES[player], x, y - 60, PLAYER_COLORS[player])

    def handle_sprite_click(self, pos):
        for player, rect in self.sprite_rects.items():
            if rect.collidepoint(pos):
                if self.selected_player == player:
                    self.selected_player = None
                else:
                    self.selected_player = player
                return True
        return False

    def draw_title(self, surface):
        title_text = "AMONG US - WHO IS THE IMPOSTOR?"
        title_surface = self.title_font.render(title_text, True, TITLE_COLOR)
        title_rect = title_surface.get_rect(center=(WIDTH // 2, 50))
        surface.blit(title_surface, title_rect)

    def draw_loading_animation(self, surface):
        self.animation_frame += 1
        if self.animation_frame % 20 == 0:
            self.animation_dots = (self.animation_dots + 1) % 4

        dots = "." * self.animation_dots
        text = f"Scanning Bio-signals{dots}"
        text_surface = self.subtitle_font.render(text, True, ACCENT)
        text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT - 140))
        surface.blit(text_surface, text_rect)

    def draw_result(self, surface):
        if self.impostor:
            text = f"{self.impostor} is the IMPOSTOR!"
            text_surface = self.result_font.render(text, True, IMPOSTOR_RED)
        else:
            text = "Could not determine the impostor"
            text_surface = self.result_font.render(text, True, WHITE)

        text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT - 140))
        surface.blit(text_surface, text_rect)

    def run_mace4(self):
        self.solving = True
        self.solve_button.enabled = False
        self.impostor = None

        if self.scan_sound:
            self.scan_sound.play(loops=-1)

        def solve():
            try:
                generate_scenario_in_from_testimonies(TESTIMONIES, out_path="scenario_v1.in")

                mace4_path = config.MACE4_PATH
                input_file = "scenario_v1.in"
                absolute_path = os.path.abspath(input_file)
                wsl_path = absolute_path.replace('\\', '/').replace('C:', '/mnt/c').replace('c:', '/mnt/c')

                cmd = ["wsl", mace4_path, "-f", wsl_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    output = result.stdout
                    print(output)

                    player_indices = {}
                    for player in PLAYERS:
                        match = re.search(rf"function\({player},\s*\[\s*(\d+)\s*\]\)", output)
                        if match:
                            player_indices[int(match.group(1))] = player

                    impostor_match = re.search(r"relation\(impostor\(_\),\s*\[\s*([\d,\s]+)\s*\]\)", output)
                    if impostor_match and player_indices:
                        values_str = impostor_match.group(1)
                        values = [int(v.strip()) for v in values_str.split(',')]
                        for idx, val in enumerate(values):
                            if val == 1 and idx in player_indices:
                                self.impostor = player_indices[idx]
                                self.solve_result = 1
                                break

                else:
                    self.solve_result = result.stderr

            except Exception as e:
                self.solve_result = str(e)

            if self.scan_sound:
                self.scan_sound.stop()
            self.solving = False
            self.solve_button.enabled = True

        thread = threading.Thread(target=solve)
        thread.start()

    def run(self):
        self.show_emergency_meeting()
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_sprite_click(event.pos)

                if self.solve_button.handle_event(event):
                    self.run_mace4()

            self.screen.fill(DARK_BG)
            img_rect = self.background_img.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            self.screen.blit(self.background_img, img_rect)

            self.draw_title(self.screen)
            self.draw_statement_panel(self.screen)
            self.draw_players(self.screen)
            self.solve_button.draw(self.screen)

            if self.solving:
                self.draw_loading_animation(self.screen)
            elif self.solve_result:
                pygame.display.flip()
                self.play_ejection_animation()
                self.solve_result = None

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    def play_ejection_animation(self):
        if not self.impostor:
            return
        if self.reveal_sound:
            self.reveal_sound.play()

        space_path = os.path.join(ASSETS_DIR, "space.png")
        if os.path.exists(space_path):
            space_bg = pygame.image.load(space_path).convert()
            space_bg = pygame.transform.scale(space_bg, (WIDTH, HEIGHT))
        else:
            space_bg = pygame.Surface((WIDTH, HEIGHT))
            space_bg.fill(BLACK)

        original_sprite = self.sprites[self.impostor]
        sprite_x = -150
        sprite_y = HEIGHT // 2 - 60
        angle = 0

        eject_text = f"{self.impostor} was The Impostor"

        animating = True
        start_time = pygame.time.get_ticks()

        while animating:
            current_time = pygame.time.get_ticks()
            elapsed = current_time - start_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

            sprite_x += 5
            angle += 3

            self.screen.blit(space_bg, (0, 0))
            rotated_sprite = pygame.transform.rotate(original_sprite, angle)
            rect = rotated_sprite.get_rect(center=(sprite_x, sprite_y))
            self.screen.blit(rotated_sprite, rect)

            if sprite_x > WIDTH // 4:
                text_surface = self.result_font.render(eject_text, True, WHITE)
                text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                self.screen.blit(text_surface, text_rect)

            if elapsed > 6000:
                animating = False

            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    game = AmongUsGame()
    game.run()
