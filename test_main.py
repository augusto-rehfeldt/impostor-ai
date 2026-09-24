"""Offline unit tests for Impostor; the OpenAI SDK and API key are never touched.

Run from this directory: python -B -m unittest -q test_main
"""
import contextlib
import io
import random
import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock

sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=mock.Mock()))
import main  # noqa: E402

NAMES = ["Alice", "Bob", "Charlie", "David", "Eve"]


def reply(text, reasoning=None):
    output = [SimpleNamespace(type="reasoning", summary=[SimpleNamespace(text=reasoning)])] if reasoning else []
    return SimpleNamespace(output_text=text, output=output)


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
    with mock.patch.object(main.Player, "say_word", return_value=("word", None)), \
         mock.patch.object(main.Player, "vote", return_value=(target, None)), \
         mock.patch.object(main.Game, "pick_most_suspicious", return_value=None):
        return quiet(game.play_round)


class ImportTests(unittest.TestCase):
    def test_import_does_not_build_client(self):
        import importlib
        sdk = sys.modules["openai"]
        sdk.OpenAI.reset_mock()
        importlib.reload(main)
        sdk.OpenAI.assert_not_called()


class StartupTests(unittest.TestCase):
    def test_missing_api_key_exits_with_message(self):
        with mock.patch.object(main, "api_key_path", main.Path("no-such-dir") / "api_key.txt"),              mock.patch("builtins.input", side_effect=AssertionError("prompted")):
            with self.assertRaisesRegex(SystemExit, "api_key.txt"):
                quiet(main.main)


class HelperTests(unittest.TestCase):
    def test_extract_reasoning(self):
        self.assertEqual(main.extract_reasoning(reply("x", "because")), "because")
        self.assertIsNone(main.extract_reasoning(reply("x")))

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
        with mock.patch.object(main, "ask", return_value=reply("Stovepipe hat", "tall")) as ask:
            self.assertEqual(main.Player("A", secret_person="Lincoln").say_word(self.ctx), ("stovepipe", "tall"))
        self.assertIn("Lincoln", ask.call_args.args[0])

    def test_impostor_prompt_hides_secret(self):
        with mock.patch.object(main, "ask", return_value=reply("hat")) as ask:
            main.Player("A", is_impostor=True).say_word(self.ctx)
        self.assertNotIn("Lincoln", ask.call_args.args[0])

    def test_api_errors_fall_back(self):
        player = main.Player("A", secret_person="Lincoln")
        with mock.patch.object(main, "ask", side_effect=RuntimeError("down")):
            self.assertEqual(quiet(player.say_word, self.ctx), ("hmm", None))
            self.assertEqual(quiet(player.defend, self.ctx), ("I am innocent!", None))
            players = [player, main.Player("B")]
            self.assertIn(quiet(player.vote, players, self.ctx)[0], {"B", "SKIP"})

    def test_vote_is_validated(self):
        players = [main.Player(n) for n in ("A", "B", "C")]
        players[2].was_voted_out = True
        with mock.patch.object(main, "ask", return_value=reply("B")):
            self.assertEqual(players[0].vote(players, self.ctx)[0], "B")
        for invalid in ("A", "C", "Zed"):  # self, eliminated, unknown
            with mock.patch.object(main, "ask", return_value=reply(invalid)):
                self.assertIn(players[0].vote(players, self.ctx)[0], {"B", "SKIP"})
        with mock.patch.object(main, "ask", return_value=reply("Zed")):
            self.assertEqual(players[0].vote(players, self.ctx, can_skip=False)[0], "B")


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
        with mock.patch.object(main.Player, "say_word", return_value=("w", None)), \
             mock.patch.object(main.Player, "vote", side_effect=lambda *a, **k: (next(votes), None)), \
             mock.patch.object(main.Game, "pick_most_suspicious", return_value=None):
            self.assertEqual(quiet(game.play_round), (False, "tie"))
        self.assertFalse(any(p.was_voted_out for p in game.players))

    def test_max_rounds(self):
        game = make_game()
        game.round_number = game.max_rounds
        self.assertEqual(quiet(game.play_round), (True, "max_rounds"))

    def test_pick_most_suspicious(self):
        game = make_game()
        with mock.patch.object(main, "ask", return_value=reply("Eve")):
            self.assertEqual(game.pick_most_suspicious({}).name, "Eve")
        with mock.patch.object(main, "ask", side_effect=RuntimeError):
            self.assertIsNone(game.pick_most_suspicious({}))


if __name__ == "__main__":
    unittest.main()
