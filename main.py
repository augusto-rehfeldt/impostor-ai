import os
import random
import sys
from pathlib import Path

# Models come from book writer's shared AI suite, like mathforge and music writer:
# the same provider/model menu, credentials, retries and usage-limit handling.
HERE = Path(__file__).resolve().parent
BOOK_WRITER = Path(os.getenv("IMPOSTOR_BOOK_WRITER") or HERE.parent / "book writer")
service = None


def connect():
    """Pick provider and model with book writer's menu (remembered per script) and build its AIService."""
    global service
    sys.path.insert(0, str(BOOK_WRITER))
    from ai_book_creator.cli import choose_ai
    from ai_book_creator.services.ai_service import AIService

    interactive = sys.stdin.isatty()
    _, config, _ = choose_ai(None, "review" if interactive else "auto",
                             state_file=HERE / "provider_state.json")
    service = AIService(config_path=config, allow_auth_prompt=interactive)
    return service


def ask(prompt):
    return (service or connect()).generate_content(prompt, model_type="writing",
                                                   max_retries=2, wait_for_limits=False).strip()


def tally(game):
    return "impostor" if any(p.is_impostor and not p.was_voted_out for p in game.players) else "crew"


class Player:
    def __init__(self, name, is_impostor=False, secret_person=None):
        self.name = name
        self.is_impostor = is_impostor
        self.secret_person = secret_person
        self.word_said = None
        self.was_voted_out = False
        self.vote_history = []

    def say_word(self, game_context):
        """Each player says one word related to the secret person."""
        words_said = (
            ", ".join([f"{p}: {w}" for p, w in game_context["words_said"].items()])
            or "None yet"
        )

        if self.is_impostor:
            prompt = (
                f"You are the IMPOSTOR in a word-association deduction game.\n"
                f"You do NOT know who the secret person is.\n"
                f"Other players have already said: {words_said}.\n"
                f"Say ONE word that could plausibly relate to those hints and help you blend in.\n"
                f"IMPORTANT: Respond with only ONE word, nothing else."
            )
        else:
            prompt = (
                f"You are a CREWMATE. The secret person is {self.secret_person}.\n"
                f"Other players have already said: {words_said}.\n"
                f"Say ONE word related to {self.secret_person}, giving a subtle hint.\n"
                f"IMPORTANT: Respond with only ONE word, nothing else."
            )

        try:
            return ask(prompt).split()[0].lower()
        except Exception as e:
            print(f"   [Error: {e or 'empty reply'}]")
            return "hmm"

    def defend(self, game_context):
        """Impostor or accused player can defend themselves."""
        words_summary = ", ".join(
            [f"{p}: {w}" for p, w in game_context["words_said"].items()]
        )

        if self.is_impostor:
            prompt = (
                f"You are the IMPOSTOR who has been accused!\n"
                f"The words said were: {words_summary}.\n"
                f"Give a SHORT defense (1-2 sentences) to convince others you're innocent.\n"
                f"Stay in character and be clever."
            )
        else:
            prompt = (
                f"You are a CREWMATE defending yourself against accusations.\n"
                f"The secret person is {self.secret_person} and you said: {self.word_said}.\n"
                f"The words said were: {words_summary}.\n"
                f"Give a SHORT defense (1-2 sentences) reaffirming your innocence.\n"
                f"Stay in character and be subtle."
            )

        try:
            return ask(prompt) or "I am innocent!"
        except Exception as e:
            print(f"   [Error: {e}]")
            return "I am innocent!"

    def vote(self, players, game_context, can_skip=True):
        """Each player votes for who they think is the impostor."""
        active_players = [p for p in players if not p.was_voted_out and p.name != self.name]
        player_names = [p.name for p in active_players]

        if can_skip:
            player_names.append("SKIP")

        words_summary = ", ".join(
            [f"{p}: {w}" for p, w in game_context["words_said"].items()]
        )

        if self.is_impostor:
            prompt = (
                f"You are the IMPOSTOR trying to avoid being voted out.\n"
                f"Players and their words: {words_summary}\n"
                f"Vote for someone whose word seems MOST suspicious or random.\n"
                f"Respond with ONLY the NAME of the player you vote for."
            )
        else:
            prompt = (
                f"You are a CREWMATE trying to find the IMPOSTOR.\n"
                f"The secret person is {self.secret_person}.\n"
                f"Players and their words: {words_summary}\n"
                f"Identify who seems most suspicious and vote for them.\n"
                f"Respond with ONLY the NAME of the player you vote for."
            )

        try:
            voted_player_name = ask(prompt)
            # Validate vote
            if voted_player_name not in player_names:
                voted_player_name = random.choice(player_names)
            return voted_player_name
        except Exception as e:
            print(f"   [Error: {e}]")
            return random.choice(player_names)


CATEGORIES = {
    "Historical Figures": [
        "Socrates", "Plato", "Aristotle", "Alexander the Great", "Confucius",
        "Laozi", "Sun Tzu", "Julius Caesar", "Augustus", "Cleopatra",
        "Hammurabi", "Homer", "Leonidas I", "Pericles", "Hippocrates",
        "Archimedes", "Pythagoras", "Hannibal Barca", "Spartacus", "Boudica",
        "Charlemagne", "Genghis Khan", "Marco Polo", "William the Conqueror",
        "Joan of Arc", "Leonardo da Vinci", "Michelangelo", "Raphael",
        "Galileo Galilei", "Copernicus", "Kepler", "Isaac Newton", "Descartes",
        "Voltaire", "Rousseau", "John Locke", "Thomas Hobbes", "Kant",
        "Martin Luther", "Shakespeare", "Cervantes", "Machiavelli",
        "Christopher Columbus", "Magellan", "Napoleon", "Washington",
        "Jefferson", "Franklin", "Lincoln", "Nelson Mandela", "Marie Curie",
        "Einstein", "Freud", "Churchill", "Gandhi", "Che Guevara",
        "Elizabeth I", "Victoria", "Catherine the Great", "Joan of Arc",
    ],
    "Scientists & Inventors": [
        "Einstein", "Newton", "Darwin", "Curie", "Tesla", "Edison",
        "Bell", "Pasteur", "Mendel", "Galileo", "Copernicus", "Kepler",
        "Hawking", "Turing", "Babbage", "Lovelace", "Fermi", "Bohr",
        "Einstein", "Dirac", "Schrödinger", "Heisenberg", "Curie",
        "Shockley", "Morse", "Bell", "Whitney", "McCormick", "Ford",
        "Wright Brothers", "Jobs", "Gates", "Musk",
    ],
    "Artists & Writers": [
        "Shakespeare", "Dante", "Homer", "Virgil", "Cervantes", "Tolstoy",
        "Dostoevsky", "Austen", "Dickens", "Hemingway", "Fitzgerald",
        "Picasso", "Van Gogh", "Monet", "Da Vinci", "Michelangelo", "Raphael",
        "Rembrandt", "Warhol", "Kahlo", "Dali", "Frida Kahlo",
        "Beethoven", "Mozart", "Bach", "Wagner", "Tchaikovsky",
        "Oscar Wilde", "Poe", "Twain", "Austen", "Brontë",
    ],
    "World Leaders": [
        "Lincoln", "Washington", "Jefferson", "FDR", "Eisenhower", "Kennedy",
        "Reagan", "Clinton", "Obama", "Napoleon", "Churchill", "De Gaulle",
        "Hitler", "Stalin", "Lenin", "Trotsky", "Mao", "Deng Xiaoping",
        "Gandhi", "Nehru", "Ataturk", "Khaled", "Fidel", "Ho Chi Minh",
        "Margaret Thatcher", "Tony Blair", "Merkel", "Macron",
        "Peter the Great", "Catherine the Great", "Ivan the Terrible",
    ],
}

# Auto-generate player names pool
PLAYER_NAME_POOL = [
    "Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Heidi",
    "Ivan", "Judy", "Kevin", "Laura", "Mike", "Nancy", "Oscar", "Peggy",
    "Quinn", "Ruth", "Steve", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zack", "Alex", "Blake", "Casey", "Dana", "Elliot", "Flynn",
    "Gray", "Harper", "Indigo", "Jesse", "Kai", "Logan", "Maya", "Nolan",
    "Phoenix", "Quinn", "River", "Sage", "Tanner", "Unity", "Vesper", "Winter",
]


class Game:
    def __init__(self, players_names, category_name=None, num_impostors=1):
        self.players = []
        self.category_name = category_name
        self.num_impostors = num_impostors
        self.figures = CATEGORIES.get(category_name, random.choice(list(CATEGORIES.values())))
        self.secret_person = None
        self.impostors = []
        self.round_number = 0
        self.max_rounds = 10
        self.round_history = []
        self.setup_game(players_names)

    def setup_game(self, players_names):
        self.secret_person = random.choice(self.figures)

        # Select impostors
        impostor_names = random.sample(players_names, self.num_impostors)

        for name in players_names:
            if name in impostor_names:
                player = Player(name, is_impostor=True)
                self.impostors.append(player)
            else:
                player = Player(name, secret_person=self.secret_person)
            self.players.append(player)

        random.shuffle(self.players)

        print("\n" + "=" * 50)
        print("🎭 IMPOSTOR - A Deduction Game 🎭")
        print("=" * 50)
        print(f"\n📂 Category: {self.category_name}")
        print(f"🔍 Secret person: {self.secret_person}")
        print(f"🕵️  Impostor(s): {', '.join([p.name for p in self.impostors])}")
        print(f"👥 Players: {', '.join([p.name for p in self.players])}")

    def display_status(self):
        """Display current game status."""
        active = [p for p in self.players if not p.was_voted_out]
        print(f"\n📊 Round {self.round_number} | Active players: {len(active)}")
        print("-" * 40)
        for p in self.players:
            status = "❌" if p.was_voted_out else ("🕵️" if p.is_impostor else "👤")
            word = p.word_said if p.word_said else "-"
            print(f"  {status} {p.name}: {word}")
        print("-" * 40)

    def play_round(self):
        """Play one round of the game."""
        if self.round_number >= self.max_rounds:
            return True, "max_rounds"
        self.round_number += 1

        print(f"\n{'=' * 50}")
        print(f"📍 ROUND {self.round_number}")
        print(f"{'=' * 50}")

        game_context = {"secret_person": self.secret_person, "words_said": {}}

        # Phase 1: Word association
        print("\n📝 WORD ASSOCIATION PHASE")
        print("Each player says one word related to the secret person...\n")

        for player in self.players:
            if player.was_voted_out:
                continue

            print(f"[{player.name}'s turn]")
            word = player.say_word(game_context)
            player.word_said = word
            game_context["words_said"][player.name] = word
            print()

        self.display_status()

        # Phase 2: Discussion
        print("\n💬 DISCUSSION PHASE")
        print("Players discuss who they think is suspicious...\n")

        accused = self.pick_most_suspicious(game_context)
        if accused and not accused.was_voted_out:
            print(f"🔔 {accused.name} is being questioned!")
            defense = accused.defend(game_context)
            print(f"   🗣️  {accused.name} says: \"{defense}\"")

        # Phase 3: Voting
        print("\n🗳️ VOTING PHASE")
        print("Each player votes for who they think is the impostor...\n")

        votes = {}
        vote_details = {}

        for player in self.players:
            if player.was_voted_out:
                continue

            voted_name = player.vote(self.players, game_context)
            player.vote_history.append(voted_name)

            if voted_name == "SKIP":
                print(f"[{player.name}] → SKIP")
            else:
                print(f"[{player.name}] → votes for {voted_name}")

            votes[voted_name] = votes.get(voted_name, 0) + 1
            vote_details[player.name] = voted_name

        # Count votes
        print("\n📊 VOTE TALLY:")
        for name, count in sorted(votes.items(), key=lambda x: -x[1]):
            print(f"   {name}: {count} vote(s)")

        # Determine outcome
        if not votes:
            return False, "no_votes"

        voted_out_name = max(votes, key=votes.get)
        tied = sum(1 for c in votes.values() if c == votes[voted_out_name]) > 1

        if tied:
            print("\n⚖️ The vote is TIED! No one is voted out.")
            return False, "tie"

        if voted_out_name == "SKIP":
            print("\n⚪ Players chose to SKIP. No one is voted out.")
            return False, "skip"

        voted_out_player = next(p for p in self.players if p.name == voted_out_name)
        voted_out_player.was_voted_out = True

        print(f"\n❌ {voted_out_name} was voted out!")

        # Reveal truth
        if voted_out_player.is_impostor:
            print(f"✅ It was {voted_out_name}! An IMPOSTOR was caught!")
        else:
            print(f"⚠️ {voted_out_name} was innocent. The game continues...")

        # Check win conditions
        remaining_impostors = [p for p in self.players if p.is_impostor and not p.was_voted_out]
        remaining_crew = [p for p in self.players if not p.is_impostor and not p.was_voted_out]

        if len(remaining_impostors) == 0:
            return True, "crew_win"
        if len(remaining_impostors) >= len(remaining_crew):
            return True, "impostor_win"

        return False, "continue"

    def pick_most_suspicious(self, game_context):
        """Pick the player who seems most suspicious based on their word."""
        words = {p.name: p.word_said for p in self.players if not p.was_voted_out}

        prompt = (
            f"You are analyzing suspicious behavior in a deduction game.\n"
            f"The secret person is: {self.secret_person}\n"
            f"Player words: {words}\n"
            f"Based on the words, which player seems MOST suspicious and likely to be the impostor?\n"
            f"Respond with ONLY the player's name."
        )

        try:
            name = ask(prompt)
            return next((p for p in self.players if p.name == name), None)
        except Exception:
            return None

    def start_game(self):
        """Start the game loop."""
        game_over = False
        result = None

        while not game_over:
            result = self.play_round()
            game_over, outcome = result

            if outcome == "max_rounds":
                print("\n🏁 Maximum rounds reached!")
                remaining_impostors = [p.name for p in self.players if p.is_impostor and not p.was_voted_out]
                print(f"😈 Impostor(s) escaped: {', '.join(remaining_impostors)}")
                break

            if outcome in ("crew_win", "impostor_win"):
                break
            if self.round_number >= self.max_rounds:
                continue  # next play_round reports max_rounds; no prompt needed

            print("\nPress Enter to continue to the next round...")
            input()

        # Game over summary
        self.show_game_summary(outcome)

    def show_game_summary(self, outcome):
        """Show a summary of the game."""
        print("\n" + "=" * 50)
        print("📜 GAME OVER SUMMARY")
        print("=" * 50)
        print(f"\n🏆 Result: {'CREWMATES WIN! 🎉' if outcome == 'crew_win' else 'IMPOSTOR WINS! 😈'}")
        print(f"🔍 Secret person: {self.secret_person}")
        print(f"🕵️  Impostor(s): {', '.join([p.name for p in self.impostors])}")
        print(f"📍 Rounds played: {self.round_number}")
        print("\n📊 Word History:")
        for p in self.players:
            if p.word_said:
                tag = "[IMPOSTOR]" if p.is_impostor else ""
                print(f"   {p.name} {tag}: {p.word_said}")
        print("=" * 50)


def play_again(scores):
    """Ask if players want to play again."""
    print("\n🎮 Play again?")
    print("1. Yes, same settings")
    print("2. Yes, new category")
    print("3. View scores")
    print("4. Quit")

    choice = input("\n> ").strip()
    return choice


def main():
    connect()  # provider/model menu first, so a missing credential stops before game setup
    scores = {"crew": 0, "impostor": 0}

    print("🎭 IMPOSTOR - A Deduction Game 🎭")
    print("=" * 40)
    print("\nTry to identify the IMPOSTOR among the crew!")
    print("Everyone knows the secret person EXCEPT the impostor.")
    print("Use word associations to find clues and vote out the impostor!\n")

    # Setup - number of players
    print("How many players? (4-10)")
    num_players_input = input("> ").strip()

    try:
        num_players = int(num_players_input)
        num_players = max(4, min(10, num_players))
    except:
        num_players = 4

    print(f"\n👥 Players: {num_players}")

    # Auto-generate player names
    players_names = random.sample(PLAYER_NAME_POOL, num_players)

    print(f"\n👥 Players: {', '.join(players_names)}")

    print("\n📂 Available Categories:")
    for i, name in enumerate(CATEGORIES.keys(), 1):
        print(f"   {i}. {name}")
    print(f"   {len(CATEGORIES) + 1}. Random")

    cat_choice = input("\nSelect category (number)> ").strip()
    try:
        idx = int(cat_choice) - 1
        cat_names = list(CATEGORIES.keys())
        if idx == len(cat_names):
            category_name = random.choice(cat_names)
        else:
            category_name = cat_names[idx]
    except:
        category_name = random.choice(list(CATEGORIES.keys()))

    # Number of impostors
    num_imp = 1
    if len(players_names) >= 6:
        print("\nHow many impostors? (1-2)")
        try:
            num_imp = int(input("> ").strip())
            num_imp = max(1, min(2, num_imp))
        except:
            num_imp = 1

    game = Game(players_names, category_name, num_impostors=num_imp)
    game.start_game()
    scores[tally(game)] += 1

    # Play again loop
    while True:
        choice = play_again(scores)
        if choice == "1":
            game = Game(players_names, category_name, num_impostors=num_imp)
            game.start_game()
            scores[tally(game)] += 1
        elif choice == "2":
            cat_names = list(CATEGORIES.keys())
            print("\n📂 Categories:")
            for i, name in enumerate(cat_names, 1):
                print(f"   {i}. {name}")

            cat_choice = input("\nSelect category (number)> ").strip()
            try:
                idx = int(cat_choice) - 1
                category_name = cat_names[idx]
            except:
                category_name = random.choice(cat_names)

            game = Game(players_names, category_name, num_impostors=num_imp)
            game.start_game()
            scores[tally(game)] += 1
        elif choice == "3":
            print(f"\n📊 Overall Score:")
            print(f"   Crewmates: {scores['crew']}")
            print(f"   Impostors: {scores['impostor']}")
        else:
            print("\nThanks for playing! 👋")
            break

    print(f"\nFinal Score - Crew: {scores['crew']} | Impostor: {scores['impostor']}")


if __name__ == "__main__":
    main()
