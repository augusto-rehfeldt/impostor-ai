"""Offline unit tests for Impostor; book writer's shared AI suite is stubbed.

Run from this directory: python -B -m unittest -q test_main
"""
import contextlib
import io
import random
import sys
import unittest
from unittest import mock

sys.modules["openai"] = None  # the game must not use a provider SDK directly
import main  # noqa: E402

NAMES = ["Alice", "Bob", "Charlie", "David", "Eve"]


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def make_game(num_impostors=1, impostors=None):
    game = quiet(main.Game, list(NAMES), "World Leaders", num_impostors=num_impostors)
    if impostors:
        for p in game.players:
            p.is_impostor = p.name in impostors
            p.secret_person = None if p.is_impostor else game.secret_person
        game.impostors = [p for p in game.players if p.is_impostor]
    return game


def rigged_round(game, target):
    """Play one round where everyone votes for `target`."""
    with mock.patch.object(main.Player, "say_word", return_value="word"), \
         mock.patch.object(main.Player, "vote", return_value=target), \
         mock.patch.object(main.Game, "pick_most_suspicious", return_value=None):
        return quiet(game.play_round)


def fake_book_writer(choose_ai, ai_service):
    """sys.modules entries standing in for book writer's ai_book_creator package."""
    return {"ai_book_creator": mock.Mock(),
            "ai_book_creator.cli": mock.Mock(choose_ai=choose_ai),
            "ai_book_creator.services": mock.Mock(),
            "ai_book_creator.services.ai_service": mock.Mock(AIService=ai_service)}


class SharedSuiteTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, main, "service", None)

    def test_connect_uses_book_writer_menu_and_service(self):
        choose_ai = mock.Mock(return_value=("hyper", "cfg.json", ["m"]))
        ai_service = mock.Mock()
        with mock.patch.dict(sys.modules, fake_book_writer(choose_ai, ai_service)), \
             mock.patch.object(sys, "path", list(sys.path)):
            self.assertIs(quiet(main.connect), ai_service.return_value)
            self.assertIn(str(main.BOOK_WRITER), sys.path)
        self.assertEqual(choose_ai.call_args.kwargs["state_file"], main.HERE / "provider_state.json")
        self.assertEqual(ai_service.call_args.kwargs["config_path"], "cfg.json")
        self.assertIs(main.service, ai_service.return_value)

    def test_ask_returns_generated_text(self):
        main.service = mock.Mock(**{"generate_content.return_value": "  Hat \n"})
        self.assertEqual(main.ask("prompt"), "Hat")
        # A turn fails fast; the callers fall back to a neutral move instead of stalling for hours.
        main.service.generate_content.assert_called_once_with("prompt", model_type="writing",
                                                              max_retries=2, wait_for_limits=False)

    def test_ask_connects_once_on_first_use(self):
        shared = mock.Mock(**{"generate_content.return_value": "x"})

        def connect():
            main.service = shared
            return shared
        with mock.patch.object(main, "connect", side_effect=connect) as patched:
            main.ask("a")
            main.ask("b")
        patched.assert_called_once()

    def test_main_picks_provider_before_setup_questions(self):
        order = []

        def stop(*args):
            order.append("input")
            raise KeyboardInterrupt
        with mock.patch.object(main, "connect", side_effect=lambda: order.append("connect")), \
             mock.patch("builtins.input", side_effect=stop):
            with self.assertRaises(KeyboardInterrupt):
                quiet(main.main)
        self.assertEqual(order, ["connect", "input"])


class HelperTests(unittest.TestCase):
    def test_tally(self):
        game = make_game(impostors={"Alice"})
        self.assertEqual(main.tally(game), "impostor")
        next(p for p in game.players if p.name == "Alice").was_voted_out = True
        self.assertEqual(main.tally(game), "crew")


class SetupTests(unittest.TestCase):
    def test_roles_assigned(self):
        random.seed(0)
        for count in (1, 2):
            game = make_game(num_impostors=count)
            self.assertEqual(sorted(p.name for p in game.players), sorted(NAMES))
            self.assertEqual(len(game.impostors), count)
            self.assertIn(game.secret_person, main.CATEGORIES["World Leaders"])
            for p in game.players:
                self.assertEqual(p.secret_person, None if p.is_impostor else game.secret_person)

    def test_unknown_category_uses_a_real_one(self):
        game = quiet(main.Game, list(NAMES), "nope")
        self.assertIn(game.figures, list(main.CATEGORIES.values()))


class PlayerTests(unittest.TestCase):
    ctx = {"secret_person": "Lincoln", "words_said": {"Bob": "hat"}}

    def test_say_word_takes_first_word_lowercase(self):
        with mock.patch.object(main, "ask", return_value="Stovepipe hat") as ask:
            self.assertEqual(main.Player("A", secret_person="Lincoln").say_word(self.ctx), "stovepipe")
        self.assertIn("Lincoln", ask.call_args.args[0])

    def test_impostor_prompt_hides_secret(self):
        with mock.patch.object(main, "ask", return_value="hat") as ask:
            main.Player("A", is_impostor=True).say_word(self.ctx)
        self.assertNotIn("Lincoln", ask.call_args.args[0])

    def test_api_errors_fall_back(self):
        player = main.Player("A", secret_person="Lincoln")
        with mock.patch.object(main, "ask", side_effect=RuntimeError("down")):
            self.assertEqual(quiet(player.say_word, self.ctx), "hmm")
            self.assertEqual(quiet(player.defend, self.ctx), "I am innocent!")
            players = [player, main.Player("B")]
            self.assertIn(quiet(player.vote, players, self.ctx), {"B", "SKIP"})

    def test_empty_reply_falls_back(self):
        with mock.patch.object(main, "ask", return_value=""):
            self.assertEqual(quiet(main.Player("A", secret_person="Lincoln").say_word, self.ctx), "hmm")

    def test_vote_is_validated(self):
        players = [main.Player(n) for n in ("A", "B", "C")]
        players[2].was_voted_out = True
        with mock.patch.object(main, "ask", return_value="B"):
            self.assertEqual(players[0].vote(players, self.ctx), "B")
        for invalid in ("A", "C", "Zed"):  # self, eliminated, unknown
            with mock.patch.object(main, "ask", return_value=invalid):
                self.assertIn(players[0].vote(players, self.ctx), {"B", "SKIP"})
        with mock.patch.object(main, "ask", return_value="Zed"):
            self.assertEqual(players[0].vote(players, self.ctx, can_skip=False), "B")


class RoundTests(unittest.TestCase):
    def test_catching_the_only_impostor_wins(self):
        game = make_game(impostors={"Alice"})
        self.assertEqual(rigged_round(game, "Alice"), (True, "crew_win"))
        self.assertEqual(main.tally(game), "crew")

    def test_innocent_voted_out_continues(self):
        game = make_game(impostors={"Alice"})
        self.assertEqual(rigged_round(game, "Bob"), (False, "continue"))
        self.assertTrue(next(p for p in game.players if p.name == "Bob").was_voted_out)

    def test_second_impostor_keeps_game_going(self):
        game = make_game(num_impostors=2, impostors={"Alice", "Bob"})
        self.assertEqual(rigged_round(game, "Alice"), (False, "continue"))
        self.assertEqual(main.tally(game), "impostor")
        self.assertEqual(rigged_round(game, "Bob"), (True, "crew_win"))
        self.assertEqual(main.tally(game), "crew")

    def test_impostors_win_at_parity(self):
        game = make_game(num_impostors=2, impostors={"Alice", "Bob"})
        self.assertEqual(rigged_round(game, "Charlie"), (True, "impostor_win"))

    def test_skip_and_tie_eliminate_nobody(self):
        game = make_game(impostors={"Alice"})
        self.assertEqual(rigged_round(game, "SKIP"), (False, "skip"))
        votes = iter(["Alice", "Bob", "Alice", "Bob", "SKIP"])
        with mock.patch.object(main.Player, "say_word", return_value="w"), \
             mock.patch.object(main.Player, "vote", side_effect=lambda *a, **k: next(votes)), \
             mock.patch.object(main.Game, "pick_most_suspicious", return_value=None):
            self.assertEqual(quiet(game.play_round), (False, "tie"))
        self.assertFalse(any(p.was_voted_out for p in game.players))

    def test_max_rounds(self):
        game = make_game()
        game.round_number = game.max_rounds
        self.assertEqual(quiet(game.play_round), (True, "max_rounds"))
        self.assertEqual(game.round_number, game.max_rounds)  # summary reports rounds actually played

    def test_no_continue_prompt_after_last_round(self):
        game = make_game(impostors={"Alice"})
        with mock.patch.object(main.Player, "say_word", return_value="w"), \
             mock.patch.object(main.Player, "vote", return_value="SKIP"), \
             mock.patch.object(main.Game, "pick_most_suspicious", return_value=None), \
             mock.patch("builtins.input", return_value="") as prompt:
            quiet(game.start_game)
        self.assertEqual(game.round_number, game.max_rounds)
        self.assertEqual(prompt.call_count, game.max_rounds - 1)

    def test_pick_most_suspicious(self):
        game = make_game()
        with mock.patch.object(main, "ask", return_value="Eve"):
            self.assertEqual(game.pick_most_suspicious({}).name, "Eve")
        with mock.patch.object(main, "ask", side_effect=RuntimeError):
            self.assertIsNone(game.pick_most_suspicious({}))


if __name__ == "__main__":
    unittest.main()
