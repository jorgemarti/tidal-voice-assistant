from llm_parser import has_command_verb


def test_real_commands_have_a_verb():
    for t in ["reproduce el caballo percherón", "Okey música, pon algo de Rosalía", "ponme Bohemian Rhapsody",
              "quiero escuchar La Gossa Sorda", "play The Strokes", "posa Bon dia", "reproduce la canción esto es halloween"]:
        assert has_command_verb(t), t


def test_conversation_is_not_a_command():
    for t in ["Feelin' the Responsibility", "De La Soul", "we can we should focus on this next week",
              "¿Quieres el Cloe?", "era algo que me gusta a mí", "", None, "reponer el stock", "display settings"]:
        assert not has_command_verb(t), t
